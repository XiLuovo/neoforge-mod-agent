from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_models import AgentDecision, AgentPromptTrace, AgentRunResult, AgentStep
from .agent_options import (
    merge_generated_files as _merge_generated_files,
    normalize_code_lane as _normalize_code_lane,
    normalize_rag_mode as _normalize_rag_mode,
)
from .agent_orchestrator_wiring import (
    create_neoforge_modify_workflow,
    create_neoforge_repair_workflow,
    create_neoforge_runtime,
)
from .agent_runtime import AgentRuntimeRequest, AgentTraceWriter
from .auditor import WorkspaceAuditor
from .config import AppConfig
from .direct_code_agent import DirectCodeAgent, DirectCodeApplyResult, DirectCodeChange, DirectCodePlan
from .evidence_writer import AgentEvidenceWriter
from .llm_client import check_llm_provider_health, create_llm_client
from .llm_planner import LLMPlanningError, PlannerArtifacts, plan_with_decomposed_llm, plan_with_llm
from .llm_reviewer import LLM_REVIEWER_SYSTEM_PROMPT, LLMReviewResult, LLMReviewer
from .models import BuildResult, ModSpec, RequestOverrides
from .planner import ModProjectPlanner
from .planner_resolution import PlannerResolution
from .repair_loop import AutoRepairRunner
from .repair_rag import RepairRAGAdvisor
from .tool_calling_agent import ToolCallingRepairAgent
from .tools import ensure_directory, slugify_mod_id, write_generation_summary, write_json, write_text
from .validator import validate_mod_spec


