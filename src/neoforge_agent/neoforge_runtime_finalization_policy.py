from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent_runtime import AgentRuntimeRequest, AgentRuntimeStageResult
from .direct_code_agent import DirectCodeApplyResult
from .neoforge_runtime_workflow_ports import NeoForgeRuntimeAuditPort


@dataclass(slots=True)
class NeoForgeRuntimeFinalizationPolicyDeps:
    domain_name: str
    domain_spec_metadata: dict[str, Any]
    audit: NeoForgeRuntimeAuditPort


class NeoForgeRuntimeFinalizationPolicy:
    """NeoForge runtime final success and payload policy."""

    def __init__(self, deps: NeoForgeRuntimeFinalizationPolicyDeps) -> None:
        self.deps = deps

    def final_success(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> bool:
        success = execution.success and self.deps.audit.audit_success(audit.payload)
        direct_code_result = execution.state.get("direct_code") if isinstance(execution.state, dict) else None
        if isinstance(direct_code_result, DirectCodeApplyResult):
            success = success and direct_code_result.success
        if request.mode == "develop" and repair.payload.get("attempted"):
            success = success and bool(repair.payload.get("success"))
        if repair.payload.get("repair_needed") and not isinstance(direct_code_result, DirectCodeApplyResult):
            success = bool(repair.payload.get("repair_success"))
        return success

    def final_payload(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> dict[str, Any]:
        return {
            "runtime": {
                "domain": self.deps.domain_name,
                "domain_spec": self.deps.domain_spec_metadata,
                "stages": ["planner", "reviewer", "executor", "auditor", "repair"],
            },
            "generation": execution.payload,
            "audit": audit.payload,
            "repair": repair.payload,
        }

    def review_failure_payload(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
    ) -> dict[str, Any]:
        return {
            "runtime": {
                "domain": self.deps.domain_name,
                "failed_stage": "reviewer",
            },
            "spec": plan.payload.get("spec"),
            "review": review.payload,
        }
