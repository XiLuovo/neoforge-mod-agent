from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .agent_models import AgentDecision, AgentPromptTrace, AgentRunResult, AgentStep
from .agent_options import (
    merge_generated_files as _merge_generated_files,
    normalize_code_lane as _normalize_code_lane,
)
from .config import AppConfig
from .direct_code_agent import DirectCodeApplyResult
from .llm_planner import LLMPlanningError, PlannerArtifacts
from .models import BuildResult, ModSpec
from .modifier import WorkspaceModifier
from .patch_agent import patch_agent_artifacts, write_patch_agent_report


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


class UpdateGenerationSummaryDirectCodeFn(Protocol):
    def __call__(
        self,
        workspace: Path,
        result: DirectCodeApplyResult,
        *,
        generated_files: list[str],
    ) -> None:
        ...


@dataclass(slots=True)
class NeoForgeModifyTracePort:
    trace_from_artifacts: Callable[[str, str, PlannerArtifacts], AgentPromptTrace]
    write_agent_run: Callable[[AgentRunResult], None]
    planner_trace: PlannerTraceFn
    planner_knowledge_refs: Callable[[PlannerArtifacts | None], list[dict]]


@dataclass(slots=True)
class NeoForgeModifyReviewAuditPort:
    review_spec: Callable[[ModSpec], AgentStep]
    decision_from_review: Callable[[AgentStep], AgentDecision]
    execution_errors: Callable[[dict], list[str]]
    run_audit_step: Callable[[Path, bool, list[AgentStep], list[AgentDecision]], dict]
    audit_success: Callable[[dict], bool]


@dataclass(slots=True)
class NeoForgeModifyDirectCodePort:
    should_use_direct_code: Callable[[str, str, PlannerArtifacts | None], bool]
    execute_direct_code_lane: ExecuteDirectCodeLaneFn
    build_workspace: BuildWorkspaceFn
    finalize_direct_code_report: FinalizeDirectCodeReportFn
    update_generation_summary_direct_code: UpdateGenerationSummaryDirectCodeFn


@dataclass(slots=True)
class NeoForgeModifyRepairPort:
    run_analysis_step: RunRepairAnalysisStepFn


@dataclass(slots=True)
class NeoForgeModifyWorkflowDeps:
    config: AppConfig
    trace: NeoForgeModifyTracePort
    review_audit: NeoForgeModifyReviewAuditPort
    direct_code: NeoForgeModifyDirectCodePort
    repair: NeoForgeModifyRepairPort