class AgentOrchestrator:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()
        self.planner = ModProjectPlanner(self.config)
        self.auditor = WorkspaceAuditor(self.config)
        self.repair_runner = AutoRepairRunner(self.config)
        self.repair_rag_advisor = RepairRAGAdvisor(self.config)
        self.tool_calling_repair_agent = ToolCallingRepairAgent(
            self.config,
            auditor=self.auditor,
            builder=self.planner.builder,
            repair_runner=self.repair_runner,
        )
        self.llm_reviewer = LLMReviewer(self.config)
        self.direct_code_agent = DirectCodeAgent(self.config)
        self.evidence_writer = AgentEvidenceWriter(self.config)
        self.trace_writer = AgentTraceWriter(self.config)
        self.modify_workflow = create_neoforge_modify_workflow(self)
        self.repair_workflow = create_neoforge_repair_workflow(self)
        self.runtime = create_neoforge_runtime(self)

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
        max_iterations: int = 1,
        rag_mode: str = "auto",
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
                    "max_iterations": max_iterations,
                    "rag_mode": _normalize_rag_mode(rag_mode),
                },
            )
        )

    def run_develop(
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
        max_iterations: int = 5,
        rag_mode: str = "auto",
    ) -> AgentRunResult:
        return self.runtime.run_generate(
            AgentRuntimeRequest(
                mode="develop",
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
                    "max_iterations": max_iterations,
                    "rag_mode": _normalize_rag_mode(rag_mode),
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
        require_llm: bool = False,
        code_lane: str = "hybrid",
        max_iterations: int = 1,
    ) -> AgentRunResult:
        return self.modify_workflow.run(
            workspace,
            change_request,
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            run_build=run_build,
            run_audit=run_audit,
            repair=repair,
            require_llm=require_llm,
            code_lane=code_lane,
            max_iterations=max_iterations,
        )

    def run_repair(
        self,
        workspace: Path,
        *,
        goal: str = "Fix build and audit failures without changing user-owned files.",
        planner_mode: str = "llm",
        llm_provider: str = "mock",
        max_iterations: int = 5,
        run_build: bool = True,
        run_audit: bool = True,
        rag_mode: str = "auto",
    ) -> AgentRunResult:
        return self.repair_workflow.run(
            workspace,
            goal=goal,
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            max_iterations=max_iterations,
            run_build=run_build,
            run_audit=run_audit,
            rag_mode=rag_mode,
        )

    def _plan_generate(
        self,
        request: str,
        *,
        overrides: RequestOverrides,
        planner_mode: str,
        llm_provider: str,
        require_llm: bool = False,
    ) -> PlannerResolution:
        if planner_mode == "rules":
            return PlannerResolution(
                spec=self._apply_overrides(self.planner.parse_request(request, overrides=overrides), overrides),
                artifacts=None,
                warnings=[],
                planner_mode_used="rules",
            )

        if planner_mode in {"llm", "decomposed"}:
            planner_label = "Decomposed planner" if planner_mode == "decomposed" else "LLM planner"
            planner_fn = plan_with_decomposed_llm if planner_mode == "decomposed" else plan_with_llm
            health = check_llm_provider_health(llm_provider)
            if llm_provider == "openai-compatible" and not health.healthy:
                if require_llm:
                    raise ValueError(
                        f"{planner_label} is required but provider health check failed: "
                        + "; ".join([*health.errors, *health.warnings])
                    )
                spec = self._apply_overrides(self.planner.parse_request(request, overrides=overrides), overrides)
                warnings = [
                    f"{planner_label} provider health check failed; planner fell back to rules.",
                    *health.errors,
                    *health.warnings,
                ]
                return PlannerResolution(
                    spec=spec,
                    artifacts=None,
                    warnings=warnings,
                    planner_mode_used=f"{planner_mode}->rules",
                )
            try:
                client = create_llm_client(llm_provider, self.config.project_root)
                spec, artifacts = planner_fn(request, client, config=self.config)
                self._apply_overrides(spec, overrides)
                return PlannerResolution(
                    spec=spec,
                    artifacts=artifacts,
                    warnings=list(artifacts.warnings),
                    planner_mode_used=planner_mode,
                )
            except (LLMPlanningError, ValueError, RuntimeError) as exc:
                if require_llm:
                    if isinstance(exc, LLMPlanningError):
                        raise
                    raise ValueError(f"{planner_label} is required but failed: {exc}") from exc
                spec = self._apply_overrides(self.planner.parse_request(request, overrides=overrides), overrides)
                artifacts = exc.artifacts if isinstance(exc, LLMPlanningError) else None
                warnings = [f"{planner_label} failed; fallback to rules: {exc}"]
                if artifacts is not None:
                    warnings.extend(artifacts.warnings)
                return PlannerResolution(
                    spec=spec,
                    artifacts=artifacts,
                    warnings=warnings,
                    planner_mode_used=f"{planner_mode}->rules",
                )

        rules_spec = self.planner.parse_request(request, overrides=overrides)
        if rules_spec.all_content() or rules_spec.entities or rules_spec.recipes:
            return PlannerResolution(
                spec=rules_spec,
                artifacts=None,
                warnings=[],
                planner_mode_used="auto->rules",
            )

        health = check_llm_provider_health(llm_provider)
        if llm_provider == "openai-compatible" and not health.healthy:
            warnings = [
                "Auto planner kept rules output because LLM provider health check failed.",
                *health.errors,
                *health.warnings,
            ]
            return PlannerResolution(
                spec=self._apply_overrides(rules_spec, overrides),
                artifacts=None,
                warnings=warnings,
                planner_mode_used="auto->rules",
            )
        try:
            client = create_llm_client(llm_provider, self.config.project_root)
            spec, artifacts = plan_with_llm(request, client, config=self.config)
            self._apply_overrides(spec, overrides)
            warnings = [*artifacts.warnings, "Auto planner used LLM because rules planning returned no content."]
            return PlannerResolution(
                spec=spec,
                artifacts=artifacts,
                warnings=warnings,
                planner_mode_used="auto->llm",
            )
        except (LLMPlanningError, ValueError, RuntimeError) as exc:
            artifacts = exc.artifacts if isinstance(exc, LLMPlanningError) else None
            warnings = [f"Auto planner fallback to rules after LLM failure: {exc}"]
            if artifacts is not None:
                warnings.extend(artifacts.warnings)
            return PlannerResolution(
                spec=self._apply_overrides(rules_spec, overrides),
                artifacts=artifacts,
                warnings=warnings,
                planner_mode_used="auto->rules",
            )

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

    def _run_llm_reviewer(
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
        try:
            result = self.llm_reviewer.review(
                workspace=workspace,
                user_goal=user_goal,
                llm_provider=llm_provider,
                review_stage=review_stage,
                intent_contract=intent_contract,
                modspec=modspec,
                rag=rag,
                tool_call_trace=tool_call_trace,
                changed_files=changed_files,
                audit_result=audit_result,
                build_result=build_result,
                prior_reviewer_observation=prior_reviewer_observation,
            )
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            report = {
                "coverage_status": "partial",
                "covered_requirements": [],
                "missing_requirements": [],
                "unsupported_or_risky_requests": [],
                "patch_risks": [error_text],
                "recommended_checks": ["Inspect reviewer provider configuration and rerun review."],
                "decision": "needs_repair",
                "confidence": 0.0,
            }
            result = LLMReviewResult(
                success=False,
                reviewer_report=report,
                prompt_trace=AgentPromptTrace(
                    role="reviewer_agent",
                    planner_mode="llm_reviewer",
                    provider=llm_provider,
                    prompt_kind=f"reviewer_{review_stage}",
                    system_prompt=LLM_REVIEWER_SYSTEM_PROMPT,
                    input_text=user_goal,
                    normalized_json=report,
                    warnings=[error_text],
                    error=error_text,
                ),
                provider=llm_provider,
                model="",
                warnings=[error_text],
            )
        self._append_llm_reviewer_trace(result, steps, decisions, review_stage=review_stage)
        return result

    def _append_llm_reviewer_trace(
        self,
        result: LLMReviewResult,
        steps: list[AgentStep],
        decisions: list[AgentDecision],
        *,
        review_stage: str,
    ) -> None:
        report = result.to_dict()
        status = "pass" if report.get("decision") == "approve" else "warning" if report.get("decision") == "needs_repair" else "fail"
        steps.append(
            AgentStep(
                role="reviewer_agent",
                status=status,
                summary=f"LLM reviewer {report.get('decision')} with {report.get('coverage_status')} coverage.",
                details={
                    "review_stage": review_stage,
                    "decision": report.get("decision"),
                    "coverage_status": report.get("coverage_status"),
                    "confidence": report.get("confidence"),
                    "source": "llm_reviewer",
                },
                warnings=[*report.get("missing_requirements", []), *report.get("patch_risks", [])],
                errors=report.get("unsupported_or_risky_requests", []) if status == "fail" else [],
            )
        )
        decisions.append(
            AgentDecision(
                role="reviewer_agent",
                decision=f"llm_review_{report.get('decision')}",
                rationale="The LLM reviewer checks requirement coverage, unsupported requests, patch risk, and residual audit/build risk without overriding deterministic gates.",
                status=status,
                inputs=["user_goal", "intent_contract", "modspec", "tool_trace", "audit_result", "build_result"],
                outputs=[
                    f"coverage_status={report.get('coverage_status')}",
                    f"decision={report.get('decision')}",
                    f"confidence={report.get('confidence')}",
                ],
            )
        )

    def _load_modspec_dict(self, workspace: Path) -> dict[str, Any]:
        path = workspace / ".agent" / "modspec.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _changed_files_from_repair_payload(self, payload: dict[str, Any]) -> list[str]:
        files: list[str] = []
        structured = payload.get("structured_patch") if isinstance(payload, dict) else {}
        if isinstance(structured, dict):
            files.extend(str(item) for item in structured.get("changed_files", []) if str(item))
        repair_loop = payload.get("repair_loop") if isinstance(payload, dict) else {}
        if isinstance(repair_loop, dict):
            for attempt in repair_loop.get("attempts", []) or []:
                if isinstance(attempt, dict):
                    files.extend(str(item) for item in attempt.get("changed_files", []) if str(item))
        return sorted(set(files))

    def _run_repair_analysis_step(
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
                max_attempts=max_attempts,
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
        self.evidence_writer.write_agent_repair_plan(workspace, payload)

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
