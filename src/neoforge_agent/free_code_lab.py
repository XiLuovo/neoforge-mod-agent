from __future__ import annotations

import difflib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .auditor import WorkspaceAuditor
from .builder import GradleBuilder
from .config import AppConfig
from .direct_code_agent import FORBIDDEN_CONTENT_TOKENS, normalize_direct_code_path
from .llm_client import check_llm_provider_health, create_llm_client
from .models import BuildResult
from .tools import ensure_directory, safe_workspace_name, write_json, write_text


FREE_CODE_LAB_VERSION = "1.0"
FREE_CODE_OPERATIONS = {"write_file", "replace_text"}
FREE_CODE_RISK_LEVELS = {"low", "medium", "high"}
FREE_CODE_ALLOWED_ROOTS = {
    "src/main/java",
    "src/main/resources",
    "build.gradle",
    "gradle.properties",
    ".agent",
}
FREE_CODE_FORBIDDEN_PREFIXES = {
    ".git",
    "gradle/wrapper",
    "build",
    ".gradle",
}
HARVEST_RECOMMENDATIONS = {"reject", "keep_as_lab_sample", "harvest_into_generator"}
HARVEST_DIRECTIONS = {
    "modspec_field",
    "dsl",
    "java_generator_template",
    "json_resource_template",
    "audit_rule",
    "repair_rule",
}
MANUAL_RUNTIME_CHECKS = [
    "游戏能否启动",
    "能否创建/进入世界",
    "创造物品栏是否出现目标物品/方块",
    "方块能否放置、破坏、掉落",
    "GUI 能否打开",
    "配方是否可用",
    "服务端/客户端是否无崩溃",
    "日志是否有明显 error",
]


@dataclass(slots=True)
class FreeCodeChange:
    path: str
    operation: str
    reason: str
    risk_level: str = "medium"
    content: str | None = None
    search: str | None = None
    replace: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FreeCodeChange":
        return cls(
            path=str(data.get("path", "")),
            operation=str(data.get("operation", "")),
            reason=str(data.get("reason", "")),
            risk_level=str(data.get("risk_level", "medium")).lower(),
            content=str(data["content"]) if data.get("content") is not None else None,
            search=str(data["search"]) if data.get("search") is not None else None,
            replace=str(data["replace"]) if data.get("replace") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "path": self.path,
            "operation": self.operation,
            "reason": self.reason,
            "risk_level": self.risk_level,
        }
        if self.content is not None:
            payload["content"] = self.content
        if self.search is not None:
            payload["search"] = self.search
        if self.replace is not None:
            payload["replace"] = self.replace
        return payload


@dataclass(slots=True)
class FreeCodePlan:
    request: str
    summary: str = ""
    gap: str = "unknown"
    changes: list[FreeCodeChange] = field(default_factory=list)
    harvest_direction: str = "java_generator_template"

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, request: str) -> "FreeCodePlan":
        plan_data = data.get("free_code_plan") if isinstance(data.get("free_code_plan"), dict) else data
        changes = [
            FreeCodeChange.from_dict(raw)
            for raw in plan_data.get("changes", [])
            if isinstance(raw, dict)
        ]
        return cls(
            request=str(plan_data.get("request", request)),
            summary=str(plan_data.get("summary", "")),
            gap=str(plan_data.get("gap", "unknown")),
            changes=changes,
            harvest_direction=str(plan_data.get("harvest_direction", "java_generator_template")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": FREE_CODE_LAB_VERSION,
            "request": self.request,
            "summary": self.summary,
            "gap": self.gap,
            "harvest_direction": self.harvest_direction,
            "changes": [change.to_dict() for change in self.changes],
        }


@dataclass(slots=True)
class FreeCodeLabResult:
    success: bool
    run_id: str
    request: str
    source_workspace: Path
    lab_workspace: Path
    report_dir: Path
    plan: FreeCodePlan
    changed_files: list[str]
    errors: list[str]
    warnings: list[str]
    build: BuildResult
    audit_payload: dict[str, Any]
    manual_runtime_checklist_path: Path
    artifacts: dict[str, Path]
    harvest_candidate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "version": FREE_CODE_LAB_VERSION,
            "run_id": self.run_id,
            "request": self.request,
            "source_workspace": str(self.source_workspace),
            "lab_workspace": str(self.lab_workspace),
            "report_dir": str(self.report_dir),
            "plan": self.plan.to_dict(),
            "changed_files": list(self.changed_files),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "build": self.build.to_dict(),
            "audit": dict(self.audit_payload),
            "manual_runtime_checklist_path": str(self.manual_runtime_checklist_path),
            "artifacts": {key: str(value) for key, value in self.artifacts.items()},
            "harvest_candidate": dict(self.harvest_candidate),
        }


