from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .agent_models import AgentDecision, AgentPromptTrace, AgentRunResult, AgentStep
from .config import AppConfig
from .domain_spec import DomainSpecPlugin
from .evidence_writer import AgentEvidenceWriter


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


@dataclass(slots=True)
class AgentRuntimeTrace:
    steps: list[AgentStep] = field(default_factory=list)
    decisions: list[AgentDecision] = field(default_factory=list)
    prompt_traces: list[AgentPromptTrace] = field(default_factory=list)

    def extend(self, stage: AgentRuntimeStageResult) -> None:
        self.steps.extend(stage.steps)
        self.decisions.extend(stage.decisions)
        self.prompt_traces.extend(stage.prompt_traces)

    def build_run(
        self,
        request: AgentRuntimeRequest,
        *,
        success: bool,
        planner_mode: str,
        payload: dict[str, Any],
        workspace: Path | None = None,
    ) -> AgentRunResult:
        return AgentRunResult(
            success=success,
            mode=request.mode,
            request=request.request,
            planner_mode=planner_mode,
            llm_provider=request.llm_provider,
            workspace=workspace,
            steps=list(self.steps),
            decisions=list(self.decisions),
            prompt_traces=list(self.prompt_traces),
            payload=payload,
        )


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
        trace = AgentRuntimeTrace()

        plan = self.plugin.plan_generate(request)
        trace.extend(plan)
        planner_mode_used = plan.planner_mode_used or request.planner_mode
        if not plan.success:
            return trace.build_run(
                request,
                success=False,
                planner_mode=planner_mode_used,
                payload=plan.payload,
            )

        review = self.plugin.review(request, plan)
        trace.extend(review)
        if not review.success:
            return trace.build_run(
                request,
                success=False,
                planner_mode=planner_mode_used,
                payload=self.plugin.review_failure_payload(request, plan, review),
            )

        execution = self.plugin.execute_generate(request, plan, review)
        trace.extend(execution)
        workspace = execution.workspace

        audit = self.plugin.audit(request, plan, execution)
        trace.extend(audit)

        repair = self.plugin.repair(request, execution, audit)
        trace.extend(repair)

        success = self.plugin.final_success(request, execution, audit, repair)
        run = trace.build_run(
            request,
            success=success,
            planner_mode=planner_mode_used,
            workspace=workspace,
            payload=self.plugin.final_payload(request, plan, review, execution, audit, repair),
        )
        self.trace_writer.write(run)
        return run


class AgentTraceWriter:
    """Compatibility facade for agent evidence writing."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.evidence_writer = AgentEvidenceWriter(config)

    def write(self, run: AgentRunResult) -> None:
        self.evidence_writer.write_agent_run(run)

    def write_agent_run(self, run: AgentRunResult) -> None:
        self.evidence_writer.write_agent_run(run)

    def agent_trace_summary(self, run: AgentRunResult) -> dict[str, Any]:
        return self.evidence_writer.agent_trace_summary(run)

    def tool_call_trace(self, run: AgentRunResult) -> list[dict[str, Any]]:
        return self.evidence_writer.tool_call_trace(run)

    def reviewer_report(self, run: AgentRunResult) -> dict[str, Any]:
        return self.evidence_writer.reviewer_report(run)

    def render_trace_summary_md(self, run: AgentRunResult, trace_summary: dict[str, Any]) -> str:
        return self.evidence_writer.render_trace_summary_md(run, trace_summary)

    def render_agent_run_md(self, run: AgentRunResult) -> str:
        return self.evidence_writer.render_agent_run_md(run)

    def render_reviewer_report_md(self, run: AgentRunResult, reviewer_report: dict[str, Any]) -> str:
        return self.evidence_writer.render_reviewer_report_md(run, reviewer_report)

    def render_decisions_md(self, run: AgentRunResult) -> str:
        return self.evidence_writer.render_decisions_md(run)
