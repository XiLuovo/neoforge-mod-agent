from __future__ import annotations

from dataclasses import dataclass

from .agent_runtime import AgentRuntimeRequest, AgentRuntimeStageResult
from .neoforge_runtime_workflow_ports import NeoForgeRuntimeReviewPort


@dataclass(slots=True)
class NeoForgeReviewWorkflowDeps:
    review: NeoForgeRuntimeReviewPort


class NeoForgeReviewWorkflow:
    """NeoForge ModSpec review stage behind the runtime plugin."""

    def __init__(self, deps: NeoForgeReviewWorkflowDeps) -> None:
        self.deps = deps

    def run(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        review_port = self.deps.review
        spec = plan.state["spec"]
        review_step = review_port.review_spec(spec)
        return AgentRuntimeStageResult(
            success=review_step.status != "fail",
            steps=[review_step],
            decisions=[review_port.decision_from_review(review_step)],
            payload={"spec": spec.to_dict()},
        )
