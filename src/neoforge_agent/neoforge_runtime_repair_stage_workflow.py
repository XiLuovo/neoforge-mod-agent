from __future__ import annotations

from dataclasses import dataclass

from .agent_models import AgentDecision, AgentStep
from .agent_runtime import AgentRuntimeRequest, AgentRuntimeStageResult
from .neoforge_runtime_workflow_ports import (
    NeoForgeRuntimeDevelopRefinePort,
    NeoForgeRuntimeRepairPort,
)


@dataclass(slots=True)
class NeoForgeRuntimeRepairStageWorkflowDeps:
    repair: NeoForgeRuntimeRepairPort
    develop_refine: NeoForgeRuntimeDevelopRefinePort


class NeoForgeRuntimeRepairStageWorkflow:
    """NeoForge runtime repair stage router behind the runtime plugin."""

    def __init__(self, deps: NeoForgeRuntimeRepairStageWorkflowDeps) -> None:
        self.deps = deps

    def run(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        repair_port = self.deps.repair
        steps: list[AgentStep] = []
        decisions: list[AgentDecision] = []
        if execution.workspace is None:
            payload = {
                "attempted": False,
                "repair_needed": False,
                "repair_success": None,
                "reason": "Execution did not produce a workspace.",
            }
            return AgentRuntimeStageResult(success=True, steps=steps, decisions=decisions, payload=payload)
        if request.mode == "develop" and request.repair:
            return self.deps.develop_refine.run(request, execution, audit)
        payload = repair_port.run_analysis_step(
            execution.workspace,
            build_payload=execution.build_payload,
            audit_payload=audit.payload,
            repair=request.repair,
            steps=steps,
            decisions=decisions,
            max_attempts=int(request.options.get("max_iterations", 1) or 1),
        )
        stage_success = True
        if payload.get("repair_needed"):
            stage_success = bool(payload.get("repair_success"))
        return AgentRuntimeStageResult(
            success=stage_success,
            steps=steps,
            decisions=decisions,
            payload=payload,
            workspace=execution.workspace,
        )