@dataclass(slots=True)
class HarvestReportResult:
    success: bool
    run_id: str
    report_dir: Path
    candidates: list[dict[str, Any]]
    metrics: dict[str, Any]
    report_json_path: Path
    report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "candidates": list(self.candidates),
            "metrics": dict(self.metrics),
            "report_json_path": str(self.report_json_path),
            "report_md_path": str(self.report_md_path),
        }


class FreeCodeLabRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()
        self.auditor = WorkspaceAuditor(self.config)
        self.builder = GradleBuilder(self.config)

    def run(
        self,
        request: str,
        *,
        from_workspace: Path,
        run_name: str | None = None,
        llm_provider: str = "mock",
        run_build: bool = False,
    ) -> FreeCodeLabResult:
        run_id = safe_workspace_name(run_name or datetime.now().strftime("%Y%m%d-%H%M%S"))
        source_workspace = from_workspace.resolve()
        if not source_workspace.exists():
            raise FileNotFoundError(f"Source workspace does not exist: {source_workspace}")
        run_dir = self.config.workspace_root / "free-code-lab-runs" / run_id
        if run_dir.exists():
            raise FileExistsError(f"Free-Code Lab run already exists: {run_dir}")
        report_dir = ensure_directory(run_dir / ".agent")
        lab_workspace = report_dir.parent / "workspace"
        shutil.copytree(source_workspace, lab_workspace)

        artifacts = free_code_lab_artifacts(report_dir)
        plan, warnings = self._plan(request, llm_provider=llm_provider)
        write_json(artifacts["plan_json"], plan.to_dict())
        write_text(artifacts["plan_md"], render_free_code_plan_md(plan))

        before_text_by_path: dict[str, str] = {}
        after_text_by_path: dict[str, str] = {}
        changed_files: list[str] = []
        errors = self._review_plan(plan)
        if not errors:
            for change in plan.changes:
                target = self._resolve_change_path(lab_workspace, change.path)
                before = target.read_text(encoding="utf-8") if target.exists() else ""
                before_text_by_path[change.path] = before
                try:
                    after = self._apply_change(target, change, before)
                except ValueError as exc:
                    errors.append(str(exc))
                    break
                after_text_by_path[change.path] = after
                changed_files.append(change.path)

        diff_text = render_free_code_diff(before_text_by_path, after_text_by_path)
        write_text(artifacts["diff_md"], diff_text)

        audit_payload = self._audit(lab_workspace) if not errors else {"attempted": False, "success": None}
        build_result = (
            self.builder.build(lab_workspace)
            if run_build and not errors
            else BuildResult(attempted=False, success=None, summary="Gradle build was not requested.")
        )
        checklist_path = write_manual_runtime_checklist_template(artifacts["manual_checklist_md"])
        success = not errors and _audit_success(audit_payload) and (not build_result.attempted or build_result.success is True)
        candidate = harvest_candidate_payload(
            run_id=run_id,
            request=request,
            plan=plan,
            source_workspace=source_workspace,
            lab_workspace=lab_workspace,
            changed_files=changed_files,
            build=build_result,
            audit_payload=audit_payload,
            manual_runtime_checklist_path=checklist_path,
            success=success,
            errors=errors,
        )
        write_json(artifacts["harvest_candidate_json"], candidate)
        report_payload = {
            "success": success,
            "version": FREE_CODE_LAB_VERSION,
            "run_id": run_id,
            "request": request,
            "source_workspace": str(source_workspace),
            "lab_workspace": str(lab_workspace),
            "policy": {
                "experimental_only": True,
                "does_not_update_generator": True,
                "allowed_roots": sorted(FREE_CODE_ALLOWED_ROOTS),
                "operations": sorted(FREE_CODE_OPERATIONS),
            },
            "plan": plan.to_dict(),
            "changed_files": changed_files,
            "audit": audit_payload,
            "build": build_result.to_dict(),
            "manual_runtime_checklist_path": str(checklist_path),
            "harvest_candidate_path": str(artifacts["harvest_candidate_json"]),
            "errors": errors,
            "warnings": warnings,
        }
        write_json(artifacts["report_json"], report_payload)
        return FreeCodeLabResult(
            success=success,
            run_id=run_id,
            request=request,
            source_workspace=source_workspace,
            lab_workspace=lab_workspace,
            report_dir=report_dir,
            plan=plan,
            changed_files=changed_files,
            errors=errors,
            warnings=warnings,
            build=build_result,
            audit_payload=audit_payload,
            manual_runtime_checklist_path=checklist_path,
            artifacts=artifacts,
            harvest_candidate=candidate,
        )

    def _plan(self, request: str, *, llm_provider: str) -> tuple[FreeCodePlan, list[str]]:
        warnings: list[str] = []
        if llm_provider == "openai-compatible":
            health = check_llm_provider_health(llm_provider)
            if not health.healthy:
                warnings.extend(["LLM provider health check failed; using deterministic lab sample.", *health.errors, *health.warnings])
                return deterministic_free_code_plan(request), warnings
        if llm_provider == "mock":
            return deterministic_free_code_plan(request), warnings
        try:
            client = create_llm_client(llm_provider, self.config.project_root)
            completion = client.complete_json(FREE_CODE_SYSTEM_PROMPT, free_code_user_prompt(request))
            if completion.parsed_json:
                return FreeCodePlan.from_dict(completion.parsed_json, request=request), warnings
            warnings.append("LLM did not return JSON; using deterministic lab sample.")
        except Exception as exc:  # noqa: BLE001 - lab generation must record provider failures and continue safely.
            warnings.append(f"LLM free-code planning failed; using deterministic lab sample: {exc}")
        return deterministic_free_code_plan(request), warnings

    def _review_plan(self, plan: FreeCodePlan) -> list[str]:
        errors: list[str] = []
        if not plan.changes:
            errors.append("Free-Code Lab plan must contain at least one change.")
        if plan.harvest_direction not in HARVEST_DIRECTIONS:
            errors.append(f"Unsupported harvest direction: {plan.harvest_direction}")
        for change in plan.changes:
            errors.extend(_validate_free_code_change(change))
        return errors

    def _resolve_change_path(self, workspace: Path, relative_path: str) -> Path:
        normalized = normalize_direct_code_path(relative_path)
        target = (workspace / normalized).resolve()
        workspace = workspace.resolve()
        if target != workspace and workspace not in target.parents:
            raise ValueError(f"Free-Code Lab path escapes workspace: {relative_path}")
        return target

    def _apply_change(self, target: Path, change: FreeCodeChange, before: str) -> str:
        ensure_directory(target.parent)
        if change.operation == "write_file":
            content = change.content or ""
            write_text(target, content)
            return content
        if change.operation == "replace_text":
            search = change.search or ""
            count = before.count(search)
            if count != 1:
                raise ValueError(f"replace_text expected exactly one match in {change.path}, found {count}.")
            after = before.replace(search, change.replace or "", 1)
            write_text(target, after)
            return after
        raise ValueError(f"Unsupported Free-Code Lab operation: {change.operation}")

    def _audit(self, workspace: Path) -> dict[str, Any]:
        try:
            result = self.auditor.audit_workspace(workspace)
        except FileNotFoundError as exc:
            return {"attempted": True, "success": False, "error": str(exc)}
        payload = result.to_dict()
        payload["attempted"] = True
        return payload


class HarvestReportRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(self, *, run_name: str | None = None) -> HarvestReportResult:
        run_id = safe_workspace_name(run_name or datetime.now().strftime("%Y%m%d-%H%M%S"))
        report_dir = ensure_directory(self.config.workspace_root / "harvest-runs" / run_id / ".agent")
        candidates = self._collect_candidates()
        metrics = _harvest_metrics(candidates)
        report_json = report_dir / "harvest-report.json"
        report_md = report_dir / "harvest-report.md"
        result = HarvestReportResult(
            success=True,
            run_id=run_id,
            report_dir=report_dir,
            candidates=candidates,
            metrics=metrics,
            report_json_path=report_json,
            report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, render_harvest_report_md(result))
        return result

    def _collect_candidates(self) -> list[dict[str, Any]]:
        root = self.config.workspace_root / "free-code-lab-runs"
        if not root.exists():
            return []
        candidates: list[dict[str, Any]] = []
        for path in sorted(root.glob("*/.agent/harvest-candidate.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            payload["candidate_path"] = str(path)
            candidates.append(payload)
        return candidates


def deterministic_free_code_plan(request: str) -> FreeCodePlan:
    content = "\n".join(
        [
            "# Free-Code Lab Note",
            "",
            f"Request: {request}",
            "",
            "This file is an experimental lab artifact. It is not part of the stable generator output.",
            "",
        ]
    )
    return FreeCodePlan(
        request=request,
        summary="Record an experimental generate-gap sample for harvest review.",
        gap=infer_generate_gap(request),
        harvest_direction=infer_harvest_direction(request),
        changes=[
            FreeCodeChange(
                path=".agent/free-code-lab-note.md",
                operation="write_file",
                content=content,
                reason="Keep an isolated lab artifact without changing stable generated sources.",
                risk_level="low",
            )
        ],
    )


def infer_generate_gap(request: str) -> str:
    lowered = request.lower()
    if "gui" in lowered or "screen" in lowered or "menu" in lowered or "界面" in request:
        return "advanced_machine_gui"
    if "boss" in lowered:
        return "boss_mechanic"
    if "multiblock" in lowered or "多方块" in request:
        return "multiblock_structure"
    if "network" in lowered or "同步" in request:
        return "network_sync"
    return "generate_gap"


def infer_harvest_direction(request: str) -> str:
    gap = infer_generate_gap(request)
    if gap == "advanced_machine_gui":
        return "java_generator_template"
    if gap in {"boss_mechanic", "multiblock_structure"}:
        return "dsl"
    return "modspec_field"


def free_code_lab_artifacts(report_dir: Path) -> dict[str, Path]:
    return {
        "plan_json": report_dir / "free-code-plan.json",
        "plan_md": report_dir / "free-code-plan.md",
        "diff_md": report_dir / "free-code-diff.md",
        "report_json": report_dir / "free-code-report.json",
        "manual_checklist_md": report_dir / "manual-runtime-checklist.md",
        "harvest_candidate_json": report_dir / "harvest-candidate.json",
    }


def write_manual_runtime_checklist_template(path: Path) -> Path:
    lines = ["# Manual Runtime Checklist", ""]
    lines.extend(f"- [ ] {item}" for item in MANUAL_RUNTIME_CHECKS)
    lines.extend(
        [
            "",
            "## Result",
            "",
            "- [ ] pass",
            "- [ ] fail",
            "",
            "Notes:",
            "",
        ]
    )
    return write_text(path, "\n".join(lines))


def harvest_candidate_payload(
    *,
    run_id: str,
    request: str,
    plan: FreeCodePlan,
    source_workspace: Path,
    lab_workspace: Path,
    changed_files: list[str],
    build: BuildResult,
    audit_payload: dict[str, Any],
    manual_runtime_checklist_path: Path,
    success: bool,
    errors: list[str],
) -> dict[str, Any]:
    recommendation = "keep_as_lab_sample"
    blockers: list[str] = []
    if errors:
        recommendation = "reject"
        blockers.extend(errors)
    elif audit_payload.get("attempted") and audit_payload.get("success") is False:
        recommendation = "reject"
        blockers.append("audit_failed")
    elif build.attempted and build.success is False:
        recommendation = "reject"
        blockers.append("build_failed")
    elif not manual_runtime_checklist_path.exists():
        recommendation = "reject"
        blockers.append("manual_runtime_checklist_missing")
    elif success:
        recommendation = "keep_as_lab_sample"
    return {
        "version": FREE_CODE_LAB_VERSION,
        "run_id": run_id,
        "request": request,
        "generate_gap": plan.gap,
        "harvest_direction": plan.harvest_direction,
        "recommendation": recommendation,
        "source_workspace": str(source_workspace),
        "lab_workspace": str(lab_workspace),
        "changed_files": list(changed_files),
        "manual_runtime_checklist_path": str(manual_runtime_checklist_path),
        "automatic_gates": {
            "audit": _audit_gate_payload(audit_payload),
            "build": _build_gate_payload(build),
        },
        "requires_manual_runtime_pass": True,
        "ready_to_harvest": recommendation == "harvest_into_generator",
        "blockers": blockers,
        "notes": [
            "Free-Code Lab samples never update the stable generator automatically.",
            "Set recommendation to harvest_into_generator only after manual runtime checklist is completed and reviewed.",
        ],
    }


def render_free_code_plan_md(plan: FreeCodePlan) -> str:
    lines = [
        "# Free-Code Lab Plan",
        "",
        f"Request: {plan.request}",
        f"Gap: `{plan.gap}`",
        f"Harvest direction: `{plan.harvest_direction}`",
        f"Summary: {plan.summary}",
        "",
        "## Changes",
        "",
    ]
    if not plan.changes:
        lines.append("- No changes declared.")
    for change in plan.changes:
        lines.extend(
            [
                f"- `{change.operation}` `{change.path}`",
                f"  - risk: `{change.risk_level}`",
                f"  - reason: {change.reason}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def render_free_code_diff(before_by_path: dict[str, str], after_by_path: dict[str, str]) -> str:
    lines = ["# Free-Code Lab Diff", ""]
    paths = sorted(set(before_by_path) | set(after_by_path))
    if not paths:
        lines.extend(["No changes were applied.", ""])
        return "\n".join(lines)
    for path in paths:
        diff = difflib.unified_diff(
            before_by_path.get(path, "").splitlines(),
            after_by_path.get(path, "").splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
        lines.extend(["```diff", *diff, "```", ""])
    return "\n".join(lines)


def render_harvest_report_md(result: HarvestReportResult) -> str:
    lines = [
        "# Capability Harvest Report",
        "",
        f"- run id: `{result.run_id}`",
        f"- candidates: `{len(result.candidates)}`",
        f"- ready to harvest: `{result.metrics.get('ready_to_harvest_count', 0)}`",
        f"- rejected: `{result.metrics.get('reject_count', 0)}`",
        "",
        "## Candidates",
        "",
    ]
    if not result.candidates:
        lines.append("- No Free-Code Lab candidates found.")
    for candidate in result.candidates:
        lines.extend(
            [
                f"- `{candidate.get('run_id')}` {candidate.get('generate_gap')} -> `{candidate.get('recommendation')}`",
                f"  - direction: `{candidate.get('harvest_direction')}`",
                f"  - request: {candidate.get('request')}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _validate_free_code_change(change: FreeCodeChange) -> list[str]:
    errors: list[str] = []
    try:
        normalized = normalize_direct_code_path(change.path)
    except ValueError as exc:
        return [str(exc)]
    lowered = normalized.lower()
    if not _is_allowed_free_code_path(lowered):
        errors.append(f"Free-Code Lab path is outside allowed roots: {normalized}")
    if any(lowered == prefix or lowered.startswith(f"{prefix}/") for prefix in FREE_CODE_FORBIDDEN_PREFIXES):
        errors.append(f"Free-Code Lab path is forbidden: {normalized}")
    if lowered.endswith(".jar") or lowered.endswith(".class"):
        errors.append(f"Free-Code Lab cannot modify binary artifacts: {normalized}")
    if change.operation not in FREE_CODE_OPERATIONS:
        errors.append(f"Unsupported Free-Code Lab operation for {change.path}: {change.operation}")
    if change.risk_level not in FREE_CODE_RISK_LEVELS:
        errors.append(f"Unsupported Free-Code Lab risk level for {change.path}: {change.risk_level}")
    if change.operation == "write_file" and change.content is None:
        errors.append(f"write_file requires content for {change.path}.")
    if change.operation == "replace_text":
        if not change.search:
            errors.append(f"replace_text requires non-empty search text for {change.path}.")
        if change.replace is None:
            errors.append(f"replace_text requires replace text for {change.path}.")
    if not change.reason.strip():
        errors.append(f"Free-Code Lab change must include a reason for {change.path}.")
    text = "\n".join(part for part in (change.content, change.search, change.replace) if part)
    for token in sorted(FORBIDDEN_CONTENT_TOKENS):
        if token in text:
            errors.append(f"Free-Code Lab change for {change.path} contains forbidden token: {token}")
    return errors


def _is_allowed_free_code_path(path: str) -> bool:
    return any(path == root or path.startswith(f"{root}/") for root in FREE_CODE_ALLOWED_ROOTS)


def _audit_success(audit_payload: dict[str, Any]) -> bool:
    return not audit_payload.get("attempted") or audit_payload.get("success") is True


def _build_gate_payload(build: BuildResult) -> dict[str, Any]:
    if not build.attempted:
        status = "not_run"
    elif build.success:
        status = "pass"
    else:
        status = "fail"
    return {"attempted": build.attempted, "success": build.success, "status": status, "summary": build.summary}


def _audit_gate_payload(audit_payload: dict[str, Any]) -> dict[str, Any]:
    if not audit_payload.get("attempted"):
        status = "not_run"
    elif audit_payload.get("success") is True:
        status = "pass"
    else:
        status = "fail"
    return {
        "attempted": bool(audit_payload.get("attempted")),
        "success": audit_payload.get("success"),
        "status": status,
        "errors_count": audit_payload.get("errors_count", len(audit_payload.get("errors", []) or [])),
        "warnings_count": audit_payload.get("warnings_count", len(audit_payload.get("warnings", []) or [])),
    }


def _harvest_metrics(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    recommendations: dict[str, int] = {key: 0 for key in HARVEST_RECOMMENDATIONS}
    directions: dict[str, int] = {key: 0 for key in HARVEST_DIRECTIONS}
    for candidate in candidates:
        recommendation = str(candidate.get("recommendation", "reject"))
        if recommendation in recommendations:
            recommendations[recommendation] += 1
        direction = str(candidate.get("harvest_direction", ""))
        if direction in directions:
            directions[direction] += 1
    return {
        "total_candidates": len(candidates),
        "ready_to_harvest_count": sum(1 for candidate in candidates if candidate.get("ready_to_harvest")),
        "reject_count": recommendations["reject"],
        "recommendations": recommendations,
        "directions": directions,
    }


FREE_CODE_SYSTEM_PROMPT = """You produce Free-Code Lab plans as JSON. Only output JSON."""


def free_code_user_prompt(request: str) -> str:
    return (
        "Create a Free-Code Lab plan for this NeoForge generated workspace request. "
        "Return JSON with free_code_plan containing request, summary, gap, harvest_direction, and changes. "
        "Allowed operations are write_file and replace_text. "
        "Allowed roots are src/main/java, src/main/resources, build.gradle, gradle.properties, and .agent. "
        f"Request: {request}"
    )
