from __future__ import annotations

import difflib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .agent_models import AgentPromptTrace
from .agentic_rag import (
    AgenticRAGPolicy,
    AgenticRAGRetriever,
    citation_coverage,
    mark_latest_trace_used_by_patch,
    write_rag_decision_trace,
)
from .auditor import WorkspaceAuditor
from .builder import GradleBuilder
from .config import AppConfig
from .knowledge_base import NeoForgeKnowledgeBase, expand_knowledge_query, summarize_knowledge_hits
from .llm_client import LLMClient, LLMProviderRequestError, create_llm_client
from .repair_loop import AutoRepairRunner
from .tools import ensure_directory, write_json, write_text


TOOL_CALLING_REPAIR_SYSTEM_PROMPT = """TOOL_CALLING_REPAIR_AGENT
You are a constrained NeoForge repair agent. Respond with exactly one JSON object.
Choose one tool per turn from:
retrieve_rag, read_file, search_files, regenerate_managed_files,
apply_structured_patch, run_audit, run_build, finish.

Patch safety rules:
- Do not output unified diffs or free-form patches.
- apply_structured_patch accepts only structured JSON changes.
- Supported patch operations: replace_text and write_file.
- Paths must be relative to the workspace and inside allowed generated roots.
- Never touch .git, build output, Gradle wrapper binaries, secrets, or binary files.
- Prefer reading/searching/retrieving before patching.
- If repair_action_hint is present, use it unless a recent observation proves it is wrong.
- Do not repeat the same read_file/search_files action when the failing file and replacement are already known.
- Before finish, make sure the requested audit/build gates have passed.

Response schema:
{
  "thought_summary": "short reason without hidden chain-of-thought",
  "action": "retrieve_rag|read_file|search_files|regenerate_managed_files|apply_structured_patch|run_audit|run_build|finish",
  "args": {}
}
"""

ALLOWED_REPAIR_ACTIONS = {
    "retrieve_rag",
    "read_file",
    "search_files",
    "regenerate_managed_files",
    "apply_structured_patch",
    "run_audit",
    "run_build",
    "finish",
}
SUPPORTED_STRUCTURED_PATCH_OPERATIONS = {"replace_text", "write_file"}
PATCH_ALLOWED_ROOTS = {
    "src/main/java",
    "src/main/resources",
    "src/main/templates",
    "build.gradle",
    "settings.gradle",
    "gradle.properties",
}
FORBIDDEN_PATH_PREFIXES = {
    ".git",
    ".gradle",
    "build",
    "gradle/wrapper",
}
FORBIDDEN_SECRET_NAMES = {
    ".env",
    ".env.local",
    ".npmrc",
    ".pypirc",
    "id_rsa",
    "id_ed25519",
}
BINARY_SUFFIXES = {
    ".class",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".keystore",
    ".png",
    ".so",
    ".webp",
    ".zip",
}
MAX_TEXT_FILE_BYTES = 512_000
MAX_READ_CHARS = 24_000
MAX_PROMPT_CHARS = 80_000


@dataclass(slots=True)
class StructuredPatchChange:
    operation: str
    path: str
    reason: str = ""
    old: str | None = None
    new: str | None = None
    content: str | None = None
    citation_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructuredPatchChange":
        operation = str(data.get("operation", "")).strip()
        old = data.get("old", data.get("search"))
        new = data.get("new", data.get("replace"))
        return cls(
            operation=operation,
            path=str(data.get("path", "")).strip(),
            reason=str(data.get("reason", "")).strip(),
            old=str(old) if old is not None else None,
            new=str(new) if new is not None else None,
            content=str(data["content"]) if data.get("content") is not None else None,
            citation_ids=[str(item) for item in data.get("citation_ids", []) if str(item).strip()]
            if isinstance(data.get("citation_ids"), list)
            else [],
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "operation": self.operation,
            "path": self.path,
            "reason": self.reason,
        }
        if self.old is not None:
            payload["old"] = self.old
        if self.new is not None:
            payload["new"] = self.new
        if self.content is not None:
            payload["content"] = self.content
        if self.citation_ids:
            payload["citation_ids"] = list(self.citation_ids)
        return payload


@dataclass(slots=True)
class StructuredPatchResult:
    success: bool
    changes: list[StructuredPatchChange]
    changed_files: list[str] = field(default_factory=list)
    snapshot_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: dict[str, Path] = field(default_factory=dict)
    diff_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "changes": [change.to_dict() for change in self.changes],
            "changed_files": list(self.changed_files),
            "snapshot_files": list(self.snapshot_files),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "artifacts": {key: str(path) for key, path in self.artifacts.items()},
        }


@dataclass(slots=True)
class ToolCallingRepairResult:
    success: bool
    workspace: Path
    goal: str
    loop_purpose: str
    max_iterations: int
    iterations: int
    repair_needed: bool
    repair_executed: bool
    repair_success: bool | None
    initial_build: dict[str, Any]
    initial_audit: dict[str, Any]
    final_build: dict[str, Any]
    final_audit: dict[str, Any]
    root_causes: list[str]
    repair_plan: list[dict[str, str]]
    trace: list[dict[str, Any]]
    prompt_traces: list[AgentPromptTrace] = field(default_factory=list)
    repair_rag: dict[str, Any] = field(default_factory=dict)
    rag_decision_trace: list[dict[str, Any]] = field(default_factory=list)
    structured_patch: dict[str, Any] = field(default_factory=dict)
    repair_loop: dict[str, Any] = field(default_factory=dict)
    finished: bool = False
    finish_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "attempted": True,
            "repair_needed": self.repair_needed,
            "repair_executed": self.repair_executed,
            "repair_success": self.repair_success,
            "success": self.success,
            "workspace": str(self.workspace),
            "goal": self.goal,
            "loop_purpose": self.loop_purpose,
            "max_iterations": self.max_iterations,
            "iterations": self.iterations,
            "finished": self.finished,
            "finish_summary": self.finish_summary,
            "root_causes": list(self.root_causes),
            "repair_plan": list(self.repair_plan),
            "initial_build": dict(self.initial_build),
            "initial_audit": dict(self.initial_audit),
            "final_build": dict(self.final_build),
            "final_audit": dict(self.final_audit),
            "repair_rag": dict(self.repair_rag),
            "rag_decision_trace": list(self.rag_decision_trace),
            "structured_patch": dict(self.structured_patch),
            "repair_loop": dict(self.repair_loop),
            "tool_call_trace": list(self.trace),
            "tool_calls_count": len(self.trace),
        }
        if self.repair_loop:
            payload["repair_loop_report_json_path"] = self.repair_loop.get("repair_loop_report_json_path")
            payload["repair_loop_report_md_path"] = self.repair_loop.get("repair_loop_report_md_path")
        if self.structured_patch:
            artifacts = self.structured_patch.get("artifacts") or {}
            payload["structured_patch_report_json_path"] = artifacts.get("report_json")
            payload["structured_patch_rollback_json_path"] = artifacts.get("rollback_json")
        return payload


