from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_models import AgentDecision, AgentPromptTrace, AgentRunResult, AgentStep
from .agent_runtime import AgentRuntime, AgentRuntimeRequest, AgentRuntimeStageResult, AgentTraceWriter
from .auditor import WorkspaceAuditor
from .config import AppConfig
from .direct_code_agent import DirectCodeAgent, DirectCodeApplyResult, DirectCodeChange, DirectCodePlan
from .domain_spec import NeoForgeModSpecPlugin
from .llm_client import check_llm_provider_health, create_llm_client
from .llm_planner import LLMPlanningError, PlannerArtifacts, plan_with_llm, write_planner_artifacts
from .modifier import WorkspaceModifier
from .models import BuildResult, ModSpec, RequestOverrides
from .planner import ModProjectPlanner
from .patch_agent import patch_agent_artifacts, write_patch_agent_report
from .repair_loop import AutoRepairRunner
from .repair_rag import RepairRAGAdvisor
from .tools import ensure_directory, slugify_mod_id, write_generation_summary, write_json, write_text
from .validator import validate_mod_spec


class AgentOrchestrator:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()
        self.planner = ModProjectPlanner(self.config)
        self.auditor = WorkspaceAuditor(self.config)
        self.repair_runner = AutoRepairRunner(self.config)
        self.repair_rag_advisor = RepairRAGAdvisor(self.config)
        self.direct_code_agent = DirectCodeAgent(self.config)
        self.trace_writer = AgentTraceWriter(self.config)
        self.runtime = AgentRuntime(NeoForgeRuntimePlugin(self), self.trace_writer)

    def run_generate(
        self,
        request: str,
        *,
        overrides: RequestOverrides | None = None,
        planner_mode: str = "llm",
        llm_provider: str = "mock",
        workspace_name: str | None = None,
        overwrite: bool = False,
        run_build: bool = False,
        run_audit: bool = True,
        repair: bool = True,
        require_llm: bool = False,
        code_lane: str = "hybrid",
    ) -> AgentRunResult:
        return self.runtime.run_generate(
            AgentRuntimeRequest(
                mode="generate",
                request=request,
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                run_build=run_build,
                run_audit=run_audit,
                repair=repair,
                options={
                    "overrides": overrides or RequestOverrides(),
                    "workspace_name": workspace_name,
                    "overwrite": overwrite,
                    "require_llm": require_llm,
                    "code_lane": code_lane,
                },
            )
        )

    def run_modify(
        self,
        workspace: Path,
        change_request: str,
        *,
        planner_mode: str = "llm",
        llm_provider: str = "mock",
        run_build: bool = False,
        run_audit: bool = True,
        repair: bool = True,
        code_lane: str = "hybrid",
    ) -> AgentRunResult:
        workspace = workspace.resolve()
        code_lane = _normalize_code_lane(code_lane)
        direct_code_requested = self._direct_code_requested(change_request, code_lane, None)
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
                run_build=base_run_build,
                repair=repair,
            )
        except (LLMPlanningError, ValueError, FileNotFoundError) as exc:
            if isinstance(exc, LLMPlanningError):
                prompt_traces.append(self._trace_from_artifacts("planner_agent", "modify_patch", exc.artifacts))
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
            self._write_agent_run(run)
            return run

        direct_code_requested = self._direct_code_requested(change_request, code_lane, result.planner_artifacts)
        effective_run_audit = run_audit or direct_code_requested
        modify_payload = {
            "success": result.success,
            "workspace": str(result.workspace),
            "modspec_path": str(result.modspec_path),
            "modify_summary_path": str(result.modify_summary_path),
            "added": result.added,
            "updated": result.updated,
            "skipped": result.skipped,
            "warnings": result.warnings,
            "build": result.build.to_dict(),
            "code_lane": code_lane,
            "direct_code_requested": direct_code_requested,
        }
        prompt_traces.append(
            self._planner_trace(
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
                knowledge_refs=self._knowledge_refs_from_planner_artifacts(result.planner_artifacts),
            )
        )

        merged_spec = ModSpec.from_dict(json.loads(result.modspec_path.read_text(encoding="utf-8")))
        review_step = self._review_spec(merged_spec)
        steps.append(review_step)
        decisions.append(self._decision_from_review(review_step))
        steps.append(
            AgentStep(
                role="executor_agent",
                status="pass" if result.success else "fail",
                summary="Modified workspace." if result.success else "Workspace modification failed.",
                details={"build": result.build.to_dict()},
                warnings=list(result.warnings),
                errors=[] if result.success else self._execution_errors(modify_payload),
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
            direct_code_result = self._execute_direct_code_lane(
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
                result.build = self.planner.builder.build(result.workspace, repair=repair)
                modify_payload["build"] = result.build.to_dict()
                if result.build.success is False:
                    result.success = False
                    modify_payload["success"] = False

        audit_payload = self._run_audit_step(result.workspace, effective_run_audit, steps, decisions)
        if direct_code_result is not None:
            direct_code_success = (
                direct_code_result.success
                and result.build.attempted
                and result.build.success is True
                and self._audit_success(audit_payload)
            )
            self.direct_code_agent.finalize_report(
                result.workspace,
                direct_code_result,
                build=result.build,
                audit_payload=audit_payload,
                success=direct_code_success,
            )
            direct_code_payload = direct_code_result.to_dict()
        repair_payload = self._run_repair_analysis_step(
            result.workspace,
            build_payload=modify_payload.get("build", {}),
            audit_payload=audit_payload,
            repair=repair,
            steps=steps,
            decisions=decisions,
        )
        success = result.success and self._audit_success(audit_payload)
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
            self._update_generation_summary_direct_code(
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
        self._write_agent_run(run)
        return run

    def _plan_generate(
        self,
        request: str,
        *,
        overrides: RequestOverrides,
        planner_mode: str,
        llm_provider: str,
        require_llm: bool = False,
    ) -> tuple[ModSpec, PlannerArtifacts | None, list[str], str]:
        if planner_mode == "rules":
            return self._apply_overrides(self.planner.parse_request(request, overrides=overrides), overrides), None, [], "rules"

        if planner_mode == "llm":
            health = check_llm_provider_health(llm_provider)
            if llm_provider == "openai-compatible" and not health.healthy:
                if require_llm:
                    raise ValueError(
                        "LLM planner is required but provider health check failed: "
                        + "; ".join([*health.errors, *health.warnings])
                    )
                spec = self._apply_overrides(self.planner.parse_request(request, overrides=overrides), overrides)
                warnings = [
                    "LLM provider health check failed; planner fell back to rules.",
                    *health.errors,
                    *health.warnings,
                ]
                return spec, None, warnings, "llm->rules"
            try:
                client = create_llm_client(llm_provider, self.config.project_root)
                spec, artifacts = plan_with_llm(request, client, config=self.config)
                self._apply_overrides(spec, overrides)
                return spec, artifacts, list(artifacts.warnings), "llm"
            except (LLMPlanningError, ValueError, RuntimeError) as exc:
                if require_llm:
                    if isinstance(exc, LLMPlanningError):
                        raise
                    raise ValueError(f"LLM planner is required but failed: {exc}") from exc
                spec = self._apply_overrides(self.planner.parse_request(request, overrides=overrides), overrides)
                artifacts = exc.artifacts if isinstance(exc, LLMPlanningError) else None
                warnings = [f"LLM planner failed; fallback to rules: {exc}"]
                if artifacts is not None:
                    warnings.extend(artifacts.warnings)
                return spec, artifacts, warnings, "llm->rules"

        rules_spec = self.planner.parse_request(request, overrides=overrides)
        if rules_spec.all_content() or rules_spec.entities or rules_spec.recipes:
            return rules_spec, None, [], "auto->rules"

        health = check_llm_provider_health(llm_provider)
        if llm_provider == "openai-compatible" and not health.healthy:
            warnings = [
                "Auto planner kept rules output because LLM provider health check failed.",
                *health.errors,
                *health.warnings,
            ]
            return self._apply_overrides(rules_spec, overrides), None, warnings, "auto->rules"
        try:
            client = create_llm_client(llm_provider, self.config.project_root)
            spec, artifacts = plan_with_llm(request, client, config=self.config)
            self._apply_overrides(spec, overrides)
            warnings = [*artifacts.warnings, "Auto planner used LLM because rules planning returned no content."]
            return spec, artifacts, warnings, "auto->llm"
        except (LLMPlanningError, ValueError, RuntimeError) as exc:
            artifacts = exc.artifacts if isinstance(exc, LLMPlanningError) else None
            warnings = [f"Auto planner fallback to rules after LLM failure: {exc}"]
            if artifacts is not None:
                warnings.extend(artifacts.warnings)
            return self._apply_overrides(rules_spec, overrides), artifacts, warnings, "auto->rules"

    def _apply_overrides(self, spec: ModSpec, overrides: RequestOverrides) -> ModSpec:
        if overrides.mod_id:
            spec.mod_id = slugify_mod_id(overrides.mod_id)
        if overrides.display_name:
            spec.display_name = overrides.display_name
        if overrides.package_name:
            spec.package_name = overrides.package_name
        if overrides.version:
            spec.version = overrides.version
        if overrides.authors:
            spec.authors = list(overrides.authors)
        if overrides.license_name:
            spec.license_name = overrides.license_name
        if overrides.description:
            spec.description = overrides.description
        return spec

    def _review_spec(self, spec: ModSpec) -> AgentStep:
        report = validate_mod_spec(spec, self.config)
        warnings = [issue.message for issue in report.warnings]
        errors = [issue.message for issue in report.errors]
        feature_count = len(list(spec.iter_features()))
        if feature_count == 0:
            warnings.append("ModSpec has no generated content features.")
        review_checks = self._review_checks(spec, feature_count, len(report.errors), len(report.warnings))
        return AgentStep(
            role="reviewer_agent",
            status="pass" if report.is_valid else "fail",
            summary=f"Reviewed ModSpec with {feature_count} feature(s).",
            details={
                "approved": report.is_valid,
                "feature_count": feature_count,
                "review_checks": review_checks,
                "validation": report.to_dict(),
            },
            warnings=warnings,
            errors=errors,
        )

    def _review_checks(
        self,
        spec: ModSpec,
        feature_count: int,
        errors_count: int,
        warnings_count: int,
    ) -> list[dict[str, str]]:
        has_supported_content = bool(spec.all_content() or spec.entities or spec.recipes)
        return [
            {
                "id": "modspec_schema_boundary",
                "status": "pass",
                "summary": "Planner output is a ModSpec object; Java, Gradle, assets, and datapack files remain deterministic generator outputs.",
            },
            {
                "id": "feature_presence",
                "status": "pass" if feature_count > 0 else "warning",
                "summary": f"Reviewed {feature_count} generated feature declaration(s).",
            },
            {
                "id": "validator_errors",
                "status": "pass" if errors_count == 0 else "fail",
                "summary": f"Validator reported {errors_count} error(s).",
            },
            {
                "id": "validator_warnings",
                "status": "pass" if warnings_count == 0 else "warning",
                "summary": f"Validator reported {warnings_count} warning(s).",
            },
            {
                "id": "content_coverage_hint",
                "status": "pass" if has_supported_content else "warning",
                "summary": "Spec contains generator-supported content declarations." if has_supported_content else "Spec has no supported content declarations to execute.",
            },
        ]

    def _run_audit_step(
        self,
        workspace: Path,
        run_audit: bool,
        steps: list[AgentStep],
        decisions: list[AgentDecision],
    ) -> dict:
        if not run_audit:
            payload = {"attempted": False, "success": None}
            steps.append(
                AgentStep(
                    role="auditor_agent",
                    status="skip",
                    summary="Audit was not requested.",
                    details=payload,
                )
            )
            decisions.append(
                AgentDecision(
                    role="auditor_agent",
                    decision="skip_audit",
                    rationale="The caller disabled workspace audit for this agent run.",
                    status="skip",
                    inputs=[str(workspace)],
                    outputs=[],
                )
            )
            return payload

        try:
            result = self.auditor.audit_workspace(workspace)
        except FileNotFoundError as exc:
            payload = {"attempted": True, "success": False, "error": str(exc)}
            steps.append(
                AgentStep(
                    role="auditor_agent",
                    status="fail",
                    summary="Audit failed before report generation.",
                    details=payload,
                    errors=[str(exc)],
                )
            )
            decisions.append(
                AgentDecision(
                    role="auditor_agent",
                    decision="audit_workspace",
                    rationale="The auditor could not load required workspace metadata before running structural checks.",
                    status="fail",
                    inputs=[str(workspace)],
                    outputs=[str(exc)],
                )
            )
            return payload

        payload = result.to_dict()
        payload["attempted"] = True
        steps.append(
            AgentStep(
                role="auditor_agent",
                status="pass" if result.success else "fail",
                summary="Workspace audit passed." if result.success else "Workspace audit found issues.",
                details={
                    "audit_report_path": result.audit_report_path,
                    "errors_count": len(result.errors),
                    "warnings_count": len(result.warnings),
                    "checks_count": len(result.checks),
                },
                warnings=[issue.message for issue in result.warnings],
                errors=[issue.message for issue in result.errors],
            )
        )
        decisions.append(
            AgentDecision(
                role="auditor_agent",
                decision="audit_workspace",
                rationale="The auditor compared generated files and references against ModSpec and generation-summary artifacts.",
                status="pass" if result.success else "fail",
                inputs=["workspace", ".agent/modspec.json", ".agent/generation-summary.json"],
                outputs=[
                    f"errors={len(result.errors)}",
                    f"warnings={len(result.warnings)}",
                    f"checks={len(result.checks)}",
                ],
            )
        )
        return payload

    def _run_repair_analysis_step(
        self,
        workspace: Path,
        *,
        build_payload: dict,
        audit_payload: dict,
        repair: bool,
        steps: list[AgentStep],
        decisions: list[AgentDecision],
    ) -> dict:
        build_failed = build_payload.get("attempted") and build_payload.get("success") is False
        audit_failed = audit_payload.get("attempted") and audit_payload.get("success") is False
        repair_needed = bool(build_failed or audit_failed)

        payload = {
            "attempted": repair and repair_needed,
            "repair_needed": repair_needed,
            "repair_executed": False,
            "repair_success": None,
            "debug_context_path": build_payload.get("debug_context_path"),
            "fix_request_path": build_payload.get("fix_request_path"),
            "suspected_errors_path": build_payload.get("suspected_errors_path"),
            "audit_report_path": audit_payload.get("audit_report_path"),
            "root_causes": self._repair_root_causes(build_payload, audit_payload),
        }
        payload["repair_plan"] = self._repair_plan_actions(build_payload, audit_payload, payload["root_causes"])
        if repair_needed:
            payload["repair_rag"] = self._repair_rag_advice(
                workspace,
                root_causes=payload["root_causes"],
                repair_plan=payload["repair_plan"],
                build_payload=build_payload,
                audit_payload=audit_payload,
            )
        else:
            payload["repair_rag"] = RepairRAGAdvisor.skipped("No repair needed.").to_dict()

        if not repair_needed:
            steps.append(
                AgentStep(
                    role="repair_agent",
                    status="skip",
                    summary="No repair analysis needed.",
                    details=payload,
                )
            )
            decisions.append(
                AgentDecision(
                    role="repair_agent",
                    decision="skip_repair",
                    rationale="Build and audit did not report failing checks, so no repair context was needed.",
                    status="skip",
                    inputs=["build_result", "audit_result"],
                    outputs=[],
                )
            )
            return payload

        if repair:
            repair_loop_result = self.repair_runner.run(
                workspace,
                max_attempts=1,
                run_build=bool(build_payload.get("attempted")),
                run_audit=bool(audit_payload.get("attempted")),
            )
            payload["repair_executed"] = True
            payload["repair_success"] = repair_loop_result.success
            payload["repair_loop"] = repair_loop_result.to_dict()
            payload["repair_loop_report_json_path"] = str(repair_loop_result.repair_loop_report_json_path)
            payload["repair_loop_report_md_path"] = str(repair_loop_result.repair_loop_report_md_path)

        status = "pass" if payload.get("repair_success") else "skip"
        if repair:
            status = "pass" if payload.get("repair_success") else "fail"
        summary = (
            "Executed safe repair loop and checks now pass."
            if payload.get("repair_success")
            else "Safe repair loop ran but checks still fail."
            if repair
            else "Repair analysis was not requested."
        )
        steps.append(
            AgentStep(
                role="repair_agent",
                status=status,
                summary=summary,
                details=payload,
                errors=[] if payload.get("repair_success") else list(payload["root_causes"]),
            )
        )
        decisions.append(
            AgentDecision(
                role="repair_agent",
                decision="execute_safe_repair_loop" if repair else "skip_repair_context",
                rationale=(
                    "The repair agent regenerated only managed files from .agent/modspec.json and reran the requested checks."
                    if repair
                    else "Repair was disabled, so the agent only reported the repair plan."
                ),
                status=status,
                inputs=["build_result", "audit_result"],
                outputs=[
                    f"root_causes={len(payload['root_causes'])}",
                    f"repair_actions={len(payload['repair_plan'])}",
                    f"repair_rag_hits={payload.get('repair_rag', {}).get('hits_count', 0)}",
                    f"repair_success={payload.get('repair_success')}",
                ],
                knowledge_refs=self._knowledge_refs_from_repair_rag(payload.get("repair_rag") or {}),
            )
        )
        if repair:
            self._write_repair_plan(workspace, payload)
        return payload

    def _knowledge_refs_from_planner_artifacts(self, artifacts: PlannerArtifacts | None) -> list[dict]:
        if artifacts is None:
            return []
        return _normalize_knowledge_refs(
            artifacts.used_knowledge,
            reason="Planner retrieved this knowledge before producing the ModSpec decision.",
        )

    def _knowledge_refs_from_repair_rag(self, repair_rag: dict) -> list[dict]:
        hits = repair_rag.get("hits") if isinstance(repair_rag, dict) else []
        return _normalize_knowledge_refs(
            hits if isinstance(hits, list) else [],
            reason="Repair RAG retrieved this knowledge to explain the repair decision.",
        )

    def _intent_contract(
        self,
        request_text: str,
        spec: ModSpec,
        artifacts: PlannerArtifacts | None,
        *,
        code_lane: str,
    ) -> dict[str, Any]:
        raw = artifacts.raw_json if artifacts is not None and isinstance(artifacts.raw_json, dict) else {}
        normalized = (
            artifacts.normalized_json
            if artifacts is not None and isinstance(artifacts.normalized_json, dict)
            else {}
        )
        direct_plan = normalized.get("direct_code_plan") if isinstance(normalized.get("direct_code_plan"), dict) else raw.get("direct_code_plan")
        routing_decision = normalized.get("routing_decision") if isinstance(normalized.get("routing_decision"), dict) else raw.get("routing_decision")
        lane = _normalize_code_lane(code_lane)
        return {
            "modspec": spec.to_dict(),
            "direct_code_plan": direct_plan if isinstance(direct_plan, dict) else None,
            "routing_decision": routing_decision if isinstance(routing_decision, dict) else {
                "lane": lane,
                "reason": "Selected by --code-lane or ModSpec-first default routing.",
            },
            "requires_direct_code": self._direct_code_requested(request_text, lane, artifacts),
            "code_lane": lane,
        }

    def _planner_trace(
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
        if artifacts is not None:
            return self._trace_from_artifacts(role, prompt_kind, artifacts)
        return AgentPromptTrace(
            role=role,
            planner_mode=planner_mode,
            provider="rules" if "rules" in planner_mode else llm_provider,
            prompt_kind=prompt_kind,
            input_text=prompt,
            normalized_json=spec.to_dict(),
        )

    def _trace_from_artifacts(
        self,
        role: str,
        prompt_kind: str,
        artifacts: PlannerArtifacts,
    ) -> AgentPromptTrace:
        return AgentPromptTrace(
            role=role,
            planner_mode=artifacts.planner_mode,
            provider=artifacts.provider,
            prompt_kind=prompt_kind,
            system_prompt=artifacts.system_prompt,
            input_text=artifacts.input_text,
            raw_text=artifacts.raw_text,
            raw_json=artifacts.raw_json,
            normalized_json=artifacts.normalized_json,
            warnings=list(artifacts.warnings),
            error=artifacts.error,
            rag_query=artifacts.rag_query,
            rag_query_expansions=list(artifacts.rag_query_expansions),
            rag_hits=list(artifacts.rag_hits),
            rag_categories=dict(artifacts.rag_categories),
            rag_capabilities=dict(artifacts.rag_capabilities),
            used_knowledge=list(artifacts.used_knowledge),
            rag_quality=dict(artifacts.rag_quality),
            parse_attempts=list(artifacts.parse_attempts),
            retry_attempts=artifacts.retry_attempts,
            schema_retry_attempts=artifacts.schema_retry_attempts,
            schema_validation_attempts=list(artifacts.schema_validation_attempts),
            json_repair_applied=artifacts.json_repair_applied,
            provider_config=dict(artifacts.provider_config),
            provider_health=dict(artifacts.provider_health),
            provider_metadata=dict(artifacts.provider_metadata),
            completion_usage=dict(artifacts.completion_usage),
            completion_attempts=list(artifacts.completion_attempts),
        )

    def _decision_from_review(self, step: AgentStep) -> AgentDecision:
        approved = bool(step.details.get("approved"))
        return AgentDecision(
            role="reviewer_agent",
            decision="approve_modspec" if approved else "reject_modspec",
            rationale="The reviewer agent runs deterministic ModSpec validation before any generated workspace is trusted.",
            status=step.status,
            inputs=["planned_modspec"],
            outputs=[
                f"approved={str(approved).lower()}",
                f"errors={len(step.errors)}",
                f"warnings={len(step.warnings)}",
            ],
        )

    def _repair_root_causes(self, build_payload: dict, audit_payload: dict) -> list[str]:
        causes: list[str] = []
        if build_payload.get("attempted") and build_payload.get("success") is False:
            issues = build_payload.get("issues") or []
            if issues:
                causes.extend(str(issue.get("message", "Build issue")) for issue in issues if isinstance(issue, dict))
            else:
                causes.append(str(build_payload.get("summary", "Build failed.")))
        if audit_payload.get("attempted") and audit_payload.get("success") is False:
            errors = audit_payload.get("errors") or []
            if errors:
                causes.extend(str(error.get("message", "Audit issue")) for error in errors if isinstance(error, dict))
            elif audit_payload.get("error"):
                causes.append(str(audit_payload["error"]))
        return causes

    def _repair_plan_actions(self, build_payload: dict, audit_payload: dict, root_causes: list[str]) -> list[dict[str, str]]:
        actions: list[dict[str, str]] = []
        if build_payload.get("attempted") and build_payload.get("success") is False:
            actions.append(
                {
                    "id": "inspect_build_logs",
                    "summary": "Open Gradle stdout/stderr and suspected-errors artifacts, then map compiler or data errors back to the owning ModSpec feature.",
                    "artifact": str(build_payload.get("suspected_errors_path") or build_payload.get("stdout_path") or ""),
                }
            )
        if audit_payload.get("attempted") and audit_payload.get("success") is False:
            actions.append(
                {
                    "id": "inspect_audit_report",
                    "summary": "Read audit-report.json, identify missing managed files or broken references, then regenerate from .agent/modspec.json instead of editing generated files by hand.",
                    "artifact": str(audit_payload.get("audit_report_path") or ""),
                }
            )
        if not actions and root_causes:
            actions.append(
                {
                    "id": "review_root_causes",
                    "summary": "Review classified root causes and decide whether the fix belongs in ModSpec normalization, deterministic generation, or audit expectations.",
                    "artifact": "",
                }
            )
        return actions

    def _repair_rag_advice(
        self,
        workspace: Path,
        *,
        root_causes: list[str],
        repair_plan: list[dict[str, str]],
        build_payload: dict,
        audit_payload: dict,
    ) -> dict:
        try:
            return self.repair_rag_advisor.advise(
                workspace,
                root_causes=root_causes,
                repair_plan=repair_plan,
                build_payload=build_payload,
                audit_payload=audit_payload,
            ).to_dict()
        except Exception as exc:  # RAG advice must never mask the original repair failure.
            return {
                "success": False,
                "attempted": True,
                "reason": f"{type(exc).__name__}: {exc}",
                "query": "",
                "limit": 0,
                "hits": [],
                "hits_count": 0,
                "query_expansions": [],
                "categories": {},
                "capabilities": {},
                "context": "",
                "report_json_path": None,
                "report_md_path": None,
            }

    def _write_agent_run(self, run: AgentRunResult) -> None:
        self.trace_writer.write(run)

    def _agent_trace_summary(self, run: AgentRunResult) -> dict:
        decisions_by_role: dict[str, list[AgentDecision]] = {}
        for decision in run.decisions:
            decisions_by_role.setdefault(decision.role, []).append(decision)
        traces_by_role: dict[str, list[AgentPromptTrace]] = {}
        for trace in run.prompt_traces:
            traces_by_role.setdefault(trace.role, []).append(trace)

        roles = []
        for step in run.steps:
            role_decisions = decisions_by_role.get(step.role, [])
            role_traces = traces_by_role.get(step.role, [])
            role_knowledge_refs = _unique_knowledge_refs(
                item
                for decision in role_decisions
                for item in decision.knowledge_refs
            )
            roles.append(
                {
                    "role": step.role,
                    "status": step.status,
                    "summary": step.summary,
                    "inputs": sorted({item for decision in role_decisions for item in decision.inputs}),
                    "outputs": sorted({item for decision in role_decisions for item in decision.outputs}),
                    "decisions": [decision.to_dict() for decision in role_decisions],
                    "knowledge_ids": [str(item.get("id", "")) for item in role_knowledge_refs if item.get("id")],
                    "knowledge_refs": role_knowledge_refs,
                    "knowledge_refs_count": len(role_knowledge_refs),
                    "prompt_traces_count": len(role_traces),
                    "warnings_count": len(step.warnings),
                    "errors_count": len(step.errors),
                }
            )

        return {
            "success": run.success,
            "mode": run.mode,
            "request": run.request,
            "planner_mode": run.planner_mode,
            "llm_provider": run.llm_provider,
            "workspace": str(run.workspace or ""),
            "roles": roles,
            "roles_count": len(roles),
            "decisions_count": len(run.decisions),
            "prompt_traces_count": len(run.prompt_traces),
        }

    def _render_trace_summary_md(self, run: AgentRunResult, trace_summary: dict) -> str:
        lines = [
            "# Agent Trace Summary",
            "",
            f"Success: {str(run.success).lower()}",
            f"Mode: `{run.mode}`",
            f"Planner: `{run.planner_mode}`",
            f"LLM provider: `{run.llm_provider}`",
            f"Workspace: `{run.workspace or ''}`",
            "",
            "## Roles",
            "",
        ]
        for role in trace_summary.get("roles", []):
            lines.append(f"### {role.get('role')} - {role.get('status')}")
            lines.append("")
            lines.append(str(role.get("summary", "")))
            lines.append("")
            inputs = role.get("inputs") or []
            outputs = role.get("outputs") or []
            if inputs:
                lines.append(f"- inputs: `{', '.join(inputs)}`")
            if outputs:
                lines.append(f"- outputs: `{', '.join(outputs)}`")
            knowledge_ids = role.get("knowledge_ids") or []
            if knowledge_ids:
                lines.append(f"- knowledge ids: `{', '.join(str(item) for item in knowledge_ids)}`")
            lines.append(f"- decisions: `{len(role.get('decisions') or [])}`")
            lines.append(f"- prompt traces: `{role.get('prompt_traces_count', 0)}`")
            lines.append("")
        return "\n".join(lines)

    def _write_repair_plan(self, workspace: Path, payload: dict) -> None:
        agent_dir = ensure_directory(self.config.agent_dir_for(workspace))
        write_json(agent_dir / "agent-repair-plan.json", payload)
        lines = [
            "# Agent Repair Plan",
            "",
            f"Repair needed: {str(payload.get('repair_needed')).lower()}",
            f"Repair executed: {str(payload.get('repair_executed')).lower()}",
            f"Repair success: {str(payload.get('repair_success')).lower()}",
            f"Debug context: `{payload.get('debug_context_path') or ''}`",
            f"Fix request: `{payload.get('fix_request_path') or ''}`",
            f"Audit report: `{payload.get('audit_report_path') or ''}`",
            f"Repair loop report: `{payload.get('repair_loop_report_md_path') or ''}`",
            "",
            "## Root Causes",
            "",
        ]
        root_causes = payload.get("root_causes") or []
        lines.extend([f"- {cause}" for cause in root_causes] or ["- No classified root causes."])
        lines.extend(["", "## Suggested Actions", ""])
        actions = payload.get("repair_plan") or []
        if actions:
            for action in actions:
                lines.append(f"- `{action.get('id', 'action')}`: {action.get('summary', '')}")
                if action.get("artifact"):
                    lines.append(f"  - artifact: `{action['artifact']}`")
        else:
            lines.append("- No repair actions are required.")
        repair_rag = payload.get("repair_rag") or {}
        if repair_rag:
            lines.extend(["", "## Repair RAG Context", ""])
            lines.append(f"- attempted: `{repair_rag.get('attempted')}`")
            lines.append(f"- success: `{repair_rag.get('success')}`")
            if repair_rag.get("reason"):
                lines.append(f"- reason: {repair_rag.get('reason')}")
            if repair_rag.get("query"):
                lines.append(f"- query: `{repair_rag.get('query')}`")
            lines.append(f"- hits: `{repair_rag.get('hits_count', 0)}`")
            lines.append(f"- json: `{repair_rag.get('report_json_path') or ''}`")
            lines.append(f"- report: `{repair_rag.get('report_md_path') or ''}`")
            hits = repair_rag.get("hits") or []
            if hits:
                lines.extend(["", "### Relevant Knowledge", ""])
                for hit in hits:
                    lines.append(f"- `{hit.get('id')}` score={hit.get('score')}: {hit.get('title')}")
                    lines.append(f"  - category: `{hit.get('category')}`")
                    lines.append(f"  - capability: `{hit.get('capability')}`")
                    lines.append(f"  - summary: {hit.get('summary')}")
        repair_loop = payload.get("repair_loop") or {}
        if repair_loop:
            lines.extend(["", "## Executed Repair Loop", ""])
            lines.append(f"- success: `{repair_loop.get('success')}`")
            lines.append(f"- repaired: `{repair_loop.get('repaired')}`")
            lines.append(f"- attempts: `{repair_loop.get('attempts_count')}`")
            lines.append(f"- json: `{repair_loop.get('repair_loop_report_json_path')}`")
            lines.append(f"- report: `{repair_loop.get('repair_loop_report_md_path')}`")
        lines.append("")
        write_text(agent_dir / "agent-repair-plan.md", "\n".join(lines))

    def _render_agent_run_md(self, run: AgentRunResult) -> str:
        lines = [
            "# Agent Run",
            "",
            f"Success: {str(run.success).lower()}",
            f"Mode: {run.mode}",
            f"Planner: {run.planner_mode}",
            f"LLM provider: {run.llm_provider}",
            f"Workspace: `{run.workspace or ''}`",
            "",
            "## Request",
            "",
            "```text",
            run.request,
            "```",
            "",
            "## Steps",
            "",
        ]
        for step in run.steps:
            lines.append(f"- `{step.role}` `{step.status}`: {step.summary}")
            for warning in step.warnings:
                lines.append(f"  - warning: {warning}")
            for error in step.errors:
                lines.append(f"  - error: {error}")
        lines.extend(["", "## Decisions", ""])
        for decision in run.decisions:
            lines.append(f"- `{decision.role}` `{decision.status}`: {decision.decision}")
            lines.append(f"  - rationale: {decision.rationale}")
            if decision.knowledge_ids:
                lines.append(f"  - knowledge ids: `{', '.join(decision.knowledge_ids)}`")
        if run.prompt_trace_json_path:
            lines.extend(["", "## Trace Artifacts", "", f"- prompt trace: `{run.prompt_trace_json_path}`"])
        if run.agent_decisions_md_path:
            lines.append(f"- decisions: `{run.agent_decisions_md_path}`")
        if run.agent_trace_summary_json_path:
            lines.append(f"- trace summary: `{run.agent_trace_summary_json_path}`")
        lines.append("")
        return "\n".join(lines)

    def _render_decisions_md(self, run: AgentRunResult) -> str:
        lines = [
            "# Agent Decisions",
            "",
            f"Success: {str(run.success).lower()}",
            f"Mode: `{run.mode}`",
            f"Planner: `{run.planner_mode}`",
            f"LLM provider: `{run.llm_provider}`",
            f"Workspace: `{run.workspace or ''}`",
            "",
            "## Decisions",
            "",
        ]
        for index, decision in enumerate(run.decisions, start=1):
            lines.append(f"### {index}. {decision.role} - {decision.decision}")
            lines.append("")
            lines.append(f"- status: `{decision.status}`")
            lines.append(f"- rationale: {decision.rationale}")
            if decision.inputs:
                lines.append(f"- inputs: `{', '.join(decision.inputs)}`")
            if decision.outputs:
                lines.append(f"- outputs: `{', '.join(decision.outputs)}`")
            if decision.knowledge_ids:
                lines.append(f"- knowledge ids: `{', '.join(decision.knowledge_ids)}`")
                lines.append("- knowledge refs:")
                for item in decision.knowledge_refs:
                    lines.append(
                        f"  - `{item.get('id')}` `{item.get('capability')}` "
                        f"score={item.get('score')}: {item.get('title')}"
                    )
            lines.append("")
        if not run.decisions:
            lines.append("- No decisions were recorded.")
            lines.append("")
        return "\n".join(lines)

    def _execution_errors(self, payload: dict) -> list[str]:
        build = payload.get("build", {})
        if build.get("attempted") and build.get("success") is False:
            issues = build.get("issues") or []
            if issues:
                return [str(issue.get("message", "Build issue")) for issue in issues if isinstance(issue, dict)]
            return [str(build.get("summary", "Build failed."))]
        validation = payload.get("validation", {})
        issues = validation.get("issues") or []
        return [str(issue.get("message", "Execution issue")) for issue in issues if isinstance(issue, dict)]

    def _audit_success(self, audit_payload: dict) -> bool:
        if not audit_payload.get("attempted"):
            return True
        return audit_payload.get("success") is True

    def _direct_code_requested(
        self,
        request_text: str,
        code_lane: str,
        artifacts: PlannerArtifacts | None,
    ) -> bool:
        lane = _normalize_code_lane(code_lane)
        if lane == "modspec":
            return False
        if lane == "direct":
            return True

        for payload in (
            artifacts.raw_json if artifacts is not None else None,
            artifacts.normalized_json if artifacts is not None else None,
        ):
            if isinstance(payload, dict):
                if payload.get("requires_direct_code") is True:
                    return True
                if isinstance(payload.get("direct_code_plan"), dict):
                    return True

        lowered = request_text.lower()
        direct_hints = (
            "direct code",
            "direct-code",
            "raw java",
            "freeform java",
            "custom java",
            "patch source",
            "source patch",
            "write java",
            "network packet",
            "自由 java",
            "直接写代码",
            "源码补丁",
        )
        if any(hint in lowered for hint in direct_hints):
            return True
        return any(
            phrase in lowered
            for phrase in (
                "custom gui",
                "arbitrary gui",
                "handwritten gui",
                "freeform gui",
            )
        )

    def _execute_direct_code_lane(
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
        plan = self._direct_code_plan(request_text, spec, artifacts, source=source)
        result = self.direct_code_agent.apply_plan(
            workspace,
            plan,
            build=build_result,
            audit_payload=audit_payload or {"attempted": False, "success": None},
        )
        steps.append(
            AgentStep(
                role="direct_code_reviewer",
                status="pass" if result.review.approved else "fail",
                summary="Reviewed structured Direct Code patch plan.",
                details={
                    "approved": result.review.approved,
                    "checks": result.review.checks,
                    "affected_files": result.review.affected_files,
                    "artifacts": {key: str(value) for key, value in result.artifacts.items()},
                },
                warnings=list(result.review.warnings),
                errors=list(result.review.errors),
            )
        )
        decisions.append(
            AgentDecision(
                role="direct_code_reviewer",
                decision="approve_direct_code_plan" if result.review.approved else "reject_direct_code_plan",
                rationale="The reviewer checks Direct Code paths, operations, risky tokens, Java package declarations, and rollback snapshot coverage before source patches are accepted.",
                status="pass" if result.review.approved else "fail",
                inputs=["direct_code_plan", "workspace_policy"],
                outputs=[
                    f"approved={str(result.review.approved).lower()}",
                    f"affected_files={len(result.review.affected_files)}",
                    f"errors={len(result.review.errors)}",
                ],
            )
        )
        steps.append(
            AgentStep(
                role="direct_code_agent",
                status="pass" if result.success else "fail",
                summary="Applied structured Direct Code patch." if result.success else "Direct Code patch was not accepted.",
                details={
                    "changed_files": result.changed_files,
                    "snapshot_files": result.snapshot_files,
                    "artifacts": {key: str(value) for key, value in result.artifacts.items()},
                },
                warnings=list(result.warnings),
                errors=list(result.errors),
            )
        )
        decisions.append(
            AgentDecision(
                role="direct_code_agent",
                decision="apply_structured_patch",
                rationale="The Direct Code agent applies only reviewed structured JSON changes inside the generated workspace, then relies on audit/build gates and rollback artifacts.",
                status="pass" if result.success else "fail",
                inputs=["reviewed_direct_code_plan"],
                outputs=[
                    f"changed_files={len(result.changed_files)}",
                    f"snapshots={len(result.snapshot_files)}",
                    f"report={result.artifacts.get('report_json')}",
                ],
            )
        )
        return result

    def _direct_code_plan(
        self,
        request_text: str,
        spec: ModSpec,
        artifacts: PlannerArtifacts | None,
        *,
        source: str,
    ) -> DirectCodePlan:
        for payload in (
            artifacts.raw_json if artifacts is not None else None,
            artifacts.normalized_json if artifacts is not None else None,
        ):
            if isinstance(payload, dict) and isinstance(payload.get("direct_code_plan"), dict):
                plan = DirectCodePlan.from_dict(payload, request=request_text)
                if plan.changes:
                    return plan
        return self._default_direct_code_plan(request_text, spec, source=source)

    def _default_direct_code_plan(self, request_text: str, spec: ModSpec, *, source: str) -> DirectCodePlan:
        package_name = f"{spec.package_name}.directcode"
        package_path = "/".join(package_name.split("."))
        class_name = "DirectCodeNotes" if source == "generate" else "DirectCodeModifyNotes"
        content = "\n".join(
            [
                f"package {package_name};",
                "",
                f"public final class {class_name} {{",
                f"    private {class_name}() {{",
                "    }",
                "",
                "    public static String summary() {",
                f'        return "Direct Code Lane {source} patch applied."; ',
                "    }",
                "}",
                "",
            ]
        )
        return DirectCodePlan(
            request=request_text,
            summary=f"Add an audited Direct Code Lane marker class for {source}.",
            changes=[
                DirectCodeChange(
                    path=f"src/main/java/{package_path}/{class_name}.java",
                    operation="write_file",
                    content=content,
                    reason="Provide a safe, build-verifiable direct-code patch artifact.",
                    risk_level="low",
                )
            ],
        )

    def _update_generation_summary_direct_code(
        self,
        workspace: Path,
        result: DirectCodeApplyResult,
        *,
        generated_files: list[str],
    ) -> None:
        summary_path = self.config.agent_dir_for(workspace) / "generation-summary.json"
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload["generated_files"] = _merge_generated_files(
            [str(item) for item in generated_files],
            result.changed_files,
            [
                str(path.relative_to(workspace))
                for path in result.artifacts.values()
                if path.exists() and workspace in path.resolve().parents
            ],
        )
        payload["direct_code"] = result.to_dict()
        warnings = payload.get("warnings")
        if not isinstance(warnings, list):
            warnings = []
        payload["warnings"] = _merge_generated_files([str(item) for item in warnings], result.warnings, result.errors)
        write_generation_summary(workspace, self.config, payload)


class NeoForgeRuntimePlugin:
    """NeoForge domain adapter for the generic agent runtime."""

    domain_name = "neoforge"
    domain_spec_plugin = NeoForgeModSpecPlugin()

    def __init__(self, orchestrator: AgentOrchestrator) -> None:
        self.orchestrator = orchestrator

    def plan_generate(self, request: AgentRuntimeRequest) -> AgentRuntimeStageResult:
        overrides = request.options.get("overrides") or RequestOverrides()
        try:
            spec, artifacts, planner_warnings, planner_mode_used = self.orchestrator._plan_generate(
                request.request,
                overrides=overrides,
                planner_mode=request.planner_mode,
                llm_provider=request.llm_provider,
                require_llm=bool(request.options.get("require_llm")),
            )
        except (LLMPlanningError, ValueError) as exc:
            traces = []
            if isinstance(exc, LLMPlanningError):
                traces.append(self.orchestrator._trace_from_artifacts("planner_agent", "generate_modspec", exc.artifacts))
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

        feature_count = len(list(spec.iter_features()))
        code_lane = _normalize_code_lane(str(request.options.get("code_lane", "hybrid")))
        intent_contract = self.orchestrator._intent_contract(request.request, spec, artifacts, code_lane=code_lane)
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
                        "domain": self.domain_name,
                        "domain_spec": self.domain_spec_plugin.metadata.to_dict(),
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
                        f"direct_code={self.orchestrator._direct_code_requested(request.request, str(request.options.get('code_lane', 'hybrid')), artifacts)}",
                    ],
                    knowledge_refs=self.orchestrator._knowledge_refs_from_planner_artifacts(artifacts),
                )
            ],
            prompt_traces=[
                self.orchestrator._planner_trace(
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

    def review(self, request: AgentRuntimeRequest, plan: AgentRuntimeStageResult) -> AgentRuntimeStageResult:
        spec = plan.state["spec"]
        review_step = self.orchestrator._review_spec(spec)
        return AgentRuntimeStageResult(
            success=review_step.status != "fail",
            steps=[review_step],
            decisions=[self.orchestrator._decision_from_review(review_step)],
            payload={"spec": spec.to_dict()},
        )

    def execute_generate(
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
        direct_code_requested = self.orchestrator._direct_code_requested(request.request, code_lane, artifacts)
        result = self.orchestrator.planner.execute_spec(
            spec,
            workspace_name=request.options.get("workspace_name"),
            overwrite=bool(request.options.get("overwrite")),
            run_build=request.run_build and not direct_code_requested,
            parsed_from_request=True,
        )
        if artifacts is not None:
            artifacts.planner_mode = f"agent:{planner_mode_used}"
            write_planner_artifacts(result.workspace_dir, self.orchestrator.config, artifacts)
        if planner_warnings:
            result.warnings = [*planner_warnings, *result.warnings]
            write_generation_summary(result.workspace_dir, self.orchestrator.config, result.to_dict())

        extra_steps: list[AgentStep] = []
        extra_decisions: list[AgentDecision] = []
        direct_code_result: DirectCodeApplyResult | None = None
        if direct_code_requested and result.validation.is_valid:
            direct_code_result = self.orchestrator._execute_direct_code_lane(
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
                result.generated_files = _merge_generated_files(result.generated_files, direct_code_result.changed_files)
                result.build = self.orchestrator.planner.builder.build(result.workspace_dir, repair=request.repair)
            else:
                result.warnings = [*result.warnings, *direct_code_result.errors]
            self.orchestrator._update_generation_summary_direct_code(
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
            state={"generation": result, "direct_code": direct_code_result},
            workspace=result.workspace_dir,
            payload=execution_payload,
            build_payload=execution_payload.get("build", {}),
            steps=[
                AgentStep(
                    role="executor_agent",
                    status="pass" if execution_success else "fail",
                    summary="Generated workspace." if result.succeeded else "Workspace generation failed.",
                    details={
                        "domain": self.domain_name,
                        "workspace": str(result.workspace_dir),
                        "generated_files": list(result.generated_files),
                        "build": result.build.to_dict(),
                        "code_lane": code_lane,
                        "direct_code": direct_code_result.to_dict() if direct_code_result is not None else None,
                    },
                    warnings=list(result.warnings),
                    errors=[] if execution_success else self.orchestrator._execution_errors(execution_payload),
                )
            ] + extra_steps,
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
            ] + extra_decisions,
        )

    def audit(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        steps: list[AgentStep] = []
        decisions: list[AgentDecision] = []
        if execution.workspace is None:
            payload = {"attempted": request.run_audit, "success": False, "error": "Execution did not produce a workspace."}
            return AgentRuntimeStageResult(success=False, steps=steps, decisions=decisions, payload=payload)
        direct_code_result = execution.state.get("direct_code") if isinstance(execution.state, dict) else None
        payload = self.orchestrator._run_audit_step(
            execution.workspace,
            request.run_audit or isinstance(direct_code_result, DirectCodeApplyResult),
            steps,
            decisions,
        )
        if isinstance(direct_code_result, DirectCodeApplyResult):
            generation = execution.state.get("generation") if isinstance(execution.state, dict) else None
            build_result = generation.build if getattr(generation, "build", None) is not None else BuildResult(
                attempted=bool(execution.build_payload.get("attempted")),
                success=execution.build_payload.get("success"),
                command=[str(item) for item in execution.build_payload.get("command", [])],
                return_code=execution.build_payload.get("return_code"),
                summary=str(execution.build_payload.get("summary", "")),
            )
            direct_code_success = (
                direct_code_result.success
                and build_result.attempted
                and build_result.success is True
                and self.orchestrator._audit_success(payload)
            )
            self.orchestrator.direct_code_agent.finalize_report(
                execution.workspace,
                direct_code_result,
                build=build_result,
                audit_payload=payload,
                success=bool(direct_code_success),
            )
            execution.payload["direct_code"] = direct_code_result.to_dict()
            self.orchestrator._update_generation_summary_direct_code(
                execution.workspace,
                direct_code_result,
                generated_files=list(execution.payload.get("generated_files", [])),
            )
        return AgentRuntimeStageResult(
            success=self.orchestrator._audit_success(payload),
            steps=steps,
            decisions=decisions,
            payload=payload,
            workspace=execution.workspace,
        )

    def repair(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
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
        payload = self.orchestrator._run_repair_analysis_step(
            execution.workspace,
            build_payload=execution.build_payload,
            audit_payload=audit.payload,
            repair=request.repair,
            steps=steps,
            decisions=decisions,
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

    def final_success(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> bool:
        success = execution.success and self.orchestrator._audit_success(audit.payload)
        direct_code_result = execution.state.get("direct_code") if isinstance(execution.state, dict) else None
        if isinstance(direct_code_result, DirectCodeApplyResult):
            success = success and direct_code_result.success
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
                "domain": self.domain_name,
                "domain_spec": self.domain_spec_plugin.metadata.to_dict(),
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
                "domain": self.domain_name,
                "failed_stage": "reviewer",
            },
            "spec": plan.payload.get("spec"),
            "review": review.payload,
        }


def _normalize_knowledge_refs(items: list[dict] | tuple[dict, ...], *, reason: str) -> list[dict]:
    refs: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("id", "")).strip()
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        refs.append(
            {
                "id": identifier,
                "title": str(item.get("title", "")),
                "category": str(item.get("category", "")),
                "capability": str(item.get("capability", item.get("category", ""))),
                "score": int(item.get("score", 0) or 0),
                "source": str(item.get("source", "")),
                "reason": str(item.get("reason") or reason),
            }
        )
    return refs


def _unique_knowledge_refs(items) -> list[dict]:
    refs: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("id", "")).strip()
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        refs.append(dict(item))
    return refs


def _normalize_code_lane(value: str) -> str:
    normalized = str(value or "hybrid").strip().lower()
    if normalized not in {"hybrid", "modspec", "direct"}:
        raise ValueError(f"Unsupported code lane: {value}")
    return normalized


def _merge_generated_files(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            value = str(item).replace("\\", "/")
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(value)
    return merged