class NeoForgeModifyWorkflow:
    """NeoForge-specific modify workflow behind the orchestrator facade."""

    def __init__(self, deps: NeoForgeModifyWorkflowDeps) -> None:
        self.deps = deps
        self.config = deps.config

    def run(
        self,
        workspace: Path,
        change_request: str,
        *,
        planner_mode: str = "llm",
        llm_provider: str = "mock",
        run_build: bool = False,
        run_audit: bool = True,
        repair: bool = True,
        require_llm: bool = False,
        code_lane: str = "hybrid",
        max_iterations: int = 1,
    ) -> AgentRunResult:
        deps = self.deps
        trace = deps.trace
        review_audit = deps.review_audit
        direct_code = deps.direct_code
        repair_port = deps.repair
        workspace = workspace.resolve()
        code_lane = _normalize_code_lane(code_lane)
        direct_code_requested = direct_code.should_use_direct_code(change_request, code_lane, None)
        base_run_build = run_build and not direct_code_requested
        effective_run_audit = run_audit or direct_code_requested
        steps: list[AgentStep] = [
            AgentStep(
                role="context_loader",
                status="pass",
                summary="Loaded existing workspace context.",
                details={"workspace": str(workspace)},
            )
        ]
        decisions: list[AgentDecision] = [
            AgentDecision(
                role="context_loader",
                decision="load_existing_modspec",
                rationale="Modify mode treats .agent/modspec.json as the source of truth rather than reverse-engineering generated Java.",
                inputs=[str(workspace)],
                outputs=["existing_modspec"],
            )
        ]
        prompt_traces: list[AgentPromptTrace] = []

        modifier = WorkspaceModifier(self.config)
        try:
            result = modifier.modify(
                workspace,
                change_request,
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                require_llm=require_llm,
                run_build=base_run_build,
                repair=repair,
            )
        except (LLMPlanningError, ValueError, FileNotFoundError) as exc:
            if isinstance(exc, LLMPlanningError):
                prompt_traces.append(trace.trace_from_artifacts("planner_agent", "modify_patch", exc.artifacts))
            steps.append(
                AgentStep(
                    role="planner_agent",
                    status="fail",
                    summary="Modification planning or merge failed.",
                    errors=[str(exc)],
                )
            )
            run = AgentRunResult(
                success=False,
                mode="modify",
                request=change_request,
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                workspace=workspace,
                steps=steps,
                decisions=decisions,
                prompt_traces=prompt_traces,
            )
            trace.write_agent_run(run)
            return run

        direct_code_requested = direct_code.should_use_direct_code(change_request, code_lane, result.planner_artifacts)
        effective_run_audit = run_audit or direct_code_requested
        modify_payload = {
            "success": result.success,
            "workspace": str(result.workspace),
            "modspec_path": str(result.modspec_path),
            "modify_summary_path": str(result.modify_summary_path),
            "planner_mode_used": result.planner_mode_used,
            "added": result.added,
            "updated": result.updated,
            "skipped": result.skipped,
            "warnings": result.warnings,
            "build": result.build.to_dict(),
            "code_lane": code_lane,
            "direct_code_requested": direct_code_requested,
        }
        prompt_traces.append(
            trace.planner_trace(
                role="planner_agent",
                prompt_kind="modify_patch",
                prompt=change_request,
                planner_mode=result.planner_mode_used,
                llm_provider=llm_provider,
                artifacts=result.planner_artifacts,
                spec=result.patch_spec,
            )
        )
        steps.append(
            AgentStep(
                role="planner_agent",
                status="pass",
                summary="Planned a controlled patch-agent change and merged the patch ModSpec.",
                details={
                    "added": result.added,
                    "updated": result.updated,
                    "skipped": result.skipped,
                },
                warnings=list(result.warnings),
            )
        )
        decisions.append(
            AgentDecision(
                role="planner_agent",
                decision="merge_patch",
                rationale="The planner produced a patch ModSpec and the modifier merged it into the existing project state with add/update/skip semantics.",
                inputs=["existing_modspec", "change_request"],
                outputs=[
                    f"planner_mode_used={result.planner_mode_used}",
                    f"added={len(result.added)}",
                    f"updated={len(result.updated)}",
                    f"skipped={len(result.skipped)}",
                ],
                knowledge_refs=trace.planner_knowledge_refs(result.planner_artifacts),
            )
        )

        merged_spec = ModSpec.from_dict(json.loads(result.modspec_path.read_text(encoding="utf-8")))
        review_step = review_audit.review_spec(merged_spec)
        steps.append(review_step)
        decisions.append(review_audit.decision_from_review(review_step))
        steps.append(
            AgentStep(
                role="executor_agent",
                status="pass" if result.success else "fail",
                summary="Modified workspace." if result.success else "Workspace modification failed.",
                details={"build": result.build.to_dict()},
                warnings=list(result.warnings),
                errors=[] if result.success else review_audit.execution_errors(modify_payload),
            )
        )
        decisions.append(
            AgentDecision(
                role="executor_agent",
                decision="regenerate_managed_files",
                rationale="The executor regenerated only managed files from the patch-agent plan so user-owned files in the workspace remain outside the generator's overwrite scope.",
                status="pass" if result.success else "fail",
                inputs=["merged_modspec"],
                outputs=[f"workspace={result.workspace}", f"build_attempted={result.build.attempted}"],
            )
        )

        direct_code_payload: dict[str, Any] | None = None
        direct_code_result: DirectCodeApplyResult | None = None
        if direct_code_requested:
            direct_code_result = direct_code.execute_direct_code_lane(
                result.workspace,
                change_request,
                merged_spec,
                build_result=BuildResult(attempted=False, success=None, summary="Gradle build has not run yet."),
                audit_payload=None,
                steps=steps,
                decisions=decisions,
                source="modify",
                artifacts=result.planner_artifacts,
            )
            direct_code_payload = direct_code_result.to_dict()
            if not direct_code_result.success:
                result.success = False
                modify_payload["success"] = False
            else:
                result.build = direct_code.build_workspace(result.workspace, repair=repair)
                modify_payload["build"] = result.build.to_dict()
                if result.build.success is False:
                    result.success = False
                    modify_payload["success"] = False

        audit_payload = review_audit.run_audit_step(result.workspace, effective_run_audit, steps, decisions)
        if direct_code_result is not None:
            direct_code_success = (
                direct_code_result.success
                and result.build.attempted
                and result.build.success is True
                and review_audit.audit_success(audit_payload)
            )
            direct_code.finalize_direct_code_report(
                result.workspace,
                direct_code_result,
                build=result.build,
                audit_payload=audit_payload,
                success=direct_code_success,
            )
            direct_code_payload = direct_code_result.to_dict()
        repair_payload = repair_port.run_analysis_step(
            result.workspace,
            build_payload=modify_payload.get("build", {}),
            audit_payload=audit_payload,
            repair=repair,
            steps=steps,
            decisions=decisions,
            max_attempts=max_iterations,
        )
        success = result.success and review_audit.audit_success(audit_payload)
        if direct_code_result is not None:
            success = success and direct_code_result.success and result.build.attempted and result.build.success is True
        if repair_payload.get("repair_needed") and direct_code_result is None:
            success = bool(repair_payload.get("repair_success"))

        generation_summary_path = result.workspace / ".agent" / "generation-summary.json"
        generated_files: list[str] = []
        if generation_summary_path.exists():
            try:
                generation_summary = json.loads(generation_summary_path.read_text(encoding="utf-8"))
                if isinstance(generation_summary, dict):
                    generated_files = list(generation_summary.get("generated_files", []))
            except json.JSONDecodeError:
                generated_files = []
        if direct_code_result is not None:
            generated_files = _merge_generated_files(generated_files, direct_code_result.changed_files)
            direct_code.update_generation_summary_direct_code(
                result.workspace,
                direct_code_result,
                generated_files=generated_files,
            )

        patch_artifacts = patch_agent_artifacts(result.workspace, self.config)
        patch_report_payload, patch_rollback_payload = write_patch_agent_report(
            result.workspace,
            self.config,
            workspace=result.workspace,
            artifacts=patch_artifacts,
            change_request=change_request,
            planner_mode_used=result.planner_mode_used,
            llm_provider=llm_provider,
            added=result.added,
            updated=result.updated,
            skipped=result.skipped,
            generated_files=generated_files,
            build_result=result.build,
            audit_payload=audit_payload,
            repair_payload=repair_payload,
            modify_summary_path=result.modify_summary_path,
            modspec_before_path=result.workspace / ".agent" / "modspec.before.json",
            modspec_after_path=result.workspace / ".agent" / "modspec.after.json",
            success=success,
            warnings=list(result.warnings),
        )
        modify_payload["patch_agent"] = {
            "plan_json_path": str(patch_artifacts.plan_json),
            "plan_md_path": str(patch_artifacts.plan_md),
            "report_json_path": str(patch_artifacts.report_json),
            "report_md_path": str(patch_artifacts.report_md),
            "rollback_json_path": str(patch_artifacts.rollback_json),
            "rollback_md_path": str(patch_artifacts.rollback_md),
            "status": patch_report_payload["status"],
            "rollback_status": patch_rollback_payload["status"],
            "rollback_required": patch_rollback_payload["rollback_required"],
            "managed_file_count": patch_report_payload["managed_file_count"],
            "generated_files": generated_files,
        }

        run = AgentRunResult(
            success=success,
            mode="modify",
            request=change_request,
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            workspace=result.workspace,
            steps=steps,
            decisions=decisions,
            prompt_traces=prompt_traces,
            payload={
                "modify": modify_payload,
                "audit": audit_payload,
                "repair": repair_payload,
                "patch_agent": modify_payload["patch_agent"],
                **({"direct_code": direct_code_payload} if direct_code_payload is not None else {}),
            },
        )
        trace.write_agent_run(run)
        return run