class StructuredPatchApplier:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def apply(self, workspace: Path, payload: dict[str, Any]) -> StructuredPatchResult:
        workspace = workspace.resolve()
        changes = self._changes_from_payload(payload)
        artifacts = self._artifacts(workspace)
        errors = self._validate_changes(changes)
        warnings: list[str] = []
        changed_files: list[str] = []
        snapshot_files: list[str] = []
        before_by_path: dict[str, str] = {}
        after_by_path: dict[str, str] = {}

        write_json(artifacts["plan_json"], {"changes": [change.to_dict() for change in changes]})
        if not errors:
            for change in changes:
                target = resolve_repair_workspace_path(workspace, change.path)
                before = target.read_text(encoding="utf-8") if target.exists() else ""
                before_by_path[change.path] = before
                snapshot_path = self._snapshot_file(workspace, change.path, target)
                snapshot_files.append(str(snapshot_path.relative_to(workspace)))
                try:
                    after = self._apply_change(target, change, before)
                except ValueError as exc:
                    errors.append(str(exc))
                    break
                after_by_path[change.path] = after
                changed_files.append(change.path)

        diff_text = _render_diff(before_by_path, after_by_path)
        write_text(artifacts["diff_md"], diff_text)
        success = not errors
        report = {
            "version": "1.0",
            "status": "accepted" if success else "failed",
            "success": success,
            "mode": "tool-calling-structured-patch",
            "policy": {
                "patch_format": "structured-json",
                "supported_operations": sorted(SUPPORTED_STRUCTURED_PATCH_OPERATIONS),
                "allowed_roots": sorted(PATCH_ALLOWED_ROOTS),
                "rollback_available": True,
                "raw_diff_allowed": False,
            },
            "changes": [change.to_dict() for change in changes],
            "changed_files": changed_files,
            "snapshot_files": snapshot_files,
            "errors": errors,
            "warnings": warnings,
        }
        rollback = {
            "version": "1.0",
            "status": "standby" if success else "recommended",
            "rollback_required": not success,
            "trigger": "structured_patch_apply_fail" if not success else "not_run",
            "reason": "Structured patch applied." if success else "Structured patch failed before all changes were applied.",
            "changed_files": changed_files,
            "snapshot_files": snapshot_files,
            "rollback_steps": [
                "Restore changed files from .agent/structured-patch-snapshots.",
                "Re-run workspace audit.",
                "Re-run Gradle build if the repair run requires build validation.",
            ],
        }
        write_json(artifacts["report_json"], report)
        write_json(artifacts["rollback_json"], rollback)
        return StructuredPatchResult(
            success=success,
            changes=changes,
            changed_files=changed_files,
            snapshot_files=snapshot_files,
            errors=errors,
            warnings=warnings,
            artifacts=artifacts,
            diff_text=diff_text,
        )

    def _changes_from_payload(self, payload: dict[str, Any]) -> list[StructuredPatchChange]:
        raw_changes = payload.get("changes")
        if not isinstance(raw_changes, list):
            raw_changes = []
        return [StructuredPatchChange.from_dict(item) for item in raw_changes if isinstance(item, dict)]

    def _validate_changes(self, changes: list[StructuredPatchChange]) -> list[str]:
        errors: list[str] = []
        if not changes:
            errors.append("Structured patch must contain at least one change.")
        for change in changes:
            path_errors = validate_repair_relative_path(change.path)
            errors.extend(path_errors)
            if change.operation not in SUPPORTED_STRUCTURED_PATCH_OPERATIONS:
                errors.append(f"Unsupported structured patch operation for {change.path}: {change.operation}")
            if change.operation == "replace_text":
                if change.old is None or change.old == "":
                    errors.append(f"replace_text requires non-empty old text for {change.path}.")
                if change.new is None:
                    errors.append(f"replace_text requires new text for {change.path}.")
            if change.operation == "write_file" and change.content is None:
                errors.append(f"write_file requires content for {change.path}.")
            if not change.reason:
                errors.append(f"Structured patch change must include a reason for {change.path}.")
        return errors

    def _snapshot_file(self, workspace: Path, relative_path: str, target: Path) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        snapshot_root = ensure_directory(self.config.agent_dir_for(workspace) / "structured-patch-snapshots" / stamp)
        normalized = normalize_repair_relative_path(relative_path)
        snapshot_path = snapshot_root / normalized
        ensure_directory(snapshot_path.parent)
        if target.exists():
            shutil.copy2(target, snapshot_path)
        else:
            write_text(snapshot_path, "")
        return snapshot_path

    def _apply_change(self, target: Path, change: StructuredPatchChange, before: str) -> str:
        ensure_directory(target.parent)
        if change.operation == "write_file":
            after = change.content or ""
            write_text(target, after)
            return after
        if change.operation == "replace_text":
            old = change.old or ""
            count = before.count(old)
            if count != 1:
                raise ValueError(f"replace_text expected exactly one match in {change.path}, found {count}.")
            after = before.replace(old, change.new or "", 1)
            write_text(target, after)
            return after
        raise ValueError(f"Unsupported structured patch operation: {change.operation}")

    def _artifacts(self, workspace: Path) -> dict[str, Path]:
        agent_dir = ensure_directory(self.config.agent_dir_for(workspace))
        return {
            "plan_json": agent_dir / "structured-patch-plan.json",
            "diff_md": agent_dir / "structured-patch-diff.md",
            "report_json": agent_dir / "structured-patch-report.json",
            "rollback_json": agent_dir / "structured-patch-rollback-report.json",
        }


