from __future__ import annotations

from dataclasses import dataclass

from .agent_models import AgentDecision, AgentStep
from .agent_options import (
    merge_generated_files as _merge_generated_files,
    normalize_code_lane as _normalize_code_lane,
)
from .agent_runtime import AgentRuntimeRequest, AgentRuntimeStageResult
from .config import AppConfig
from .direct_code_agent import DirectCodeApplyResult
from .llm_planner import write_planner_artifacts
from .models import BuildResult
from .neoforge_runtime_workflow_ports import (
    NeoForgeRuntimeDirectCodePort,
    NeoForgeRuntimeExecutionPort,
)
from .tools import write_generation_summary


@dataclass(slots=True)
class NeoForgeGenerateExecutionWorkflowDeps:
    config: AppConfig
    domain_name: str
    execution: NeoForgeRuntimeExecutionPort
    direct_code: NeoForgeRuntimeDirectCodePort


class NeoForgeGenerateExecutionWorkflow:
    """NeoForge generate/develop execution stage behind the runtime plugin."""

    def __init__(self, deps: NeoForgeGenerateExecutionWorkflowDeps) -> None:
        self.deps = deps

    def run(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        spec = plan.state["spec"]
        artifacts = plan.state.get("artifacts")
        planner_warnings = list(plan.state.get("planner_warnings") or [])
        planner_mode_used = plan.planner_mode_used or request.planner_mode
        code_lane = _normalize_code_lane(str(request.options.get("code_lane", "hybrid")))
        execution = self.deps.execution
        direct_code = self.deps.direct_code
        direct_code_requested = direct_code.should_use_direct_code(request.request, code_lane, artifacts)
        result = execution.execute_spec(
            spec,
            workspace_name=request.options.get("workspace_name"),
            overwrite=bool(request.options.get("overwrite")),
            run_build=request.run_build and not direct_code_requested,
            parsed_from_request=True,
        )
        if artifacts is not None:
            artifacts.planner_mode = f"agent:{planner_mode_used}"
            write_planner_artifacts(result.workspace_dir, self.deps.config, artifacts)
        if planner_warnings:
            result.warnings = [*planner_warnings, *result.warnings]
            write_generation_summary(result.workspace_dir, self.deps.config, result.to_dict())

        extra_steps: list[AgentStep] = []
        extra_decisions: list[AgentDecision] = []
        direct_code_result: DirectCodeApplyResult | None = None
        if direct_code_requested and result.validation.is_valid:
            direct_code_result = direct_code.execute_direct_code_lane(
                result.workspace_dir,
                request.request,
                spec,
                build_result=BuildResult(attempted=False, success=None, summary="Gradle build has not run yet."),
                audit_payload=None,
                steps=extra_steps,
                decisions=extra_decisions,
                source="generate",
                artifacts=artifacts,
            )
            if direct_code_result.success:
                result.generated_files = _merge_generated_files(
                    result.generated_files,
                    direct_code_result.changed_files,
                )
                result.build = direct_code.build_workspace(result.workspace_dir, repair=request.repair)
            else:
                result.warnings = [*result.warnings, *direct_code_result.errors]
            direct_code.update_generation_summary_direct_code(
                result.workspace_dir,
                direct_code_result,
                generated_files=result.generated_files,
            )

        execution_payload = result.to_dict()
        if direct_code_result is not None:
            execution_payload["direct_code"] = direct_code_result.to_dict()
        execution_success = result.succeeded and (direct_code_result.success if direct_code_result is not None else True)
        return AgentRuntimeStageResult(
            success=execution_success,
            state={
                "generation": result,
                "direct_code": direct_code_result,
                "spec": spec,
                "intent_contract": plan.state.get("intent_contract") if isinstance(plan.state, dict) else None,
                "planner_artifacts": artifacts,
            },
            workspace=result.workspace_dir,
            payload=execution_payload,
            build_payload=execution_payload.get("build", {}),
            steps=[
                AgentStep(
                    role="executor_agent",
                    status="pass" if execution_success else "fail",
                    summary="Generated workspace." if result.succeeded else "Workspace generation failed.",
                    details={
                        "domain": self.deps.domain_name,
                        "workspace": str(result.workspace_dir),
                        "generated_files": list(result.generated_files),
                        "build": result.build.to_dict(),
                        "code_lane": code_lane,
                        "direct_code": direct_code_result.to_dict() if direct_code_result is not None else None,
                    },
                    warnings=list(result.warnings),
                    errors=[] if execution_success else execution.execution_errors(execution_payload),
                )
            ]
            + extra_steps,
            decisions=[
                AgentDecision(
                    role="executor_agent",
                    decision="generate_workspace",
                    rationale="The NeoForge executor plugin used deterministic generators to materialize Java, resources, data JSON, and agent metadata from the reviewed ModSpec.",
                    status="pass" if execution_success else "fail",
                    inputs=["reviewed_modspec"],
                    outputs=[
                        f"workspace={result.workspace_dir}",
                        f"generated_files={len(result.generated_files)}",
                        f"direct_code={direct_code_result is not None}",
                    ],
                )
            ]
            + extra_decisions,
        )
