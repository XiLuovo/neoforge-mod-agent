from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .agent_models import AgentDecision, AgentRunResult, AgentStep
from .agent_options import (
    normalize_rag_mode as _normalize_rag_mode,
    reviewer_requires_more_rag as _reviewer_requires_more_rag,
)
from .models import BuildResult
from .tool_calling_agent import ToolCallingRepairResult


class BuildWorkspaceFn(Protocol):
    def __call__(self, workspace: Path, *, repair: bool) -> BuildResult:
        ...


class RunAuditStepFn(Protocol):
    def __call__(
        self,
        workspace: Path,
        run_audit: bool,
        steps: list[AgentStep],
        decisions: list[AgentDecision],
    ) -> dict:
        ...


class RunToolCallingRepairFn(Protocol):
    def __call__(
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
        ...


class RunReviewerFn(Protocol):
    def __call__(
        self,
        *,
        workspace: Path,
        user_goal: str,
        llm_provider: str,
        review_stage: str,
        intent_contract: dict[str, Any] | None,
        modspec: dict[str, Any],
        rag: dict[str, Any],
        tool_call_trace: list[dict[str, Any]],
        changed_files: list[str],
        audit_result: dict[str, Any],
        build_result: dict[str, Any],
        steps: list[AgentStep],
        decisions: list[AgentDecision],
    ) -> Any:
        ...


@dataclass(slots=True)
class NeoForgeRepairObservationPort:
    build_workspace: BuildWorkspaceFn
    run_audit_step: RunAuditStepFn
    repair_root_causes: Callable[[dict, dict], list[str]]
    repair_plan_actions: Callable[[dict, dict, list[str]], list[dict[str, str]]]


@dataclass(slots=True)
class NeoForgeRepairToolLoopPort:
    run_tool_calling_repair: RunToolCallingRepairFn


@dataclass(slots=True)
class NeoForgeRepairReviewPort:
    repair_knowledge_refs: Callable[[dict], list[dict]]
    run_reviewer: RunReviewerFn
    load_modspec_dict: Callable[[Path], dict[str, Any]]
    changed_files_from_repair_payload: Callable[[dict[str, Any]], list[str]]


@dataclass(slots=True)
class NeoForgeRepairTracePort:
    write_agent_run: Callable[[AgentRunResult], None]


@dataclass(slots=True)
class NeoForgeRepairWorkflowDeps:
    observation: NeoForgeRepairObservationPort
    tool_loop: NeoForgeRepairToolLoopPort
    review: NeoForgeRepairReviewPort
    trace: NeoForgeRepairTracePort


class NeoForgeRepairWorkflow:
    """NeoForge-specific repair workflow behind the orchestrator facade."""

    def __init__(self, deps: NeoForgeRepairWorkflowDeps) -> None:
        self.deps = deps

    def run(
        self,
        workspace: Path,
        *,
        goal: str = "Fix build and audit failures without changing user-owned files.",
        planner_mode: str = "llm",
        llm_provider: str = "mock",
        max_iterations: int = 5,
        run_build: bool = True,
        run_audit: bool = True,
        rag_mode: str = "auto",
    ) -> AgentRunResult:
        deps = self.deps
        observation = deps.observation
        tool_loop = deps.tool_loop
        review = deps.review
        trace = deps.trace
        workspace = workspace.resolve()
        steps: list[AgentStep] = [
            AgentStep(
                role="context_loader",
                status="pass",
                summary="Loaded existing workspace for agent repair.",
                details={"workspace": str(workspace), "goal": goal},
            )
        ]
        decisions: list[AgentDecision] = [
            AgentDecision(
                role="context_loader",
                decision="load_existing_workspace",
                rationale="Agent repair works from the existing workspace and keeps .agent/modspec.json as the managed-file truth source.",
                inputs=[str(workspace), "repair_goal"],
                outputs=["workspace_context"],
            )
        ]

        build = (
            observation.build_workspace(workspace, repair=True)
            if run_build
            else BuildResult(attempted=False, success=None, summary="Gradle build was not executed.")
        )
        build_payload = build.to_dict()
        steps.append(
            AgentStep(
                role="builder_agent",
                status="pass" if build.success is not False else "fail",
                summary="Ran Gradle build before repair." if run_build else "Skipped Gradle build before repair.",
                details=build_payload,
                errors=[] if build.success is not False else [build.summary or "Build failed."],
            )
        )
        decisions.append(
            AgentDecision(
                role="builder_agent",
                decision="run_build_check" if run_build else "skip_build_check",
                rationale="Agent repair observes build output before selecting a repair action when build validation is enabled.",
                status="pass" if build.success is not False else "fail",
                inputs=["workspace"],
                outputs=[f"build_success={build.success}"],
            )
        )

        audit_payload = observation.run_audit_step(workspace, run_audit, steps, decisions)
        root_causes = observation.repair_root_causes(build_payload, audit_payload)
        repair_plan = observation.repair_plan_actions(build_payload, audit_payload, root_causes)
        try:
            tool_result = tool_loop.run_tool_calling_repair(
                workspace,
                goal=goal,
                llm_provider=llm_provider,
                max_iterations=max_iterations,
                run_build=run_build,
                run_audit=run_audit,
                initial_build=build_payload,
                initial_audit=audit_payload,
                root_causes=root_causes,
                repair_plan=repair_plan,
                rag_mode=_normalize_rag_mode(rag_mode),
            )
            repair_payload = tool_result.to_dict()
            steps.append(
                AgentStep(
                    role="repair_agent",
                    status="pass" if tool_result.success else "fail",
                    summary=(
                        "Executed LLM tool-calling repair loop."
                        if tool_result.success
                        else "LLM tool-calling repair loop did not pass requested gates."
                    ),
                    details={
                        "action": "tool_calling_repair_loop",
                        "tool_calls_count": tool_result.iterations,
                        "repair_success": tool_result.repair_success,
                        "final_build": tool_result.final_build,
                        "final_audit": tool_result.final_audit,
                    },
                    errors=[]
                    if tool_result.success
                    else observation.repair_root_causes(tool_result.final_build, tool_result.final_audit),
                )
            )
            decisions.append(
                AgentDecision(
                    role="repair_agent",
                    decision="execute_tool_calling_repair_loop",
                    rationale="The repair agent called the LLM after initial observations and executed only structured tools inside the workspace safety boundary.",
                    status="pass" if tool_result.success else "fail",
                    inputs=["repair_goal", "build_observation", "audit_observation"],
                    outputs=[
                        f"tool_calls={tool_result.iterations}",
                        f"repair_executed={tool_result.repair_executed}",
                        f"repair_success={tool_result.repair_success}",
                    ],
                    knowledge_refs=review.repair_knowledge_refs(repair_payload.get("repair_rag") or {}),
                )
            )
            prompt_traces = list(tool_result.prompt_traces)
            final_build_payload = repair_payload.get("final_build", build_payload)
            final_audit_payload = repair_payload.get("final_audit", audit_payload)
            success = tool_result.success
            reviewer_result = review.run_reviewer(
                workspace=workspace,
                user_goal=goal,
                llm_provider=llm_provider,
                review_stage="repair_final",
                intent_contract=None,
                modspec=review.load_modspec_dict(workspace),
                rag=repair_payload.get("repair_rag") or {},
                tool_call_trace=repair_payload.get("tool_call_trace") or [],
                changed_files=review.changed_files_from_repair_payload(repair_payload),
                audit_result=final_audit_payload,
                build_result=final_build_payload,
                steps=steps,
                decisions=decisions,
            )
            repair_payload["reviewer"] = reviewer_result.to_dict()
            prompt_traces = [*prompt_traces, reviewer_result.prompt_trace]
            if _reviewer_requires_more_rag(reviewer_result.to_dict()) and tool_result.iterations < max_iterations:
                followup_result = tool_loop.run_tool_calling_repair(
                    workspace,
                    goal=goal,
                    llm_provider=llm_provider,
                    max_iterations=max_iterations - tool_result.iterations,
                    run_build=run_build,
                    run_audit=run_audit,
                    initial_build=final_build_payload,
                    initial_audit=final_audit_payload,
                    root_causes=root_causes,
                    repair_plan=repair_plan,
                    extra_context={"reviewer_observation": reviewer_result.to_dict()},
                    rag_mode="on",
                )
                repair_payload["reviewer_requested_repair"] = followup_result.to_dict()
                repair_payload["final_build"] = followup_result.final_build
                repair_payload["final_audit"] = followup_result.final_audit
                repair_payload["success"] = followup_result.success
                repair_payload["repair_success"] = followup_result.repair_success
                combined_trace = [
                    *list(repair_payload.get("tool_call_trace") or []),
                    *list(followup_result.trace),
                ]
                repair_payload["tool_call_trace"] = combined_trace
                repair_payload["tool_calls_count"] = len(combined_trace)
                repair_payload["iterations"] = len(combined_trace)
                if followup_result.repair_rag:
                    repair_payload["repair_rag"] = followup_result.repair_rag
                if followup_result.structured_patch:
                    repair_payload["structured_patch"] = followup_result.structured_patch
                if followup_result.rag_decision_trace:
                    repair_payload["rag_decision_trace"] = [
                        *list(repair_payload.get("rag_decision_trace") or []),
                        *list(followup_result.rag_decision_trace),
                    ]
                prompt_traces.extend(followup_result.prompt_traces)
                final_build_payload = followup_result.final_build
                final_audit_payload = followup_result.final_audit
                success = followup_result.success
        except Exception as exc:  # Tool-calling repair failures must be replayable in agent-run.json.
            error_text = f"{type(exc).__name__}: {exc}"
            repair_payload = {
                "attempted": True,
                "repair_needed": bool(root_causes),
                "repair_executed": False,
                "repair_success": False,
                "root_causes": root_causes or [error_text],
                "repair_plan": repair_plan,
                "initial_build": build_payload,
                "initial_audit": audit_payload,
                "final_build": build_payload,
                "final_audit": audit_payload,
                "tool_call_trace": [
                    {
                        "iteration": 1,
                        "role": "repair_agent",
                        "source": "tool_error",
                        "action": "finish",
                        "args": {"status": "failed"},
                        "thought_summary": "Tool-calling repair could not start.",
                        "observation": {"success": False, "summary": error_text},
                    }
                ],
                "errors": [error_text],
            }
            steps.append(
                AgentStep(
                    role="repair_agent",
                    status="fail",
                    summary="Tool-calling repair failed before completion.",
                    details=repair_payload,
                    errors=[error_text],
                )
            )
            decisions.append(
                AgentDecision(
                    role="repair_agent",
                    decision="execute_tool_calling_repair_loop",
                    rationale="The repair agent attempted to start the LLM tool loop but encountered a normalized runtime failure.",
                    status="fail",
                    inputs=["repair_goal", "build_observation", "audit_observation"],
                    outputs=[error_text],
                )
            )
            prompt_traces = []
            final_build_payload = build_payload
            final_audit_payload = audit_payload
            success = False

        run = AgentRunResult(
            success=success,
            mode="repair",
            request=goal,
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            workspace=workspace,
            steps=steps,
            decisions=decisions,
            prompt_traces=prompt_traces,
            payload={
                "runtime": {
                    "domain": "neoforge",
                    "stages": ["context_loader", "builder", "auditor", "tool_calling_repair"],
                    "max_iterations": max_iterations,
                },
                "goal": goal,
                "initial_build": build_payload,
                "initial_audit": audit_payload,
                "build": final_build_payload,
                "audit": final_audit_payload,
                "repair": repair_payload,
                "reviewer": repair_payload.get("reviewer"),
            },
        )
        trace.write_agent_run(run)
        return run