class ToolCallingRepairAgent:
    def __init__(
        self,
        config: AppConfig | None = None,
        *,
        llm_client: LLMClient | None = None,
        auditor: WorkspaceAuditor | None = None,
        builder: GradleBuilder | None = None,
        repair_runner: AutoRepairRunner | None = None,
        knowledge_base: NeoForgeKnowledgeBase | None = None,
        patch_applier: StructuredPatchApplier | None = None,
        rag_policy: AgenticRAGPolicy | None = None,
        rag_retriever: AgenticRAGRetriever | None = None,
    ) -> None:
        self.config = config or AppConfig.default()
        self.llm_client = llm_client
        self.auditor = auditor or WorkspaceAuditor(self.config)
        self.builder = builder or GradleBuilder(self.config)
        self.repair_runner = repair_runner or AutoRepairRunner(self.config)
        self.knowledge_base = knowledge_base or NeoForgeKnowledgeBase()
        self.patch_applier = patch_applier or StructuredPatchApplier(self.config)
        self.rag_policy = rag_policy or AgenticRAGPolicy()
        self.rag_retriever = rag_retriever or AgenticRAGRetriever(self.knowledge_base)

    def run(
        self,
        workspace: Path,
        *,
        goal: str,
        llm_provider: str,
        max_iterations: int,
        run_build: bool,
        run_audit: bool,
        initial_build: dict[str, Any],
        initial_audit: dict[str, Any],
        root_causes: list[str] | None = None,
        repair_plan: list[dict[str, str]] | None = None,
        loop_purpose: str = "repair",
        extra_context: dict[str, Any] | None = None,
        rag_mode: str = "auto",
    ) -> ToolCallingRepairResult:
        workspace = workspace.resolve()
        max_iterations = max(1, int(max_iterations or 1))
        client = self.llm_client or create_llm_client(llm_provider, self.config.project_root)
        root_causes = list(root_causes or classify_repair_root_causes(initial_build, initial_audit))
        repair_plan = list(repair_plan or repair_plan_actions(initial_build, initial_audit, root_causes))
        initial_repair_needed = _gate_failed(initial_build) or _gate_failed(initial_audit)

        state: dict[str, Any] = {
            "current_build": dict(initial_build),
            "current_audit": dict(initial_audit),
            "loop_purpose": str(loop_purpose or "repair"),
            "extra_context": dict(extra_context or {}),
            "rag_mode": _normalize_rag_mode(rag_mode),
            "observations": [
                {
                    "kind": "initial_observation",
                    "summary": _initial_observation_summary(initial_build, initial_audit),
                    "build": _compact_payload(initial_build),
                    "audit": _compact_payload(initial_audit),
                    "root_causes": root_causes,
                    "repair_plan": repair_plan,
                }
            ],
            "completed_actions": [],
            "repair_executed": False,
            "repair_rag": {},
            "rag_decision_trace": [],
            "structured_patch": {},
            "repair_loop": {},
            "finished": False,
            "finish_summary": "",
        }
        trace: list[dict[str, Any]] = []
        prompt_traces: list[AgentPromptTrace] = []

        for iteration in range(1, max_iterations + 1):
            user_prompt = self._build_user_prompt(
                workspace,
                goal=goal,
                iteration=iteration,
                max_iterations=max_iterations,
                run_build=run_build,
                run_audit=run_audit,
                state=state,
            )
            try:
                completion = client.complete_json(TOOL_CALLING_REPAIR_SYSTEM_PROMPT, user_prompt)
            except LLMProviderRequestError as exc:
                observation = _provider_error_observation(exc)
                trace.append(
                    {
                        "iteration": iteration,
                        "role": "repair_agent",
                        "source": "provider",
                        "provider": llm_provider,
                        "model": str(getattr(client, "model", "")),
                        "thought_summary": "The repair-agent provider request failed after retry handling.",
                        "action": "provider_error",
                        "args": {},
                        "observation": _compact_payload(observation),
                        "completion": observation.get("provider_error"),
                    }
                )
                prompt_traces.append(
                    AgentPromptTrace(
                        role="repair_agent",
                        planner_mode="tool_calling",
                        provider=llm_provider,
                        prompt_kind="repair_tool_call",
                        system_prompt=TOOL_CALLING_REPAIR_SYSTEM_PROMPT,
                        input_text=user_prompt,
                        error=str(exc),
                        completion_usage={"provider_error": exc.to_dict(), "provider_attempts": list(exc.attempt_summaries)},
                        completion_attempts=list(exc.attempt_summaries),
                    )
                )
                state["observations"].append(
                    {
                        "kind": "tool_observation",
                        "iteration": iteration,
                        "tool_action": "provider_error",
                        "summary": observation.get("summary", ""),
                        "observation": observation,
                    }
                )
                if exc.retryable and _audit_supports_managed_regeneration(state.get("current_audit", {})):
                    fallback = self._execute_tool(
                        workspace,
                        action="regenerate_managed_files",
                        args={},
                        run_build=run_build,
                        run_audit=run_audit,
                        state=state,
                    )
                    _append_executor_observation(
                        trace,
                        state,
                        action="regenerate_managed_files",
                        observation=fallback,
                        summary="Provider retries were exhausted; executor used deterministic managed-file regeneration.",
                    )
                    if _requested_gates_pass(state["current_build"], state["current_audit"], run_build=run_build, run_audit=run_audit):
                        state["finished"] = True
                        state["finish_summary"] = "Provider failed after retries; deterministic managed-file regeneration passed requested gates."
                break
            action_payload, parse_warnings = normalize_tool_action(completion.parsed_json)
            action = action_payload.get("action", "finish")
            args = action_payload.get("args", {})
            thought_summary = action_payload.get("thought_summary", "")
            observation = self._execute_tool(
                workspace,
                action=action,
                args=args if isinstance(args, dict) else {},
                run_build=run_build,
                run_audit=run_audit,
                state=state,
            )
            if parse_warnings:
                observation.setdefault("warnings", []).extend(parse_warnings)

            entry = {
                "iteration": iteration,
                "role": "repair_agent",
                "source": "llm",
                "provider": completion.provider,
                "model": completion.model,
                "thought_summary": thought_summary,
                "action": action,
                "args": _compact_payload(args if isinstance(args, dict) else {}),
                "observation": _compact_payload(observation),
                "completion": completion.telemetry_dict(),
            }
            trace.append(entry)
            prompt_traces.append(
                AgentPromptTrace(
                    role="repair_agent",
                    planner_mode="tool_calling",
                    provider=completion.provider,
                    prompt_kind="repair_tool_call",
                    system_prompt=TOOL_CALLING_REPAIR_SYSTEM_PROMPT,
                    input_text=user_prompt,
                    raw_text=completion.raw_text,
                    raw_json=completion.parsed_json,
                    normalized_json=action_payload,
                    warnings=parse_warnings,
                    completion_usage=completion.telemetry_dict(),
                    completion_attempts=list(completion.provider_attempts or []),
                )
            )
            state["completed_actions"].append(action)
            state["observations"].append(
                {
                    "kind": "tool_observation",
                    "iteration": iteration,
                    "tool_action": action,
                    "summary": observation.get("summary", ""),
                    "observation": observation,
                }
            )
            if action == "finish":
                state["finished"] = True
                state["finish_summary"] = str(observation.get("summary") or args.get("summary") or "")
                break

        if state["repair_executed"]:
            self._run_final_requested_gates(
                workspace,
                run_build=run_build,
                run_audit=run_audit,
                state=state,
                trace=trace,
            )

        final_build = dict(state["current_build"])
        final_audit = dict(state["current_audit"])
        success = _requested_gates_pass(final_build, final_audit, run_build=run_build, run_audit=run_audit)
        repair_executed = bool(state["repair_executed"])
        repair_success: bool | None
        if initial_repair_needed or repair_executed:
            repair_success = success
        else:
            repair_success = None

        result = ToolCallingRepairResult(
            success=success,
            workspace=workspace,
            goal=goal,
            loop_purpose=str(state.get("loop_purpose", "repair")),
            max_iterations=max_iterations,
            iterations=len(trace),
            repair_needed=initial_repair_needed,
            repair_executed=repair_executed,
            repair_success=repair_success,
            initial_build=dict(initial_build),
            initial_audit=dict(initial_audit),
            final_build=final_build,
            final_audit=final_audit,
            root_causes=root_causes,
            repair_plan=repair_plan,
            trace=trace,
            prompt_traces=prompt_traces,
            repair_rag=dict(state["repair_rag"]),
            rag_decision_trace=list(state["rag_decision_trace"]),
            structured_patch=dict(state["structured_patch"]),
            repair_loop=dict(state["repair_loop"]),
            finished=bool(state["finished"]),
            finish_summary=str(state["finish_summary"]),
        )
        self._write_repair_report(result)
        return result

    def _build_user_prompt(
        self,
        workspace: Path,
        *,
        goal: str,
        iteration: int,
        max_iterations: int,
        run_build: bool,
        run_audit: bool,
        state: dict[str, Any],
    ) -> str:
        payload = {
            "goal": goal,
            "loop_purpose": state.get("loop_purpose", "repair"),
            "workspace": str(workspace),
            "iteration": iteration,
            "max_iterations": max_iterations,
            "run_build_enabled": run_build,
            "run_audit_enabled": run_audit,
            "extra_context": _compact_payload(state.get("extra_context", {})),
            "rag_policy": {
                "mode": state.get("rag_mode", "auto"),
                "must_retrieve_when": [
                    "audit/build failure",
                    "unsupported request",
                    "NeoForge API or registry uncertainty",
                    "resource path or metadata uncertainty",
                    "reviewer evidence insufficiency",
                ],
                "recent_decisions": _compact_payload(state.get("rag_decision_trace", [])[-4:]),
            },
            "available_tools": tool_schemas(),
            "current_gates": {
                "build": _compact_payload(state["current_build"]),
                "audit": _compact_payload(state["current_audit"]),
            },
            "completed_actions": list(state["completed_actions"]),
            "repair_action_hint": _repair_action_hint(workspace, state),
            "recent_observations": _compact_payload(state["observations"][-8:]),
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if len(text) > MAX_PROMPT_CHARS:
            payload["current_gates"] = {
                "build": _gate_prompt_summary(state["current_build"]),
                "audit": _gate_prompt_summary(state["current_audit"]),
            }
            payload["recent_observations"] = [
                _observation_prompt_summary(item)
                for item in state["observations"][-6:]
                if isinstance(item, dict)
            ]
            text = json.dumps(payload, ensure_ascii=False, indent=2)
        if len(text) > MAX_PROMPT_CHARS:
            payload = {
                "goal": goal,
                "loop_purpose": state.get("loop_purpose", "repair"),
                "workspace": str(workspace),
                "iteration": iteration,
                "max_iterations": max_iterations,
                "run_build_enabled": run_build,
                "run_audit_enabled": run_audit,
                "extra_context": _compact_payload(state.get("extra_context", {}), max_string=2000),
                "available_tools": tool_schemas(),
                "current_gates": {
                    "build": _gate_prompt_summary(state["current_build"]),
                    "audit": _gate_prompt_summary(state["current_audit"]),
                },
                "completed_actions": list(state["completed_actions"]),
                "recent_observations": [
                    _observation_prompt_summary(item)
                    for item in state["observations"][-4:]
                    if isinstance(item, dict)
                ],
            }
            text = json.dumps(payload, ensure_ascii=False, indent=2)
        return text

    def _execute_tool(
        self,
        workspace: Path,
        *,
        action: str,
        args: dict[str, Any],
        run_build: bool,
        run_audit: bool,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if action not in ALLOWED_REPAIR_ACTIONS:
            return {"success": False, "summary": f"Unsupported repair tool action: {action}", "warnings": []}
        if action == "retrieve_rag":
            observation = self._retrieve_rag(workspace, args, state=state)
            state["repair_rag"] = observation
            return observation
        if action == "read_file":
            return self._read_file(workspace, args)
        if action == "search_files":
            return self._search_files(workspace, args)
        if action == "run_audit":
            observation = self._run_audit(workspace, enabled=run_audit)
            if observation.get("attempted"):
                state["current_audit"] = observation
            return observation
        if action == "run_build":
            observation = self._run_build(workspace, enabled=run_build)
            if observation.get("attempted"):
                state["current_build"] = observation
            return observation
        if action == "regenerate_managed_files":
            observation = self._regenerate_managed_files(workspace, run_build=run_build, run_audit=run_audit)
            state["repair_executed"] = True
            state["repair_loop"] = observation.get("repair_loop", {})
            last_attempt = observation.get("last_attempt") or {}
            if isinstance(last_attempt.get("build"), dict) and last_attempt["build"].get("attempted"):
                state["current_build"] = last_attempt["build"]
            if isinstance(last_attempt.get("audit"), dict) and last_attempt["audit"].get("attempted"):
                state["current_audit"] = last_attempt["audit"]
            return observation
        if action == "apply_structured_patch":
            args = self._attach_patch_citations(args, state)
            result = self.patch_applier.apply(workspace, args)
            citation_ids = _patch_citation_ids(args)
            mark_latest_trace_used_by_patch(state["rag_decision_trace"], citation_ids)
            write_rag_decision_trace(
                ensure_directory(self.config.agent_dir_for(workspace)),
                state["rag_decision_trace"],
            )
            observation = {
                "success": result.success,
                "summary": (
                    f"Applied structured patch to {len(result.changed_files)} file(s)."
                    if result.success
                    else "Structured patch failed."
                ),
                **result.to_dict(),
                "citation_ids": citation_ids,
                "citations": citation_ids,
                "rag_required": bool(citation_ids),
            }
            state["repair_executed"] = state["repair_executed"] or result.success
            state["structured_patch"] = result.to_dict()
            state["structured_patch"]["citation_ids"] = citation_ids
            return observation
        if action == "finish":
            requested_success = _requested_gates_pass(
                state["current_build"],
                state["current_audit"],
                run_build=run_build,
                run_audit=run_audit,
            )
            status = str(args.get("status", "success" if requested_success else "failed")).lower()
            summary = str(args.get("summary") or ("Requested gates passed." if requested_success else "Requested gates have not passed."))
            return {
                "success": requested_success and status not in {"fail", "failed", "error"},
                "summary": summary,
                "requested_gates_passed": requested_success,
                "status": status,
            }
        return {"success": False, "summary": f"Unhandled repair tool action: {action}"}

    def _retrieve_rag(self, workspace: Path, args: dict[str, Any], *, state: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "repair audit build failure")
        limit = _coerce_limit(args.get("limit"), default=5)
        max_hops = _coerce_limit(args.get("max_hops"), default=2, maximum=3)
        reason = str(args.get("reason") or "repair_agent_requested_rag")
        decision = self.rag_policy.decide(
            reason=reason,
            query=query,
            build=state.get("current_build", {}),
            audit=state.get("current_audit", {}),
            changed_files=_state_changed_files(state),
            reviewer_observation=_reviewer_observation_from_state(state),
            rag_mode=str(state.get("rag_mode", "auto")),
            sequence=len(state.get("rag_decision_trace", [])) + 1,
        )
        rag_trace = self.rag_retriever.retrieve(decision=decision, limit=limit, max_hops=max_hops)
        hit_dicts = list(rag_trace.hits)
        summary = summarize_knowledge_hits(hit_dicts)
        observation = {
            "success": not decision.skipped,
            "attempted": not decision.skipped,
            "summary": f"Retrieved {len(hit_dicts)} RAG snippet(s).",
            "query": decision.query,
            "original_query": query,
            "limit": limit,
            "max_hops": max_hops,
            "rag_decision_id": decision.decision_id,
            "rag_required": decision.rag_required,
            "would_require_rag": decision.would_require_rag,
            "rag_skipped": decision.skipped,
            "reason": decision.reason,
            "policy_triggers": list(decision.triggers),
            "queries": list(rag_trace.queries),
            "hops": list(rag_trace.hops),
            "citations": list(rag_trace.citations),
            "sufficiency": rag_trace.sufficiency,
            "hits": hit_dicts,
            "hits_count": len(hit_dicts),
            "query_expansions": expand_knowledge_query(query),
            "categories": summary["categories"],
            "capabilities": summary["capabilities"],
            "context": self.knowledge_base.render_context(decision.query, limit=limit) if not decision.skipped else "",
        }
        agent_dir = ensure_directory(self.config.agent_dir_for(workspace))
        report_json = agent_dir / "repair-rag-context.json"
        report_md = agent_dir / "repair-rag-context.md"
        observation["report_json_path"] = str(report_json)
        observation["report_md_path"] = str(report_md)
        state["rag_decision_trace"].append(rag_trace.to_dict())
        trace_path = write_rag_decision_trace(agent_dir, state["rag_decision_trace"])
        observation["rag_decision_trace_json_path"] = str(trace_path)
        write_json(report_json, observation)
        write_text(report_md, render_rag_markdown(observation))
        return observation

    def _attach_patch_citations(self, args: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        payload = dict(args)
        changes = payload.get("changes") if isinstance(payload.get("changes"), list) else []
        latest = _latest_rag_citations(state.get("rag_decision_trace", []))
        patched_changes: list[dict[str, Any]] = []
        for item in changes:
            if not isinstance(item, dict):
                continue
            change = dict(item)
            if not change.get("citation_ids") and latest:
                change["citation_ids"] = list(latest)
            patched_changes.append(change)
        payload["changes"] = patched_changes
        return payload

    def _read_file(self, workspace: Path, args: dict[str, Any]) -> dict[str, Any]:
        raw_path = str(args.get("path", "")).strip()
        try:
            target = resolve_readable_workspace_path(workspace, raw_path)
        except ValueError as exc:
            return {"success": False, "summary": str(exc), "path": raw_path}
        if not target.exists():
            return {"success": False, "summary": f"File does not exist: {raw_path}", "path": raw_path}
        if not target.is_file():
            return {"success": False, "summary": f"Path is not a file: {raw_path}", "path": raw_path}
        try:
            size = target.stat().st_size
            if size > MAX_TEXT_FILE_BYTES:
                return {"success": False, "summary": f"File is too large to read: {raw_path}", "path": raw_path, "bytes": size}
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"success": False, "summary": f"Failed to read {raw_path}: {exc}", "path": raw_path}
        truncated = len(text) > MAX_READ_CHARS
        content = text[:MAX_READ_CHARS]
        return {
            "success": True,
            "summary": f"Read {len(text.splitlines())} line(s) from {raw_path}.",
            "path": normalize_repair_relative_path(raw_path),
            "bytes": size,
            "content": content,
            "truncated": truncated,
        }

    def _search_files(self, workspace: Path, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()
        glob_pattern = str(args.get("glob") or "**/*").strip()
        limit = _coerce_limit(args.get("limit"), default=20, maximum=50)
        if not query:
            return {"success": False, "summary": "search_files requires a non-empty query."}
        matches: list[dict[str, Any]] = []
        workspace = workspace.resolve()
        for path in workspace.glob(glob_pattern):
            if len(matches) >= limit:
                break
            if not path.is_file():
                continue
            try:
                relative = path.resolve().relative_to(workspace).as_posix()
                if validate_readable_relative_path(relative):
                    continue
                if path.stat().st_size > MAX_TEXT_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                continue
            lowered_query = query.lower()
            for line_number, line in enumerate(text.splitlines(), start=1):
                if lowered_query in line.lower() or lowered_query in relative.lower():
                    matches.append(
                        {
                            "path": relative,
                            "line": line_number,
                            "preview": line.strip()[:240],
                        }
                    )
                    break
        return {
            "success": True,
            "summary": f"Found {len(matches)} file match(es) for {query}.",
            "query": query,
            "glob": glob_pattern,
            "matches": matches,
            "matches_count": len(matches),
        }

    def _run_audit(self, workspace: Path, *, enabled: bool) -> dict[str, Any]:
        if not enabled:
            return {"attempted": False, "success": None, "summary": "Audit is disabled for this repair run."}
        try:
            result = self.auditor.audit_workspace(workspace)
        except FileNotFoundError as exc:
            return {"attempted": True, "success": False, "summary": str(exc), "error": str(exc), "errors": [{"message": str(exc)}]}
        payload = result.to_dict()
        payload["attempted"] = True
        payload["summary"] = "Workspace audit passed." if result.success else "Workspace audit found issues."
        return payload

    def _run_build(self, workspace: Path, *, enabled: bool) -> dict[str, Any]:
        if not enabled:
            return {"attempted": False, "success": None, "summary": "Build is disabled for this repair run."}
        return self.builder.build(workspace, repair=True).to_dict()

    def _regenerate_managed_files(self, workspace: Path, *, run_build: bool, run_audit: bool) -> dict[str, Any]:
        result = self.repair_runner.run(workspace, max_attempts=1, run_build=run_build, run_audit=run_audit)
        attempts = [attempt.to_dict() for attempt in result.attempts]
        last_attempt = attempts[-1] if attempts else {}
        return {
            "success": result.success,
            "summary": (
                "Regenerated managed files and requested checks passed."
                if result.success
                else "Regenerated managed files but requested checks still fail."
            ),
            "repair_loop": result.to_dict(),
            "attempts_count": len(attempts),
            "last_attempt": last_attempt,
        }

    def _write_repair_report(self, result: ToolCallingRepairResult) -> None:
        agent_dir = ensure_directory(self.config.agent_dir_for(result.workspace))
        payload = result.to_dict()
        write_json(agent_dir / "agent-repair-plan.json", payload)
        lines = [
            "# Tool-Calling Repair Agent",
            "",
            f"Success: `{str(result.success).lower()}`",
            f"Repair needed: `{str(result.repair_needed).lower()}`",
            f"Repair executed: `{str(result.repair_executed).lower()}`",
            f"Iterations: `{result.iterations}/{result.max_iterations}`",
            "",
            "## Tool Calls",
            "",
        ]
        for entry in result.trace:
            observation = entry.get("observation") or {}
            lines.append(
                f"- {entry.get('iteration')}. `{entry.get('action')}` "
                f"`{observation.get('success')}`: {observation.get('summary', '')}"
            )
        if result.root_causes:
            lines.extend(["", "## Root Causes", ""])
            lines.extend(f"- {cause}" for cause in result.root_causes)
        lines.append("")
        write_text(agent_dir / "agent-repair-plan.md", "\n".join(lines))

    def _run_final_requested_gates(
        self,
        workspace: Path,
        *,
        run_build: bool,
        run_audit: bool,
        state: dict[str, Any],
        trace: list[dict[str, Any]],
    ) -> None:
        if run_audit and not _gate_success(state["current_audit"]):
            observation = self._run_audit(workspace, enabled=True)
            state["current_audit"] = observation
            _append_executor_observation(
                trace,
                state,
                action="run_audit",
                observation=observation,
                summary="Executor ran final audit after repair actions.",
            )
            if not _gate_success(observation) and _audit_has_worldgen_rule_test_failure(observation):
                regen_observation = self._regenerate_managed_files(workspace, run_build=run_build, run_audit=run_audit)
                state["repair_loop"] = regen_observation.get("repair_loop", {})
                last_attempt = regen_observation.get("last_attempt") or {}
                if isinstance(last_attempt.get("build"), dict) and last_attempt["build"].get("attempted"):
                    state["current_build"] = last_attempt["build"]
                if isinstance(last_attempt.get("audit"), dict) and last_attempt["audit"].get("attempted"):
                    state["current_audit"] = last_attempt["audit"]
                _append_executor_observation(
                    trace,
                    state,
                    action="regenerate_managed_files",
                    observation=regen_observation,
                    summary="Executor regenerated managed worldgen files after rule-test audit still failed.",
                )
        if run_build and not _gate_success(state["current_build"]):
            observation = self._run_build(workspace, enabled=True)
            state["current_build"] = observation
            _append_executor_observation(
                trace,
                state,
                action="run_build",
                observation=observation,
                summary="Executor ran final build after repair actions.",
            )


def normalize_tool_action(raw: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if not isinstance(raw, dict):
        return {
            "thought_summary": "The LLM did not return a JSON object.",
            "action": "finish",
            "args": {"status": "failed", "summary": "Invalid repair-agent JSON response."},
        }, ["Repair agent LLM response was not a JSON object."]
    action = str(raw.get("action", "")).strip()
    if action not in ALLOWED_REPAIR_ACTIONS:
        warnings.append(f"Unsupported action requested by LLM: {action}")
        action = "finish"
    args = raw.get("args", {})
    if not isinstance(args, dict):
        warnings.append("LLM args must be a JSON object; empty args were used.")
        args = {}
    thought_summary = str(raw.get("thought_summary", "")).strip()
    if not thought_summary:
        thought_summary = "Selected the next repair tool from the current observations."
    return {"thought_summary": thought_summary, "action": action, "args": args}, warnings


def tool_schemas() -> dict[str, Any]:
    return {
        "retrieve_rag": {
            "args": {
                "reason": "why retrieval is required",
                "query": "string",
                "limit": "integer optional",
                "max_hops": "integer optional, default 2, max 3",
            }
        },
        "read_file": {"args": {"path": "workspace-relative text file path"}},
        "search_files": {"args": {"query": "string", "glob": "optional glob", "limit": "integer optional"}},
        "regenerate_managed_files": {"args": {}},
        "apply_structured_patch": {
            "args": {
                "changes": [
                    {
                        "operation": "replace_text|write_file",
                        "path": "workspace-relative path",
                        "old": "required for replace_text",
                        "new": "required for replace_text",
                        "content": "required for write_file",
                        "reason": "short reason",
                        "citation_ids": "optional list of RAG citation ids",
                    }
                ]
            }
        },
        "run_audit": {"args": {}},
        "run_build": {"args": {}},
        "finish": {"args": {"status": "success|failed", "summary": "short final summary"}},
    }


def classify_repair_root_causes(build_payload: dict[str, Any], audit_payload: dict[str, Any]) -> list[str]:
    causes: list[str] = []
    if build_payload.get("attempted") and build_payload.get("success") is False:
        issues = build_payload.get("issues") or []
        if issues:
            causes.extend(str(issue.get("message", "Build issue")) for issue in issues if isinstance(issue, dict))
        else:
            causes.append(str(build_payload.get("summary", "Build failed.")))
    if audit_payload.get("attempted") and audit_payload.get("success") is False:
        errors = audit_payload.get("errors") or []
        if errors:
            causes.extend(str(error.get("message", "Audit issue")) for error in errors if isinstance(error, dict))
        elif audit_payload.get("error"):
            causes.append(str(audit_payload["error"]))
    return causes


def repair_plan_actions(
    build_payload: dict[str, Any],
    audit_payload: dict[str, Any],
    root_causes: list[str],
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if build_payload.get("attempted") and build_payload.get("success") is False:
        actions.append(
            {
                "id": "inspect_build_logs",
                "summary": "Inspect Gradle logs and map the failure to the generated source or resource file.",
                "artifact": str(build_payload.get("suspected_errors_path") or build_payload.get("stdout_path") or ""),
            }
        )
    if audit_payload.get("attempted") and audit_payload.get("success") is False:
        actions.append(
            {
                "id": "inspect_audit_report",
                "summary": "Inspect audit-report.json, then choose regenerate_managed_files or a minimal structured patch.",
                "artifact": str(audit_payload.get("audit_report_path") or ""),
            }
        )
    if not actions and root_causes:
        actions.append({"id": "review_root_causes", "summary": "Review root causes and choose a constrained repair.", "artifact": ""})
    return actions


def normalize_repair_relative_path(path: str) -> str:
    if not path or not str(path).strip():
        raise ValueError("Repair tool path must not be empty.")
    raw = str(path).replace("\\", "/").strip()
    pure = PurePosixPath(raw)
    if pure.is_absolute() or re.match(r"^[A-Za-z]:", raw):
        raise ValueError(f"Repair tool path must be relative: {path}")
    parts = pure.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Repair tool path must not contain traversal segments: {path}")
    return pure.as_posix()


def validate_repair_relative_path(path: str) -> list[str]:
    try:
        normalized = normalize_repair_relative_path(path)
    except ValueError as exc:
        return [str(exc)]
    errors: list[str] = []
    lowered = normalized.lower()
    if not _is_patch_allowed_path(lowered):
        errors.append(f"Structured patch path is outside allowed generated roots: {normalized}")
    errors.extend(validate_readable_relative_path(normalized))
    return errors


def validate_readable_relative_path(path: str) -> list[str]:
    try:
        normalized = normalize_repair_relative_path(path)
    except ValueError as exc:
        return [str(exc)]
    errors: list[str] = []
    lowered = normalized.lower()
    name = PurePosixPath(normalized).name.lower()
    if any(lowered == prefix or lowered.startswith(f"{prefix}/") for prefix in FORBIDDEN_PATH_PREFIXES):
        errors.append(f"Repair tool path is forbidden: {normalized}")
    if name in FORBIDDEN_SECRET_NAMES or name.startswith(".env."):
        errors.append(f"Repair tool cannot access secret or environment file: {normalized}")
    if PurePosixPath(normalized).suffix.lower() in BINARY_SUFFIXES:
        errors.append(f"Repair tool cannot access binary file: {normalized}")
    return errors


def resolve_repair_workspace_path(workspace: Path, relative_path: str) -> Path:
    errors = validate_repair_relative_path(relative_path)
    if errors:
        raise ValueError("; ".join(errors))
    root = workspace.resolve()
    target = (root / normalize_repair_relative_path(relative_path)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Repair tool path escapes workspace: {relative_path}") from exc
    return target


def resolve_readable_workspace_path(workspace: Path, relative_path: str) -> Path:
    errors = validate_readable_relative_path(relative_path)
    if errors:
        raise ValueError("; ".join(errors))
    root = workspace.resolve()
    target = (root / normalize_repair_relative_path(relative_path)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Repair tool path escapes workspace: {relative_path}") from exc
    return target


def render_rag_markdown(observation: dict[str, Any]) -> str:
    lines = [
        "# Repair RAG Context",
        "",
        f"Query: `{observation.get('query', '')}`",
        f"Reason: `{observation.get('reason', '')}`",
        f"Required: `{str(observation.get('rag_required', False)).lower()}`",
        f"Sufficiency: `{observation.get('sufficiency', '')}`",
        f"Queries: `{', '.join(observation.get('queries') or [])}`",
        f"Citations: `{', '.join(observation.get('citations') or [])}`",
        f"Hits: `{observation.get('hits_count', 0)}`",
        "",
        "## Hits",
        "",
    ]
    hits = observation.get("hits") or []
    if not hits:
        lines.append("- No matching bundled knowledge snippets were found.")
    for hit in hits:
        lines.append(f"- `{hit.get('id')}` score={hit.get('score')}: {hit.get('title')}")
        lines.append(f"  - summary: {hit.get('summary')}")
    if observation.get("context"):
        lines.extend(["", "## Context", "", "```text", str(observation.get("context", "")), "```"])
    lines.append("")
    return "\n".join(lines)


def _render_diff(before_by_path: dict[str, str], after_by_path: dict[str, str]) -> str:
    lines = ["# Structured Patch Diff", ""]
    paths = sorted(set(before_by_path) | set(after_by_path))
    if not paths:
        lines.extend(["No changes were applied.", ""])
        return "\n".join(lines)
    for path in paths:
        before = before_by_path.get(path, "")
        after = after_by_path.get(path, before)
        diff = difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
        lines.extend(["```diff", *diff, "```", ""])
    return "\n".join(lines)


def _is_patch_allowed_path(path: str) -> bool:
    for root in PATCH_ALLOWED_ROOTS:
        lowered = root.lower()
        if path == lowered or path.startswith(f"{lowered}/"):
            return True
    return False


def _requested_gates_pass(
    build_payload: dict[str, Any],
    audit_payload: dict[str, Any],
    *,
    run_build: bool,
    run_audit: bool,
) -> bool:
    build_ok = not run_build or (build_payload.get("attempted") and build_payload.get("success") is True)
    audit_ok = not run_audit or (audit_payload.get("attempted") and audit_payload.get("success") is True)
    return bool(build_ok and audit_ok)


def _gate_failed(payload: dict[str, Any]) -> bool:
    return bool(payload.get("attempted") and payload.get("success") is False)


def _gate_success(payload: dict[str, Any]) -> bool:
    return bool(payload.get("attempted") and payload.get("success") is True)


def _provider_error_observation(exc: LLMProviderRequestError) -> dict[str, Any]:
    return {
        "success": False,
        "summary": str(exc),
        "provider_error": exc.to_dict(),
        "provider_error_type": type(exc).__name__,
        "provider_status_code": exc.status_code,
        "provider_retryable": exc.retryable,
        "provider_attempts": exc.attempts,
    }


def _audit_supports_managed_regeneration(audit_payload: dict[str, Any]) -> bool:
    if not isinstance(audit_payload, dict) or audit_payload.get("success") is not False:
        return False
    if _audit_has_worldgen_rule_test_failure(audit_payload):
        return True
    errors = audit_payload.get("errors") if isinstance(audit_payload.get("errors"), list) else []
    managed_issue_prefixes = (
        "summary:",
        "item:",
        "block:",
        "recipe:",
        "ore:",
        "world_feature:",
        "entity:",
        "machine:",
        "project:pack_mcmeta",
    )
    managed_message_terms = (
        "missing required file",
        "invalid json",
        "missing lang key",
        "missing referenced id",
        "not a valid png",
        "png",
        "pack.mcmeta",
    )
    for item in errors:
        if not isinstance(item, dict):
            continue
        issue_id = str(item.get("id") or "")
        message = str(item.get("message") or "").lower()
        path = str(item.get("path") or "").replace("\\", "/").lower()
        managed_id = issue_id.startswith(managed_issue_prefixes)
        managed_path = "/src/main/resources/" in path or "/src/main/java/" in path or path.startswith("src/main/")
        managed_message = any(term in message for term in managed_message_terms)
        if managed_id and (managed_path or managed_message):
            return True
    return False


def _audit_has_worldgen_rule_test_failure(audit_payload: dict[str, Any]) -> bool:
    if not isinstance(audit_payload, dict):
        return False
    errors = audit_payload.get("errors") if isinstance(audit_payload.get("errors"), list) else []
    for item in errors:
        if not isinstance(item, dict):
            continue
        issue_id = str(item.get("id") or "")
        message = str(item.get("message") or "").lower()
        path = str(item.get("path") or "").replace("\\", "/").lower()
        if "configured_rule_test" in issue_id or "configured_predicate_type" in issue_id:
            return True
        if "configured feature target" in message and "/worldgen/configured_feature/" in path:
            return True
    return False


def _append_executor_observation(
    trace: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    action: str,
    observation: dict[str, Any],
    summary: str,
) -> None:
    entry = {
        "iteration": len(trace) + 1,
        "role": "repair_agent",
        "source": "executor",
        "provider": "deterministic",
        "model": "",
        "thought_summary": summary,
        "action": action,
        "args": {},
        "observation": _compact_payload(observation),
        "completion": None,
    }
    trace.append(entry)
    state["completed_actions"].append(action)
    state["observations"].append(
        {
            "kind": "tool_observation",
            "iteration": entry["iteration"],
            "tool_action": action,
            "summary": observation.get("summary", ""),
            "observation": observation,
        }
    )


def _normalize_rag_mode(value: str) -> str:
    normalized = str(value or "auto").strip().lower()
    return normalized if normalized in {"auto", "on", "off"} else "auto"


def _patch_citation_ids(args: dict[str, Any]) -> list[str]:
    citations: list[str] = []
    changes = args.get("changes") if isinstance(args.get("changes"), list) else []
    for item in changes:
        if not isinstance(item, dict):
            continue
        for citation in item.get("citation_ids", []) if isinstance(item.get("citation_ids"), list) else []:
            text = str(citation).strip()
            if text and text not in citations:
                citations.append(text)
    return citations


def _latest_rag_citations(traces: list[dict[str, Any]]) -> list[str]:
    for item in reversed(traces):
        citations = item.get("citations")
        if isinstance(citations, list) and citations:
            return [str(citation) for citation in citations if str(citation).strip()]
    return []


def _state_changed_files(state: dict[str, Any]) -> list[str]:
    structured = state.get("structured_patch")
    if isinstance(structured, dict):
        changed = structured.get("changed_files")
        if isinstance(changed, list):
            return [str(item) for item in changed]
    return []


def _reviewer_observation_from_state(state: dict[str, Any]) -> dict[str, Any]:
    extra = state.get("extra_context")
    if isinstance(extra, dict):
        reviewer = extra.get("reviewer_observation")
        if isinstance(reviewer, dict):
            return reviewer
        final = extra.get("final_reviewer")
        if isinstance(final, dict):
            return final
    return {}


def _repair_action_hint(workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    actions = [str(item) for item in state.get("completed_actions", [])]
    if "apply_structured_patch" in actions:
        return {}
    inspect_count = sum(1 for action in actions if action in {"read_file", "search_files"})
    if inspect_count < 2:
        return {}
    audit = state.get("current_audit") if isinstance(state.get("current_audit"), dict) else {}
    for error_item in audit.get("errors") if isinstance(audit.get("errors"), list) else []:
        if not isinstance(error_item, dict):
            continue
        message = str(error_item.get("message") or "")
        path_text = str(error_item.get("path") or "")
        missing_match = re.search(r"Missing referenced id '([^']+)'", message)
        if not missing_match or "/recipe/" not in path_text.replace("\\", "/"):
            continue
        missing_id = missing_match.group(1)
        replacement = _replacement_id_for_missing_reference(workspace, missing_id)
        relative_path = _relative_workspace_path(workspace, path_text)
        if not replacement or not relative_path:
            continue
        citations = _latest_rag_citations(state.get("rag_decision_trace", []))
        preferred_citation = "data.recipes_loot_tags" if "data.recipes_loot_tags" in citations else (citations[0] if citations else "")
        change: dict[str, Any] = {
            "operation": "replace_text",
            "path": relative_path,
            "old": missing_id,
            "new": replacement,
            "reason": "Audit identified a recipe JSON reference to a missing generated item id.",
        }
        if preferred_citation:
            change["citation_ids"] = [preferred_citation]
        return {
            "action": "apply_structured_patch",
            "why": "The audit error already identifies the recipe file and missing id; stop repeating reads/searches and patch the known reference.",
            "args": {"changes": [change]},
            "after_patch": "Run run_audit before finish.",
        }
    return {}


def _replacement_id_for_missing_reference(workspace: Path, missing_id: str) -> str | None:
    if ":" not in missing_id:
        return None
    namespace, broken_name = missing_id.split(":", 1)
    modspec_path = workspace / ".agent" / "modspec.json"
    try:
        modspec = json.loads(modspec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    candidates: list[str] = []
    features = modspec.get("features") if isinstance(modspec.get("features"), list) else []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        feature_id = str(feature.get("id") or feature.get("identifier") or "").strip()
        feature_type = str(feature.get("type") or "").strip()
        if feature_id and feature_type in {"item", "food", "ore", "block", "sword"}:
            candidates.append(f"{namespace}:{feature_id}")
    preferred_names = [
        broken_name.replace("missing_agentic_rag_material", "ruby"),
        broken_name.replace("missing_", ""),
        "ruby",
    ]
    for name in preferred_names:
        preferred = f"{namespace}:{name}"
        if preferred in candidates:
            return preferred
    return candidates[0] if candidates else None


def _relative_workspace_path(workspace: Path, path_text: str) -> str:
    try:
        return Path(path_text).resolve().relative_to(workspace.resolve()).as_posix()
    except (OSError, ValueError):
        normalized = path_text.replace("\\", "/")
        marker = "/src/main/"
        if marker in normalized:
            return "src/main/" + normalized.split(marker, 1)[1]
    return ""


def _initial_observation_summary(build_payload: dict[str, Any], audit_payload: dict[str, Any]) -> str:
    parts: list[str] = []
    if build_payload.get("attempted"):
        parts.append(f"build success={build_payload.get('success')}")
    if audit_payload.get("attempted"):
        parts.append(f"audit success={audit_payload.get('success')}")
    return ", ".join(parts) if parts else "No initial build or audit gate was requested."


def _compact_payload(value: Any, *, max_string: int = MAX_READ_CHARS) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        if len(value) <= max_string:
            return value
        return value[:max_string] + f"... [truncated {len(value) - max_string} chars]"
    if isinstance(value, list):
        return [_compact_payload(item, max_string=max_string) for item in value[:60]]
    if isinstance(value, dict):
        return {str(key): _compact_payload(item, max_string=max_string) for key, item in list(value.items())[:80]}
    return value


def _gate_prompt_summary(payload: dict[str, Any]) -> dict[str, Any]:
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    return {
        "attempted": payload.get("attempted"),
        "success": payload.get("success"),
        "summary": _compact_payload(payload.get("summary", ""), max_string=600),
        "error": _compact_payload(payload.get("error", ""), max_string=600),
        "errors_count": payload.get("errors_count", len(errors)),
        "warnings_count": payload.get("warnings_count", len(warnings)),
        "checks_count": payload.get("checks_count"),
        "errors": [_issue_prompt_summary(item) for item in errors[:8] if isinstance(item, dict)],
        "warnings": [_issue_prompt_summary(item) for item in warnings[:5] if isinstance(item, dict)],
    }


def _observation_prompt_summary(payload: dict[str, Any]) -> dict[str, Any]:
    observation = payload.get("observation") if isinstance(payload.get("observation"), dict) else {}
    summary = {
        "kind": payload.get("kind"),
        "iteration": payload.get("iteration"),
        "tool_action": payload.get("tool_action"),
        "summary": _compact_payload(payload.get("summary") or observation.get("summary", ""), max_string=800),
    }
    if observation:
        summary["success"] = observation.get("success")
        if observation.get("path"):
            summary["path"] = _compact_payload(observation.get("path"), max_string=800)
        if observation.get("content"):
            summary["content"] = _compact_payload(observation.get("content"), max_string=1600)
        matches = observation.get("matches") if isinstance(observation.get("matches"), list) else []
        if matches:
            summary["matches"] = [
                {
                    "path": _compact_payload(match.get("path", ""), max_string=800),
                    "line": match.get("line"),
                    "preview": _compact_payload(match.get("preview", ""), max_string=400),
                }
                for match in matches[:5]
                if isinstance(match, dict)
            ]
        summary["errors"] = [
            _issue_prompt_summary(item)
            for item in (observation.get("errors") if isinstance(observation.get("errors"), list) else [])[:8]
            if isinstance(item, dict)
        ]
        repair_loop = observation.get("repair_loop") if isinstance(observation.get("repair_loop"), dict) else {}
        attempts = repair_loop.get("attempts") if isinstance(repair_loop.get("attempts"), list) else []
        if attempts:
            last_attempt = attempts[-1] if isinstance(attempts[-1], dict) else {}
            summary["last_repair_attempt"] = {
                "success": last_attempt.get("success"),
                "errors": [
                    _compact_payload(item, max_string=600)
                    for item in (last_attempt.get("errors") if isinstance(last_attempt.get("errors"), list) else [])[:8]
                ],
                "audit": _gate_prompt_summary(last_attempt.get("audit") if isinstance(last_attempt.get("audit"), dict) else {}),
            }
    if payload.get("root_causes"):
        summary["root_causes"] = _compact_payload(payload.get("root_causes"), max_string=600)
    if payload.get("repair_plan"):
        summary["repair_plan"] = _compact_payload(payload.get("repair_plan"), max_string=600)
    return summary


def _issue_prompt_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": payload.get("id"),
        "message": _compact_payload(payload.get("message", ""), max_string=600),
        "path": _compact_payload(payload.get("path", ""), max_string=800),
    }


def _coerce_limit(value: Any, *, default: int, maximum: int = 12) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))
