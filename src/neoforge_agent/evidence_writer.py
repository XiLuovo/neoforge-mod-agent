from __future__ import annotations

import difflib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .agent_models import AgentDecision, AgentPromptTrace, AgentRunResult, AgentStep
from .config import AppConfig
from .tools import ensure_directory, slugify_mod_id, write_json, write_text

if TYPE_CHECKING:
    from .llm_planner import PlannerArtifacts


class AgentEvidenceWriter:
    """Writes replayable `.agent` evidence for agent and planner runs."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def write(self, run: AgentRunResult) -> None:
        self.write_agent_run(run)

    def write_agent_run(self, run: AgentRunResult) -> None:
        if run.workspace is None:
            return
        agent_dir = ensure_directory(self.config.agent_dir_for(run.workspace))
        json_path = agent_dir / "agent-run.json"
        md_path = agent_dir / "agent-run.md"
        decisions_md_path = agent_dir / "agent-decisions.md"
        prompt_trace_json_path = agent_dir / "prompt-trace.json"
        trace_summary_json_path = agent_dir / "agent-trace-summary.json"
        trace_summary_md_path = agent_dir / "agent-trace-summary.md"
        tool_call_trace_json_path = agent_dir / "tool-call-trace.json"
        reviewer_report_json_path = agent_dir / "reviewer-report.json"
        reviewer_report_md_path = agent_dir / "reviewer-report.md"
        run.agent_run_json_path = json_path
        run.agent_run_md_path = md_path
        run.agent_decisions_md_path = decisions_md_path
        run.prompt_trace_json_path = prompt_trace_json_path
        run.agent_trace_summary_json_path = trace_summary_json_path
        run.agent_trace_summary_md_path = trace_summary_md_path
        run.tool_call_trace_json_path = tool_call_trace_json_path
        run.reviewer_report_json_path = reviewer_report_json_path
        run.reviewer_report_md_path = reviewer_report_md_path
        trace_summary = self.agent_trace_summary(run)
        tool_call_trace = self.tool_call_trace(run)
        reviewer_report = self.reviewer_report(run)
        evidence = dict(run.payload.get("evidence") or {})
        evidence.update(
            {
                "prompt_trace_json_path": str(prompt_trace_json_path),
                "tool_call_trace_json_path": str(tool_call_trace_json_path),
                "tool_calls_count": len(tool_call_trace),
                "reviewer_report_json_path": str(reviewer_report_json_path),
                "reviewer_decision": reviewer_report.get("decision"),
                "reviewer_coverage_status": reviewer_report.get("coverage_status"),
                "reviewer_source": reviewer_report.get("source"),
            }
        )
        run.payload["evidence"] = evidence
        write_text(md_path, self.render_agent_run_md(run))
        write_text(decisions_md_path, self.render_decisions_md(run))
        write_json(prompt_trace_json_path, [trace.to_dict() for trace in run.prompt_traces])
        write_json(tool_call_trace_json_path, tool_call_trace)
        write_json(reviewer_report_json_path, reviewer_report)
        write_text(reviewer_report_md_path, self.render_reviewer_report_md(run, reviewer_report))
        write_json(trace_summary_json_path, trace_summary)
        write_text(trace_summary_md_path, self.render_trace_summary_md(run, trace_summary))
        write_json(json_path, run.to_dict())

    def write_planner_artifacts(self, project_dir: Path, artifacts: PlannerArtifacts) -> None:
        agent_dir = ensure_directory(self.config.agent_dir_for(project_dir))
        write_text(agent_dir / "planner-input.txt", artifacts.input_text)
        write_text(agent_dir / "planner-mode.txt", f"{artifacts.planner_mode}:{artifacts.provider}\n")
        if artifacts.system_prompt:
            write_text(agent_dir / "planner-system-prompt.txt", artifacts.system_prompt)

        if artifacts.raw_json is not None:
            write_json(agent_dir / "llm-plan-raw.json", artifacts.raw_json)
        elif artifacts.raw_text:
            write_json(agent_dir / "llm-plan-raw.json", {"raw_text": artifacts.raw_text})

        if artifacts.bad_json_outputs:
            bad_json_dir = ensure_directory(agent_dir / "llm-bad-json-output")
            write_json(agent_dir / "llm-bad-json-outputs.json", artifacts.bad_json_outputs)
            for index, record in enumerate(artifacts.bad_json_outputs, start=1):
                write_json(bad_json_dir / f"{index:02d}-bad-json-output.json", record)
                raw_text = str(record.get("raw_text", ""))
                if raw_text:
                    write_text(bad_json_dir / f"{index:02d}-bad-json-output.txt", raw_text)

        if artifacts.normalized_json is not None:
            write_json(agent_dir / "llm-plan-normalized.json", artifacts.normalized_json)

        if (
            artifacts.decomposed_feature_plan_raw_json is not None
            or artifacts.decomposed_feature_plan_json is not None
            or artifacts.decomposed_feature_json_outputs
            or artifacts.decomposed_composed_raw_json is not None
            or artifacts.decomposed_bad_raw_outputs
        ):
            self._write_decomposed_planner_artifacts(agent_dir, artifacts)

        if (
            artifacts.decomposed_modify_existing_context is not None
            or artifacts.decomposed_modify_feature_plan_raw_json is not None
            or artifacts.decomposed_modify_feature_plan_json is not None
            or artifacts.decomposed_modify_feature_patch_outputs
            or artifacts.decomposed_modify_composed_patch_raw_json is not None
            or artifacts.decomposed_modify_merge_preview_json is not None
            or artifacts.decomposed_modify_bad_raw_outputs
        ):
            self._write_decomposed_modify_artifacts(agent_dir, artifacts)

        write_json(agent_dir / "llm-plan-warnings.json", artifacts.warnings)
        write_json(
            agent_dir / "llm-stability.json",
            {
                "provider": artifacts.provider,
                "provider_config": artifacts.provider_config,
                "provider_health": artifacts.provider_health,
                "provider_metadata": artifacts.provider_metadata,
                "completion_usage": artifacts.completion_usage,
                "completion_attempts": artifacts.completion_attempts,
                "retry_attempts": artifacts.retry_attempts,
                "schema_retry_attempts": artifacts.schema_retry_attempts,
                "schema_validation_attempts": artifacts.schema_validation_attempts,
                "json_repair_applied": artifacts.json_repair_applied,
                "parse_attempts": artifacts.parse_attempts,
                "bad_json_outputs_count": len(artifacts.bad_json_outputs),
                "bad_json_outputs_path": "llm-bad-json-outputs.json" if artifacts.bad_json_outputs else None,
            },
        )
        write_json(
            agent_dir / "rag-context.json",
            {
                "query": artifacts.rag_query,
                "query_expansions": artifacts.rag_query_expansions,
                "hits": artifacts.rag_hits,
                "categories": artifacts.rag_categories,
                "capabilities": artifacts.rag_capabilities,
                "used_knowledge": artifacts.used_knowledge,
                "quality": artifacts.rag_quality,
                "context": artifacts.rag_context,
            },
        )
        write_json(agent_dir / "llm-used-knowledge.json", artifacts.used_knowledge)
        if artifacts.rag_context:
            write_text(agent_dir / "rag-context.md", self.render_rag_context_md(artifacts))

        if artifacts.error:
            lines = [
                "# LLM Plan Error",
                "",
                artifacts.error,
                "",
                "## Raw Output",
                "",
                "```text",
                artifacts.raw_text,
                "```",
                "",
            ]
            write_text(agent_dir / "llm-plan-error.md", "\n".join(lines))

    def patch_agent_artifacts(self, project_dir: Path) -> dict[str, Path]:
        agent_dir = ensure_directory(self.config.agent_dir_for(project_dir))
        return {
            "plan_json": agent_dir / "patch-agent-plan.json",
            "plan_md": agent_dir / "patch-agent-plan.md",
            "report_json": agent_dir / "patch-agent-report.json",
            "report_md": agent_dir / "patch-agent-report.md",
            "rollback_json": agent_dir / "patch-agent-rollback-report.json",
            "rollback_md": agent_dir / "patch-agent-rollback-report.md",
        }

    def write_patch_agent_plan(self, artifacts: Any, payload: dict[str, Any]) -> None:
        write_json(_artifact_path(artifacts, "plan_json"), payload)
        write_text(_artifact_path(artifacts, "plan_md"), self.render_patch_agent_plan_md(payload))

    def write_patch_agent_report(
        self,
        artifacts: Any,
        report_payload: dict[str, Any],
        rollback_payload: dict[str, Any],
    ) -> None:
        write_json(_artifact_path(artifacts, "report_json"), report_payload)
        write_text(_artifact_path(artifacts, "report_md"), self.render_patch_agent_report_md(report_payload))
        write_json(_artifact_path(artifacts, "rollback_json"), rollback_payload)
        write_text(_artifact_path(artifacts, "rollback_md"), self.render_patch_agent_rollback_md(rollback_payload))

    def direct_code_artifacts(self, project_dir: Path) -> dict[str, Path]:
        agent_dir = ensure_directory(self.config.agent_dir_for(project_dir))
        return {
            "plan_json": agent_dir / "direct-code-plan.json",
            "plan_md": agent_dir / "direct-code-plan.md",
            "review_json": agent_dir / "direct-code-review.json",
            "diff_md": agent_dir / "direct-code-diff.md",
            "report_json": agent_dir / "direct-code-report.json",
            "rollback_json": agent_dir / "direct-code-rollback-report.json",
        }

    def write_direct_code_plan(self, artifacts: Any, plan: Any, review: Any) -> None:
        write_json(_artifact_path(artifacts, "plan_json"), plan.to_dict())
        write_text(_artifact_path(artifacts, "plan_md"), self.render_direct_code_plan_md(plan))
        write_json(_artifact_path(artifacts, "review_json"), review.to_dict())

    def write_direct_code_diff(self, artifacts: Any, diff_text: str) -> None:
        write_text(_artifact_path(artifacts, "diff_md"), diff_text or "# Direct Code Diff\n\nNo changes were applied.\n")

    def write_direct_code_report(
        self,
        artifacts: Any,
        report_payload: dict[str, Any],
        rollback_payload: dict[str, Any],
    ) -> None:
        write_json(_artifact_path(artifacts, "report_json"), report_payload)
        write_json(_artifact_path(artifacts, "rollback_json"), rollback_payload)

    def structured_patch_artifacts(self, workspace: Path) -> dict[str, Path]:
        agent_dir = ensure_directory(self.config.agent_dir_for(workspace))
        return {
            "plan_json": agent_dir / "structured-patch-plan.json",
            "diff_md": agent_dir / "structured-patch-diff.md",
            "report_json": agent_dir / "structured-patch-report.json",
            "rollback_json": agent_dir / "structured-patch-rollback-report.json",
        }

    def write_structured_patch_plan(self, artifacts: Any, payload: dict[str, Any]) -> None:
        write_json(_artifact_path(artifacts, "plan_json"), payload)

    def write_structured_patch_report(
        self,
        artifacts: Any,
        *,
        diff_text: str,
        report_payload: dict[str, Any],
        rollback_payload: dict[str, Any],
    ) -> None:
        write_text(_artifact_path(artifacts, "diff_md"), diff_text)
        write_json(_artifact_path(artifacts, "report_json"), report_payload)
        write_json(_artifact_path(artifacts, "rollback_json"), rollback_payload)

    def repair_loop_report_paths(self, workspace: Path) -> dict[str, Path]:
        agent_dir = ensure_directory(self.config.agent_dir_for(workspace))
        return {
            "report_json": agent_dir / "repair-loop-report.json",
            "report_md": agent_dir / "repair-loop-report.md",
        }

    def write_repair_loop_report(self, result: Any) -> None:
        write_json(result.repair_loop_report_json_path, result.to_dict())
        write_text(result.repair_loop_report_md_path, self.render_repair_loop_report_md(result))

    def agent_repair_plan_paths(self, workspace: Path) -> dict[str, Path]:
        agent_dir = ensure_directory(self.config.agent_dir_for(workspace))
        return {
            "plan_json": agent_dir / "agent-repair-plan.json",
            "plan_md": agent_dir / "agent-repair-plan.md",
        }

    def write_agent_repair_plan(self, workspace: Path, payload: dict[str, Any]) -> None:
        paths = self.agent_repair_plan_paths(workspace)
        write_json(paths["plan_json"], payload)
        write_text(paths["plan_md"], self.render_agent_repair_plan_md(payload))

    def write_tool_calling_repair_report(self, result: Any) -> None:
        paths = self.agent_repair_plan_paths(result.workspace)
        write_json(paths["plan_json"], result.to_dict())
        write_text(paths["plan_md"], self.render_tool_calling_repair_plan_md(result))

    def repair_rag_context_paths(self, workspace: Path) -> dict[str, Path]:
        agent_dir = ensure_directory(self.config.agent_dir_for(workspace))
        return {
            "report_json": agent_dir / "repair-rag-context.json",
            "report_md": agent_dir / "repair-rag-context.md",
        }

    def write_repair_rag_result(self, workspace: Path, result: Any) -> None:
        paths = self.repair_rag_context_paths(workspace)
        result.report_json_path = paths["report_json"]
        result.report_md_path = paths["report_md"]
        write_json(result.report_json_path, result.to_dict())
        write_text(result.report_md_path, self.render_repair_rag_result_md(result))

    def write_repair_rag_observation(self, workspace: Path, observation: dict[str, Any]) -> dict[str, Path]:
        paths = self.repair_rag_context_paths(workspace)
        observation["report_json_path"] = str(paths["report_json"])
        observation["report_md_path"] = str(paths["report_md"])
        write_json(paths["report_json"], observation)
        write_text(paths["report_md"], self.render_repair_rag_observation_md(observation))
        return paths

    def agent_trace_summary(self, run: AgentRunResult) -> dict[str, Any]:
        decisions_by_role: dict[str, list[AgentDecision]] = {}
        for decision in run.decisions:
            decisions_by_role.setdefault(decision.role, []).append(decision)
        traces_by_role: dict[str, list[AgentPromptTrace]] = {}
        for trace in run.prompt_traces:
            traces_by_role.setdefault(trace.role, []).append(trace)

        roles = []
        for step in run.steps:
            role_decisions = decisions_by_role.get(step.role, [])
            role_traces = traces_by_role.get(step.role, [])
            role_knowledge_refs = _unique_knowledge_refs(
                item
                for decision in role_decisions
                for item in decision.knowledge_refs
            )
            roles.append(
                {
                    "role": step.role,
                    "status": step.status,
                    "summary": step.summary,
                    "inputs": sorted({item for decision in role_decisions for item in decision.inputs}),
                    "outputs": sorted({item for decision in role_decisions for item in decision.outputs}),
                    "decisions": [decision.to_dict() for decision in role_decisions],
                    "knowledge_ids": [str(item.get("id", "")) for item in role_knowledge_refs if item.get("id")],
                    "knowledge_refs": role_knowledge_refs,
                    "knowledge_refs_count": len(role_knowledge_refs),
                    "prompt_traces_count": len(role_traces),
                    "warnings_count": len(step.warnings),
                    "errors_count": len(step.errors),
                }
            )

        return {
            "success": run.success,
            "mode": run.mode,
            "request": run.request,
            "planner_mode": run.planner_mode,
            "llm_provider": run.llm_provider,
            "workspace": str(run.workspace or ""),
            "roles": roles,
            "roles_count": len(roles),
            "decisions_count": len(run.decisions),
            "prompt_traces_count": len(run.prompt_traces),
            "tool_calls_count": len(self.tool_call_trace(run)),
        }

    def tool_call_trace(self, run: AgentRunResult) -> list[dict[str, Any]]:
        payload_trace = _payload_tool_call_trace(run.payload)
        if payload_trace:
            return payload_trace

        calls: list[dict[str, Any]] = []
        for index, step in enumerate(run.steps, start=1):
            calls.append(
                {
                    "index": index,
                    "role": step.role,
                    "status": step.status,
                    "action": _action_from_step(step),
                    "summary": step.summary,
                    "inputs": _step_inputs(step),
                    "outputs": _step_outputs(step),
                    "warnings_count": len(step.warnings),
                    "errors_count": len(step.errors),
                    "source": "agent_step",
                }
            )
        return calls

    def reviewer_report(self, run: AgentRunResult) -> dict[str, Any]:
        payload_report = _payload_reviewer_report(run.payload)
        if payload_report:
            report = dict(payload_report)
            report.setdefault("mode", run.mode)
            report.setdefault("workspace", str(run.workspace or ""))
            report.setdefault("source", "llm_reviewer")
            return report
        review_steps = [step for step in run.steps if step.role == "reviewer_agent"]
        review_decisions = [decision for decision in run.decisions if decision.role == "reviewer_agent"]
        status = "skip"
        if review_steps:
            status = "pass" if all(step.status != "fail" for step in review_steps) else "fail"
        return {
            "success": status != "fail",
            "status": status,
            "mode": run.mode,
            "workspace": str(run.workspace or ""),
            "steps": [step.to_dict() for step in review_steps],
            "decisions": [decision.to_dict() for decision in review_decisions],
            "checks": [
                check
                for step in review_steps
                for check in _review_checks_from_step(step)
            ],
            "warnings": [warning for step in review_steps for warning in step.warnings],
            "errors": [error for step in review_steps for error in step.errors],
        }

    def render_trace_summary_md(self, run: AgentRunResult, trace_summary: dict[str, Any]) -> str:
        lines = [
            "# Agent Trace Summary",
            "",
            f"Success: {str(run.success).lower()}",
            f"Mode: `{run.mode}`",
            f"Planner: `{run.planner_mode}`",
            f"LLM provider: `{run.llm_provider}`",
            f"Workspace: `{run.workspace or ''}`",
            "",
            "## Roles",
            "",
        ]
        for role in trace_summary.get("roles", []):
            lines.append(f"### {role.get('role')} - {role.get('status')}")
            lines.append("")
            lines.append(str(role.get("summary", "")))
            lines.append("")
            inputs = role.get("inputs") or []
            outputs = role.get("outputs") or []
            if inputs:
                lines.append(f"- inputs: `{', '.join(inputs)}`")
            if outputs:
                lines.append(f"- outputs: `{', '.join(outputs)}`")
            knowledge_ids = role.get("knowledge_ids") or []
            if knowledge_ids:
                lines.append(f"- knowledge ids: `{', '.join(str(item) for item in knowledge_ids)}`")
            lines.append(f"- decisions: `{len(role.get('decisions') or [])}`")
            lines.append(f"- prompt traces: `{role.get('prompt_traces_count', 0)}`")
            lines.append("")
        return "\n".join(lines)

    def render_agent_run_md(self, run: AgentRunResult) -> str:
        lines = [
            "# Agent Run",
            "",
            f"Success: {str(run.success).lower()}",
            f"Mode: {run.mode}",
            f"Planner: {run.planner_mode}",
            f"LLM provider: {run.llm_provider}",
            f"Workspace: `{run.workspace or ''}`",
            "",
            "## Request",
            "",
            "```text",
            run.request,
            "```",
            "",
            "## Steps",
            "",
        ]
        for step in run.steps:
            lines.append(f"- `{step.role}` `{step.status}`: {step.summary}")
            for warning in step.warnings:
                lines.append(f"  - warning: {warning}")
            for error in step.errors:
                lines.append(f"  - error: {error}")
        lines.extend(["", "## Decisions", ""])
        for decision in run.decisions:
            lines.append(f"- `{decision.role}` `{decision.status}`: {decision.decision}")
            lines.append(f"  - rationale: {decision.rationale}")
            if decision.knowledge_ids:
                lines.append(f"  - knowledge ids: `{', '.join(decision.knowledge_ids)}`")
        if run.prompt_trace_json_path:
            lines.extend(["", "## Trace Artifacts", "", f"- prompt trace: `{run.prompt_trace_json_path}`"])
        if run.agent_decisions_md_path:
            lines.append(f"- decisions: `{run.agent_decisions_md_path}`")
        if run.agent_trace_summary_json_path:
            lines.append(f"- trace summary: `{run.agent_trace_summary_json_path}`")
        if run.tool_call_trace_json_path:
            lines.append(f"- tool call trace: `{run.tool_call_trace_json_path}`")
        if run.reviewer_report_json_path:
            lines.append(f"- reviewer report: `{run.reviewer_report_json_path}`")
        lines.append("")
        return "\n".join(lines)

    def render_reviewer_report_md(self, run: AgentRunResult, reviewer_report: dict[str, Any]) -> str:
        lines = [
            "# Reviewer Report",
            "",
            f"Status: `{reviewer_report.get('status')}`",
            f"Success: {str(reviewer_report.get('success')).lower()}",
            f"Mode: `{run.mode}`",
            f"Workspace: `{run.workspace or ''}`",
            "",
            "## Checks",
            "",
        ]
        checks = reviewer_report.get("checks") or []
        if checks:
            for check in checks:
                if isinstance(check, dict):
                    lines.append(
                        f"- `{check.get('name', check.get('id', 'check'))}` "
                        f"`{check.get('status', 'recorded')}`: {check.get('summary', check.get('message', ''))}"
                    )
                else:
                    lines.append(f"- {check}")
        else:
            lines.append("- No reviewer checks were recorded for this run.")
        errors = reviewer_report.get("errors") or []
        if errors:
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- {error}" for error in errors)
        warnings = reviewer_report.get("warnings") or []
        if warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
        return "\n".join(lines)

    def render_decisions_md(self, run: AgentRunResult) -> str:
        lines = [
            "# Agent Decisions",
            "",
            f"Success: {str(run.success).lower()}",
            f"Mode: `{run.mode}`",
            f"Planner: `{run.planner_mode}`",
            f"LLM provider: `{run.llm_provider}`",
            f"Workspace: `{run.workspace or ''}`",
            "",
            "## Decisions",
            "",
        ]
        for index, decision in enumerate(run.decisions, start=1):
            lines.append(f"### {index}. {decision.role} - {decision.decision}")
            lines.append("")
            lines.append(f"- status: `{decision.status}`")
            lines.append(f"- rationale: {decision.rationale}")
            if decision.inputs:
                lines.append(f"- inputs: `{', '.join(decision.inputs)}`")
            if decision.outputs:
                lines.append(f"- outputs: `{', '.join(decision.outputs)}`")
            if decision.knowledge_ids:
                lines.append(f"- knowledge ids: `{', '.join(decision.knowledge_ids)}`")
                lines.append("- knowledge refs:")
                for item in decision.knowledge_refs:
                    lines.append(
                        f"  - `{item.get('id')}` `{item.get('capability')}` "
                        f"score={item.get('score')}: {item.get('title')}"
                    )
            lines.append("")
        if not run.decisions:
            lines.append("- No decisions were recorded.")
            lines.append("")
        return "\n".join(lines)

    def render_rag_context_md(self, artifacts: PlannerArtifacts) -> str:
        lines = [
            "# RAG Context",
            "",
            f"Query: `{artifacts.rag_query}`",
            f"Expansions: `{', '.join(artifacts.rag_query_expansions)}`",
            f"Hits: {len(artifacts.rag_hits)}",
            "",
            "## Categories",
            "",
        ]
        if artifacts.rag_categories:
            lines.extend(f"- `{key}`: {value}" for key, value in artifacts.rag_categories.items())
        else:
            lines.append("- No category hits.")
        lines.extend(
            [
                "",
                "## Used Knowledge",
                "",
            ]
        )
        if artifacts.used_knowledge:
            for item in artifacts.used_knowledge:
                lines.append(f"- `{item.get('id')}` `{item.get('capability')}` score={item.get('score')}: {item.get('title')}")
        else:
            lines.append("- No retrieved knowledge was used.")
        lines.extend(
            [
                "",
                "## Hits",
                "",
            ]
        )
        if not artifacts.rag_hits:
            lines.append("- No retrieved snippets.")
        for hit in artifacts.rag_hits:
            lines.append(f"- `{hit.get('id')}` score={hit.get('score')}: {hit.get('title')}")
        lines.extend(["", "## Context", "", "```text", artifacts.rag_context, "```", ""])
        return "\n".join(lines)

    def render_patch_agent_plan_md(self, payload: dict[str, Any]) -> str:
        lines = [
            "# V6.2 Controlled Patch Agent Plan",
            "",
            f"Status: `{payload.get('status', 'unknown')}`",
            f"Mode: `{payload.get('mode', '')}`",
            f"Planner: `{payload.get('planner_mode', '')}`",
            f"LLM provider: `{payload.get('llm_provider', '')}`",
            "",
            "## Policy",
            "",
            f"- scope: {payload.get('policy', {}).get('scope', '')}",
            f"- managed roots: {', '.join(payload.get('policy', {}).get('managed_roots', []))}",
            f"- existing source edits: `{str(payload.get('policy', {}).get('existing_source_edits', False)).lower()}`",
            f"- raw repo edits: `{str(payload.get('policy', {}).get('raw_repo_edits', False)).lower()}`",
            f"- audit required: `{str(payload.get('policy', {}).get('requires_audit', False)).lower()}`",
            f"- build requested: `{str(payload.get('policy', {}).get('build_requested', False)).lower()}`",
            "",
            "## Changes",
            "",
            f"- added: {', '.join(payload.get('changes', {}).get('added', [])) or 'none'}",
            f"- updated: {', '.join(payload.get('changes', {}).get('updated', [])) or 'none'}",
            f"- skipped: {', '.join(payload.get('changes', {}).get('skipped', [])) or 'none'}",
            "",
            "## Rollback",
            "",
            f"Snapshot: `{payload.get('snapshot', {}).get('before_modspec', '')}`",
        ]
        for step in payload.get("rollback", {}).get("steps", []):
            lines.append(f"- {step}")
        if payload.get("warnings"):
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in payload.get("warnings", []))
        return "\n".join(lines) + "\n"

    def render_patch_agent_report_md(self, payload: dict[str, Any]) -> str:
        lines = [
            "# V6.2 Controlled Patch Agent Report",
            "",
            f"Status: `{payload.get('status', 'unknown')}`",
            f"Success: `{str(payload.get('success', False)).lower()}`",
            f"Mode: `{payload.get('mode', '')}`",
            f"Workspace: `{payload.get('workspace', '')}`",
            "",
            "## Gates",
            "",
            f"- audit: `{payload.get('audit_gate', {}).get('success')}`",
            f"- build: `{payload.get('build_gate', {}).get('status', 'unknown')}`",
            f"- repair: `{payload.get('repair_gate', {}).get('repair_success')}`",
            "",
            "## Changes",
            "",
            f"- added: {', '.join(payload.get('changes', {}).get('added', [])) or 'none'}",
            f"- updated: {', '.join(payload.get('changes', {}).get('updated', [])) or 'none'}",
            f"- skipped: {', '.join(payload.get('changes', {}).get('skipped', [])) or 'none'}",
            "",
            f"Managed files: `{payload.get('managed_file_count', 0)}`",
        ]
        plan_path = payload.get("plan_path")
        if plan_path:
            lines.extend(["", f"Plan: `{plan_path}`"])
        if payload.get("warnings"):
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in payload.get("warnings", []))
        return "\n".join(lines) + "\n"

    def render_patch_agent_rollback_md(self, payload: dict[str, Any]) -> str:
        lines = [
            "# V6.2 Patch Agent Rollback Report",
            "",
            f"Status: `{payload.get('status', 'unknown')}`",
            f"Rollback required: `{str(payload.get('rollback_required', False)).lower()}`",
            f"Trigger: `{payload.get('trigger', '')}`",
            f"Reason: {payload.get('reason', '')}",
            "",
            "## Managed Files",
            "",
        ]
        lines.extend(f"- `{path}`" for path in payload.get("managed_files", []))
        lines.extend(["", "## Rollback Steps", ""])
        lines.extend(f"{index}. {step}" for index, step in enumerate(payload.get("rollback_steps", []), start=1))
        if payload.get("failure"):
            lines.extend(["", "## Failure", ""])
            failure = payload["failure"]
            for key, value in failure.items():
                lines.append(f"- {key}: {value}")
        return "\n".join(lines) + "\n"

    def render_direct_code_plan_md(self, plan: Any) -> str:
        lines = [
            "# Direct Code Plan",
            "",
            f"Mode: `{plan.mode}`",
            f"Requires direct code: `{str(plan.requires_direct_code).lower()}`",
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

    def render_direct_code_diff(self, before_by_path: dict[str, str], after_by_path: dict[str, str]) -> str:
        lines = ["# Direct Code Diff", ""]
        paths = sorted(set(before_by_path) | set(after_by_path))
        if not paths:
            lines.append("No changes were applied.")
            lines.append("")
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

    def render_structured_patch_diff(self, before_by_path: dict[str, str], after_by_path: dict[str, str]) -> str:
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

    def render_repair_loop_report_md(self, result: Any) -> str:
        lines = [
            "# Repair Loop Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Workspace: `{result.workspace}`",
            f"Max repair attempts: {result.max_attempts}",
            f"Audit enabled: {str(result.audit_enabled).lower()}",
            f"Build enabled: {str(result.build_enabled).lower()}",
            f"Repaired: {str(result.repaired).lower()}",
            "",
            "## Attempts",
            "",
        ]
        for attempt in result.attempts:
            lines.append(f"### {attempt.index}. {attempt.phase}")
            lines.append("")
            lines.append(f"- action: `{attempt.action}`")
            lines.append(f"- success: {str(attempt.success).lower()}")
            if attempt.generated_files:
                lines.append(f"- regenerated files: {len(attempt.generated_files)}")
            if attempt.audit.get("attempted"):
                lines.append(f"- audit success: {attempt.audit.get('success')}")
                lines.append(f"- audit errors: {len(attempt.audit.get('errors', []))}")
            if attempt.build.get("attempted"):
                lines.append(f"- build success: {attempt.build.get('success')}")
                lines.append(f"- build summary: {attempt.build.get('summary')}")
            for warning in attempt.warnings:
                lines.append(f"- warning: {warning}")
            for error in attempt.errors:
                lines.append(f"- error: {error}")
            lines.append("")
        return "\n".join(lines)

    def render_agent_repair_plan_md(self, payload: dict[str, Any]) -> str:
        lines = [
            "# Agent Repair Plan",
            "",
            f"Repair needed: {str(payload.get('repair_needed')).lower()}",
            f"Repair executed: {str(payload.get('repair_executed')).lower()}",
            f"Repair success: {str(payload.get('repair_success')).lower()}",
            f"Debug context: `{payload.get('debug_context_path') or ''}`",
            f"Fix request: `{payload.get('fix_request_path') or ''}`",
            f"Audit report: `{payload.get('audit_report_path') or ''}`",
            f"Repair loop report: `{payload.get('repair_loop_report_md_path') or ''}`",
            "",
            "## Root Causes",
            "",
        ]
        root_causes = payload.get("root_causes") or []
        lines.extend([f"- {cause}" for cause in root_causes] or ["- No classified root causes."])
        lines.extend(["", "## Suggested Actions", ""])
        actions = payload.get("repair_plan") or []
        if actions:
            for action in actions:
                lines.append(f"- `{action.get('id', 'action')}`: {action.get('summary', '')}")
                if action.get("artifact"):
                    lines.append(f"  - artifact: `{action['artifact']}`")
        else:
            lines.append("- No repair actions are required.")
        repair_rag = payload.get("repair_rag") or {}
        if repair_rag:
            lines.extend(["", "## Repair RAG Context", ""])
            lines.append(f"- attempted: `{repair_rag.get('attempted')}`")
            lines.append(f"- success: `{repair_rag.get('success')}`")
            if repair_rag.get("reason"):
                lines.append(f"- reason: {repair_rag.get('reason')}")
            if repair_rag.get("query"):
                lines.append(f"- query: `{repair_rag.get('query')}`")
            lines.append(f"- hits: `{repair_rag.get('hits_count', 0)}`")
            lines.append(f"- json: `{repair_rag.get('report_json_path') or ''}`")
            lines.append(f"- report: `{repair_rag.get('report_md_path') or ''}`")
            hits = repair_rag.get("hits") or []
            if hits:
                lines.extend(["", "### Relevant Knowledge", ""])
                for hit in hits:
                    lines.append(f"- `{hit.get('id')}` score={hit.get('score')}: {hit.get('title')}")
                    lines.append(f"  - category: `{hit.get('category')}`")
                    lines.append(f"  - capability: `{hit.get('capability')}`")
                    lines.append(f"  - summary: {hit.get('summary')}")
        repair_loop = payload.get("repair_loop") or {}
        if repair_loop:
            lines.extend(["", "## Executed Repair Loop", ""])
            lines.append(f"- success: `{repair_loop.get('success')}`")
            lines.append(f"- repaired: `{repair_loop.get('repaired')}`")
            lines.append(f"- attempts: `{repair_loop.get('attempts_count')}`")
            lines.append(f"- json: `{repair_loop.get('repair_loop_report_json_path')}`")
            lines.append(f"- report: `{repair_loop.get('repair_loop_report_md_path')}`")
        lines.append("")
        return "\n".join(lines)

    def render_tool_calling_repair_plan_md(self, result: Any) -> str:
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
        return "\n".join(lines)

    def render_repair_rag_result_md(self, result: Any) -> str:
        lines = [
            "# Repair RAG Context",
            "",
            f"Success: {str(result.success).lower()}",
            f"Attempted: {str(result.attempted).lower()}",
            f"Query: `{result.query}`",
            f"Hits: `{result.hits_count}`",
            f"JSON: `{result.report_json_path or ''}`",
            f"Report: `{result.report_md_path or ''}`",
            "",
            "## Retrieved Knowledge",
            "",
        ]
        if not result.hits:
            lines.append("- No matching bundled knowledge snippets were found.")
        for hit in result.hits:
            lines.extend(
                [
                    f"- `{hit.get('id')}` score={hit.get('score')}: {hit.get('title')}",
                    f"  - category: `{hit.get('category')}`",
                    f"  - capability: `{hit.get('capability')}`",
                    f"  - summary: {hit.get('summary')}",
                ]
            )
        if result.query_expansions:
            lines.extend(["", "## Automatic Query Expansions", ""])
            lines.extend(f"- `{item}`" for item in result.query_expansions)
        lines.extend(["", "## Context", "", "```text", result.context, "```", ""])
        return "\n".join(lines)

    def render_repair_rag_observation_md(self, observation: dict[str, Any]) -> str:
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

    def _write_decomposed_planner_artifacts(self, agent_dir: Path, artifacts: PlannerArtifacts) -> None:
        decomposed_dir = ensure_directory(agent_dir / "decomposed-planner")
        if artifacts.decomposed_feature_plan_raw_json is not None:
            write_json(decomposed_dir / "feature-plan-raw.json", artifacts.decomposed_feature_plan_raw_json)
        if artifacts.decomposed_feature_plan_json is not None:
            write_json(decomposed_dir / "feature-plan.json", artifacts.decomposed_feature_plan_json)
        if artifacts.decomposed_composed_raw_json is not None:
            write_json(decomposed_dir / "composed-modspec-raw.json", artifacts.decomposed_composed_raw_json)
        if artifacts.decomposed_feature_json_outputs:
            feature_json_dir = ensure_directory(decomposed_dir / "feature-json")
            write_json(decomposed_dir / "feature-jsons.json", artifacts.decomposed_feature_json_outputs)
            for index, record in enumerate(artifacts.decomposed_feature_json_outputs, start=1):
                planned = record.get("planned") if isinstance(record.get("planned"), dict) else {}
                feature_type = slugify_mod_id(str(planned.get("type", "feature")), fallback="feature")
                feature_id = slugify_mod_id(str(planned.get("id", f"feature_{index}")), fallback=f"feature_{index}")
                write_json(feature_json_dir / f"{index:02d}-{feature_type}-{feature_id}.json", record)
        if artifacts.decomposed_bad_raw_outputs:
            bad_dir = ensure_directory(decomposed_dir / "bad-raw-output")
            write_json(decomposed_dir / "bad-raw-outputs.json", artifacts.decomposed_bad_raw_outputs)
            for index, record in enumerate(artifacts.decomposed_bad_raw_outputs, start=1):
                write_json(bad_dir / f"{index:02d}-bad-raw-output.json", record)
                raw_text = str(record.get("raw_text", ""))
                if raw_text:
                    write_text(bad_dir / f"{index:02d}-bad-raw-output.txt", raw_text)

    def _write_decomposed_modify_artifacts(self, agent_dir: Path, artifacts: PlannerArtifacts) -> None:
        decomposed_dir = ensure_directory(agent_dir / "decomposed-modify")
        if artifacts.decomposed_modify_existing_context is not None:
            write_json(decomposed_dir / "existing-context.json", artifacts.decomposed_modify_existing_context)
        if artifacts.decomposed_modify_feature_plan_raw_json is not None:
            write_json(decomposed_dir / "modify-feature-plan-raw.json", artifacts.decomposed_modify_feature_plan_raw_json)
        if artifacts.decomposed_modify_feature_plan_json is not None:
            write_json(decomposed_dir / "modify-feature-plan.json", artifacts.decomposed_modify_feature_plan_json)
        if artifacts.decomposed_modify_composed_patch_raw_json is not None:
            write_json(decomposed_dir / "composed-patch-modspec.json", artifacts.decomposed_modify_composed_patch_raw_json)
        if artifacts.decomposed_modify_merge_preview_json is not None:
            write_json(decomposed_dir / "merge-preview.json", artifacts.decomposed_modify_merge_preview_json)
        if artifacts.decomposed_modify_feature_patch_outputs:
            patch_dir = ensure_directory(decomposed_dir / "feature-patch")
            write_json(decomposed_dir / "feature-patches.json", artifacts.decomposed_modify_feature_patch_outputs)
            for index, record in enumerate(artifacts.decomposed_modify_feature_patch_outputs, start=1):
                planned = record.get("planned") if isinstance(record.get("planned"), dict) else {}
                feature_type = slugify_mod_id(str(planned.get("type", "feature")), fallback="feature")
                feature_id = slugify_mod_id(str(planned.get("id", f"feature_{index}")), fallback=f"feature_{index}")
                write_json(patch_dir / f"{index:02d}-{feature_type}-{feature_id}.json", record)
        if artifacts.decomposed_modify_bad_raw_outputs:
            bad_dir = ensure_directory(decomposed_dir / "bad-raw-output")
            write_json(decomposed_dir / "bad-raw-outputs.json", artifacts.decomposed_modify_bad_raw_outputs)
            for index, record in enumerate(artifacts.decomposed_modify_bad_raw_outputs, start=1):
                write_json(bad_dir / f"{index:02d}-bad-raw-output.json", record)
                raw_text = str(record.get("raw_text", ""))
                if raw_text:
                    write_text(bad_dir / f"{index:02d}-bad-raw-output.txt", raw_text)


def _payload_tool_call_trace(payload: dict[str, Any]) -> list[dict[str, Any]]:
    direct_trace = payload.get("tool_call_trace") if isinstance(payload, dict) else None
    if isinstance(direct_trace, list) and all(isinstance(item, dict) for item in direct_trace):
        return [dict(item) for item in direct_trace]
    repair_payload = payload.get("repair") if isinstance(payload, dict) else None
    if isinstance(repair_payload, dict):
        repair_trace = repair_payload.get("tool_call_trace")
        if isinstance(repair_trace, list) and all(isinstance(item, dict) for item in repair_trace):
            return [dict(item) for item in repair_trace]
    return []


def _payload_reviewer_report(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    direct = payload.get("reviewer")
    if isinstance(direct, dict) and direct.get("source") == "llm_reviewer":
        return dict(direct)
    repair_payload = payload.get("repair")
    if isinstance(repair_payload, dict):
        reviewer = repair_payload.get("reviewer")
        if isinstance(reviewer, dict) and reviewer.get("source") == "llm_reviewer":
            return dict(reviewer)
        final_reviewer = repair_payload.get("final_reviewer")
        if isinstance(final_reviewer, dict) and final_reviewer.get("source") == "llm_reviewer":
            return dict(final_reviewer)
    return {}


def _unique_knowledge_refs(items) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("id", "")).strip()
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        refs.append(dict(item))
    return refs


def _action_from_step(step: AgentStep) -> str:
    action = step.details.get("action") if isinstance(step.details, dict) else None
    if action:
        return str(action)
    return step.role.replace("_agent", "")


def _step_inputs(step: AgentStep) -> list[str]:
    if not isinstance(step.details, dict):
        return []
    inputs = step.details.get("inputs")
    if isinstance(inputs, list):
        return [str(item) for item in inputs]
    if step.role == "planner_agent":
        return ["natural_language_request"]
    if step.role == "reviewer_agent":
        return ["intent_contract", "modspec"]
    if step.role == "executor_agent":
        return ["reviewed_modspec"]
    if step.role == "auditor_agent":
        return ["workspace", ".agent/modspec.json", ".agent/generation-summary.json"]
    if step.role == "repair_agent":
        return ["build_result", "audit_result"]
    return []


def _step_outputs(step: AgentStep) -> list[str]:
    if not isinstance(step.details, dict):
        return []
    outputs = step.details.get("outputs")
    if isinstance(outputs, list):
        return [str(item) for item in outputs]
    if step.role == "planner_agent":
        return ["intent_contract"]
    if step.role == "reviewer_agent":
        return ["reviewer_report"]
    if step.role == "executor_agent":
        workspace = step.details.get("workspace")
        return [f"workspace={workspace}"] if workspace else ["workspace"]
    if step.role == "auditor_agent":
        return [".agent/audit-report.json"]
    if step.role == "repair_agent":
        return [".agent/agent-repair-plan.json", ".agent/repair-loop-report.json"]
    return []


def _review_checks_from_step(step: AgentStep) -> list[Any]:
    if not isinstance(step.details, dict):
        return []
    checks = step.details.get("review_checks")
    return list(checks) if isinstance(checks, list) else []


def _artifact_path(artifacts: Any, key: str) -> Path:
    if isinstance(artifacts, dict):
        return artifacts[key]
    return getattr(artifacts, key)
