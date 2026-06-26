"""Internal workflow ports used to assemble the NeoForge runtime plugin."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .agent_models import AgentDecision, AgentPromptTrace, AgentStep
from .agent_runtime import AgentRuntimeRequest, AgentRuntimeStageResult
from .direct_code_agent import DirectCodeApplyResult
from .llm_planner import PlannerArtifacts
from .llm_reviewer import LLMReviewResult
from .models import BuildResult, GenerationResult, ModSpec, RequestOverrides
from .planner_resolution import PlannerResolution
from .tool_calling_agent import ToolCallingRepairResult


class PlanGenerateFn(Protocol):
    def __call__(
        self,
        request: str,
        *,
        overrides: RequestOverrides,
        planner_mode: str,
        llm_provider: str,
        require_llm: bool = False,
    ) -> PlannerResolution:
        ...


class IntentContractFn(Protocol):
    def __call__(
        self,
        request_text: str,
        spec: ModSpec,
        artifacts: PlannerArtifacts | None,
        *,
        code_lane: str,
    ) -> dict[str, Any]:
        ...


class PlannerTraceFn(Protocol):
    def __call__(
        self,
        *,
        role: str,
        prompt_kind: str,
        prompt: str,
        planner_mode: str,
        llm_provider: str,
        artifacts: PlannerArtifacts | None,
        spec: ModSpec,
    ) -> AgentPromptTrace:
        ...


class ExecuteSpecFn(Protocol):
    def __call__(
        self,
        spec: ModSpec,
        *,
        workspace_name: str | None = None,
        overwrite: bool = False,
        run_build: bool = False,
        parsed_from_request: bool = False,
    ) -> GenerationResult:
        ...


class ExecuteDirectCodeLaneFn(Protocol):
    def __call__(
        self,
        workspace: Path,
        request_text: str,
        spec: ModSpec,
        *,
        build_result: BuildResult,
        audit_payload: dict[str, Any] | None,
        steps: list[AgentStep],
        decisions: list[AgentDecision],
        source: str,
        artifacts: PlannerArtifacts | None,
    ) -> DirectCodeApplyResult:
        ...


class BuildWorkspaceFn(Protocol):
    def __call__(self, workspace: Path, *, repair: bool) -> BuildResult:
        ...


class FinalizeDirectCodeReportFn(Protocol):
    def __call__(
        self,
        workspace: Path,
        result: DirectCodeApplyResult,
        *,
        build: BuildResult,
        audit_payload: dict[str, Any],
        success: bool,
    ) -> DirectCodeApplyResult:
        ...


class UpdateGenerationSummaryDirectCodeFn(Protocol):
    def __call__(
        self,
        workspace: Path,
        result: DirectCodeApplyResult,
        *,
        generated_files: list[str],
    ) -> None:
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


class RunReviewerFn(Protocol):
    def __call__(
        self,
        *,
        workspace: Path | None,
        user_goal: str,
        llm_provider: str,
        review_stage: str,
        intent_contract: dict[str, Any] | None,
        modspec: dict[str, Any] | None,
        rag: dict[str, Any] | None,
        tool_call_trace: list[dict[str, Any]] | None,
        changed_files: list[str] | None,
        audit_result: dict[str, Any] | None,
        build_result: dict[str, Any] | None,
        steps: list[AgentStep],
        decisions: list[AgentDecision],
        prior_reviewer_observation: dict[str, Any] | None = None,
    ) -> LLMReviewResult:
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


class RunRepairAnalysisStepFn(Protocol):
    def __call__(
        self,
        workspace: Path,
        *,
        build_payload: dict,
        audit_payload: dict,
        repair: bool,
        steps: list[AgentStep],
        decisions: list[AgentDecision],
        max_attempts: int = 1,
    ) -> dict:
        ...


class RunDevelopRefineWorkflowFn(Protocol):
    def __call__(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        ...


@dataclass(slots=True)
class NeoForgeRuntimePlanningPort:
    plan_generate: PlanGenerateFn
    trace_from_artifacts: Callable[[str, str, PlannerArtifacts], AgentPromptTrace]
    intent_contract: IntentContractFn
    planner_knowledge_refs: Callable[[PlannerArtifacts | None], list[dict]]
    planner_trace: PlannerTraceFn


@dataclass(slots=True)
class NeoForgeRuntimeReviewPort:
    review_spec: Callable[[ModSpec], AgentStep]
    decision_from_review: Callable[[AgentStep], AgentDecision]


@dataclass(slots=True)
class NeoForgeRuntimeExecutionPort:
    execute_spec: ExecuteSpecFn
    execution_errors: Callable[[dict], list[str]]


@dataclass(slots=True)
class NeoForgeRuntimeAuditPort:
    run_audit_step: RunAuditStepFn
    audit_success: Callable[[dict], bool]


@dataclass(slots=True)
class NeoForgeRuntimeDirectCodePort:
    should_use_direct_code: Callable[[str, str, PlannerArtifacts | None], bool]
    execute_direct_code_lane: ExecuteDirectCodeLaneFn
    build_workspace: BuildWorkspaceFn
    finalize_direct_code_report: FinalizeDirectCodeReportFn
    update_generation_summary_direct_code: UpdateGenerationSummaryDirectCodeFn


@dataclass(slots=True)
class NeoForgeRuntimeRepairPort:
    repair_root_causes: Callable[[dict, dict], list[str]]
    repair_plan_actions: Callable[[dict, dict, list[str]], list[dict[str, str]]]
    run_reviewer: RunReviewerFn
    run_tool_calling_repair: RunToolCallingRepairFn
    repair_knowledge_refs: Callable[[dict], list[dict]]
    changed_files_from_repair_payload: Callable[[dict[str, Any]], list[str]]
    run_analysis_step: RunRepairAnalysisStepFn


@dataclass(slots=True)
class NeoForgeRuntimeDevelopRefinePort:
    run: RunDevelopRefineWorkflowFn
