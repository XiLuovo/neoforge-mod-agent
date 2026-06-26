from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent_models import AgentDecision, AgentStep
from .agent_options import normalize_code_lane as _normalize_code_lane
from .agent_runtime import AgentRuntimeRequest, AgentRuntimeStageResult
from .llm_planner import LLMPlanningError
from .models import RequestOverrides
from .neoforge_runtime_workflow_ports import (
    NeoForgeRuntimeDirectCodePort,
    NeoForgeRuntimePlanningPort,
)


@dataclass(slots=True)
class NeoForgePlanningWorkflowDeps:
    domain_name: str
    domain_spec_metadata: dict[str, Any]
    planning: NeoForgeRuntimePlanningPort
    direct_code: NeoForgeRuntimeDirectCodePort


class NeoForgePlanningWorkflow:
    """NeoForge ModSpec-first planning stage behind the runtime plugin."""

    def __init__(self, deps: NeoForgePlanningWorkflowDeps) -> None:
        self.deps = deps

    def run(self, request: AgentRuntimeRequest) -> AgentRuntimeStageResult:
        planning = self.deps.planning
        direct_code = self.deps.direct_code
        overrides = request.options.get("overrides") or RequestOverrides()
        try:
            resolution = planning.plan_generate(
                request.request,
                overrides=overrides,
                planner_mode=request.planner_mode,
                llm_provider=request.llm_provider,
                require_llm=bool(request.options.get("require_llm")),
            )
        except (LLMPlanningError, ValueError) as exc:
            traces = []
            if isinstance(exc, LLMPlanningError):
                traces.append(planning.trace_from_artifacts("planner_agent", "generate_modspec", exc.artifacts))
            return AgentRuntimeStageResult(
                success=False,
                steps=[
                    AgentStep(
                        role="planner_agent",
                        status="fail",
                        summary="Planning failed.",
                        errors=[str(exc)],
                    )
                ],
                prompt_traces=traces,
                payload={"planning_error": str(exc)},
                planner_mode_used=request.planner_mode,
            )

        spec = resolution.spec
        artifacts = resolution.artifacts
        planner_warnings = resolution.warnings
        planner_mode_used = resolution.planner_mode_used
        feature_count = len(list(spec.iter_features()))
        code_lane = _normalize_code_lane(str(request.options.get("code_lane", "hybrid")))
        intent_contract = planning.intent_contract(request.request, spec, artifacts, code_lane=code_lane)
        direct_code_requested = direct_code.should_use_direct_code(
            request.request,
            str(request.options.get("code_lane", "hybrid")),
            artifacts,
        )
        return AgentRuntimeStageResult(
            success=True,
            state={
                "spec": spec,
                "intent_contract": intent_contract,
                "artifacts": artifacts,
                "planner_warnings": planner_warnings,
            },
            steps=[
                AgentStep(
                    role="planner_agent",
                    status="pass",
                    summary=f"Planned ModSpec with {feature_count} feature(s).",
                    details={
                        "domain": self.deps.domain_name,
                        "domain_spec": self.deps.domain_spec_metadata,
                        "planner_mode_used": planner_mode_used,
                        "spec": spec.to_dict(),
                        "intent_contract": intent_contract,
                    },
                    warnings=planner_warnings,
                )
            ],
            decisions=[
                AgentDecision(
                    role="planner_agent",
                    decision="route_generation_request",
                    rationale="The NeoForge domain plugin keeps ModSpec as the first intent contract and can attach a Direct Code plan when the selected code lane requires audited source patches.",
                    inputs=[
                        "natural_language_request",
                        f"planner_mode={request.planner_mode}",
                        f"code_lane={code_lane}",
                    ],
                    outputs=[
                        f"features={feature_count}",
                        f"planner_mode_used={planner_mode_used}",
                        f"direct_code={direct_code_requested}",
                    ],
                    knowledge_refs=planning.planner_knowledge_refs(artifacts),
                )
            ],
            prompt_traces=[
                planning.planner_trace(
                    role="planner_agent",
                    prompt_kind="generate_modspec",
                    prompt=request.request,
                    planner_mode=planner_mode_used,
                    llm_provider=request.llm_provider,
                    artifacts=artifacts,
                    spec=spec,
                )
            ],
            payload={"intent_contract": intent_contract, "spec": spec.to_dict()},
            planner_mode_used=planner_mode_used,
        )
