from __future__ import annotations

from typing import Any

from .agent_runtime import AgentRuntimeRequest, AgentRuntimeStageResult
from .domain_spec import NeoForgeModSpecPlugin
from .neoforge_runtime_plugin_ports import NeoForgeRuntimePluginDeps


class NeoForgeRuntimePlugin:
    """NeoForge domain adapter for the generic agent runtime."""

    domain_name = "neoforge"
    domain_spec_plugin = NeoForgeModSpecPlugin()

    def __init__(self, deps: NeoForgeRuntimePluginDeps) -> None:
        self.deps = deps

    def plan_generate(self, request: AgentRuntimeRequest) -> AgentRuntimeStageResult:
        return self.deps.planning_workflow.run(request)

    def review(self, request: AgentRuntimeRequest, plan: AgentRuntimeStageResult) -> AgentRuntimeStageResult:
        return self.deps.review_workflow.run(request, plan)

    def execute_generate(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        return self.deps.generate_execution.run(request, plan, review)

    def audit(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        return self.deps.audit_workflow.run(request, plan, execution)

    def repair(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        return self.deps.repair_stage.run(request, execution, audit)

    def final_success(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> bool:
        return self.deps.finalization.final_success(request, execution, audit, repair)

    def final_payload(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> dict[str, Any]:
        return self.deps.finalization.final_payload(request, plan, review, execution, audit, repair)

    def review_failure_payload(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
    ) -> dict[str, Any]:
        return self.deps.finalization.review_failure_payload(request, plan, review)
