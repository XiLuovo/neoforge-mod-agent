from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .agent_models import AgentDecision, AgentPromptTrace, AgentRunResult, AgentStep
from .config import AppConfig
from .domain_spec import DomainSpecPlugin
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class AgentRuntimeRequest:
    mode: str
    request: str
    planner_mode: str
    llm_provider: str
    run_build: bool = False
    run_audit: bool = True
    repair: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentRuntimeStageResult:
    success: bool
    steps: list[AgentStep] = field(default_factory=list)
    decisions: list[AgentDecision] = field(default_factory=list)
    prompt_traces: list[AgentPromptTrace] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    state: Any = None
    workspace: Path | None = None
    planner_mode_used: str | None = None
    build_payload: dict[str, Any] = field(default_factory=dict)


class AgentRuntimePlugin(Protocol):
    domain_name: str
    domain_spec_plugin: DomainSpecPlugin

    def plan_generate(self, request: AgentRuntimeRequest) -> AgentRuntimeStageResult:
        ...

    def review(self, request: AgentRuntimeRequest, plan: AgentRuntimeStageResult) -> AgentRuntimeStageResult:
        ...

    def execute_generate(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        ...

    def audit(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        ...

    def repair(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        ...

    def final_success(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> bool:
        ...

    def final_payload(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> dict[str, Any]:
        ...

    def review_failure_payload(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
    ) -> dict[str, Any]:
        ...


class AgentRuntime:
    """Domain-neutral agent workflow skeleton.

    The runtime owns the planner -> reviewer -> executor -> auditor -> repair
    control flow. Domain plugins own the actual planning, generation, audit,
    and repair behavior.
    """

    def __init__(self, plugin: AgentRuntimePlugin, trace_writer: "AgentTraceWriter") -> None:
        self.plugin = plugin
        self.trace_writer = trace_writer

    def run_generate(self, request: AgentRuntimeRequest) -> AgentRunResult:
        steps: list[AgentStep] = []
        decisions: list[AgentDecision] = []
        prompt_traces: list[AgentPromptTrace] = []

        plan = self.plugin.plan_generate(request)
        _extend_trace(steps, decisions, prompt_traces, plan)
        planner_mode_used = plan.planner_mode_used or request.planner_mode
        if not plan.success:
            return AgentRunResult(
                success=False,
                mode=request.mode,
                request=request.request,
                planner_mode=planner_mode_used,
                llm_provider=request.llm_provider,
                steps=steps,
                decisions=decisions,
                prompt_traces=prompt_traces,
                payload=plan.payload,
            )

        review = self.plugin.review(request, plan)
        _extend_trace(steps, decisions, prompt_traces, review)
        if not review.success:
            return AgentRunResult(
                success=False,
                mode=request.mode,
                request=request.request,
                planner_mode=planner_mode_used,
                llm_provider=request.llm_provider,
                steps=steps,
                decisions=decisions,
                prompt_traces=prompt_traces,
                payload=self.plugin.review_failure_payload(request, plan, review),
            )

        execution = self.plugin.execute_generate(request, plan, review)
        _extend_trace(steps, decisions, prompt_traces, execution)
        workspace = execution.workspace

        audit = self.plugin.audit(request, plan, execution)
        _extend_trace(steps, decisions, prompt_traces, audit)

        repair = self.plugin.repair(request, execution, audit)
        _extend_trace(steps, decisions, prompt_traces, repair)

        success = self.plugin.final_success(request, execution, audit, repair)
        run = AgentRunResult(
            success=success,
            mode=request.mode,
            request=request.request,
            planner_mode=planner_mode_used,
            llm_provider=request.llm_provider,
            workspace=workspace,
            steps=steps,
            decisions=decisions,
            prompt_traces=prompt_traces,
            payload=self.plugin.final_payload(request, plan, review, execution, audit, repair),
        )
        self.trace_writer.write(run)
        return run


class AgentTraceWriter:
    """Writes agent traces without depending on a specific generation domain."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def write(self, run: AgentRunResult) -> None:
        if run.workspace is None:
            return
        agent_dir = ensure_directory(self.config.agent_dir_for(run.workspace))
        json_path = agent_dir / "agent-run.json"
        md_path = agent_dir / "agent-run.md"
        decisions_md_path = agent_dir / "agent-decisions.md"
        prompt_trace_json_path = agent_dir / "prompt-trace.json"
        trace_summary_json_path = agent_dir / "agent-trace-summary.json"
        trace_summary_md_path = agent_dir / "agent-trace-summary.md"
        run.agent_run_json_path = json_path
        run.agent_run_md_path = md_path
        run.agent_decisions_md_path = decisions_md_path
        run.prompt_trace_json_path = prompt_trace_json_path
        run.agent_trace_summary_json_path = trace_summary_json_path
        run.agent_trace_summary_md_path = trace_summary_md_path
        trace_summary = self.agent_trace_summary(run)
        write_text(md_path, self.render_agent_run_md(run))
        write_text(decisions_md_path, self.render_decisions_md(run))
        write_json(prompt_trace_json_path, [trace.to_dict() for trace in run.prompt_traces])
        write_json(trace_summary_json_path, trace_summary)
        write_text(trace_summary_md_path, self.render_trace_summary_md(run, trace_summary))
        write_json(json_path, run.to_dict())

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


def _extend_trace(
    steps: list[AgentStep],
    decisions: list[AgentDecision],
    prompt_traces: list[AgentPromptTrace],
    stage: AgentRuntimeStageResult,
) -> None:
    steps.extend(stage.steps)
    decisions.extend(stage.decisions)
    prompt_traces.extend(stage.prompt_traces)


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
