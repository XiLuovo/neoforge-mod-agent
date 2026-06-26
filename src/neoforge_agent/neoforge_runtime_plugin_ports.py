"""Public plugin-facing ports for the NeoForge agent runtime seam."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .agent_runtime import AgentRuntimeRequest, AgentRuntimeStageResult


class RunGenerateExecutionWorkflowFn(Protocol):
    def __call__(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        ...


class RunAuditWorkflowFn(Protocol):
    def __call__(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        ...


class RunPlanningWorkflowFn(Protocol):
    def __call__(
        self,
        request: AgentRuntimeRequest,
    ) -> AgentRuntimeStageResult:
        ...


class RunRepairStageWorkflowFn(Protocol):
    def __call__(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        ...


class RunReviewWorkflowFn(Protocol):
    def __call__(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        ...


class FinalSuccessPolicyFn(Protocol):
    def __call__(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> bool:
        ...


class FinalPayloadPolicyFn(Protocol):
    def __call__(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> dict[str, Any]:
        ...


class ReviewFailurePayloadPolicyFn(Protocol):
    def __call__(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
    ) -> dict[str, Any]:
        ...


@dataclass(slots=True)
class NeoForgeRuntimeGenerateExecutionPort:
    run: RunGenerateExecutionWorkflowFn


@dataclass(slots=True)
class NeoForgeRuntimeAuditWorkflowPort:
    run: RunAuditWorkflowFn


@dataclass(slots=True)
class NeoForgeRuntimePlanningWorkflowPort:
    run: RunPlanningWorkflowFn


@dataclass(slots=True)
class NeoForgeRuntimeRepairStagePort:
    run: RunRepairStageWorkflowFn


@dataclass(slots=True)
class NeoForgeRuntimeReviewWorkflowPort:
    run: RunReviewWorkflowFn


@dataclass(slots=True)
class NeoForgeRuntimeFinalizationPort:
    final_success: FinalSuccessPolicyFn
    final_payload: FinalPayloadPolicyFn
    review_failure_payload: ReviewFailurePayloadPolicyFn


@dataclass(slots=True)
class NeoForgeRuntimePluginDeps:
    planning_workflow: NeoForgeRuntimePlanningWorkflowPort
    review_workflow: NeoForgeRuntimeReviewWorkflowPort
    generate_execution: NeoForgeRuntimeGenerateExecutionPort
    audit_workflow: NeoForgeRuntimeAuditWorkflowPort
    repair_stage: NeoForgeRuntimeRepairStagePort
    finalization: NeoForgeRuntimeFinalizationPort
