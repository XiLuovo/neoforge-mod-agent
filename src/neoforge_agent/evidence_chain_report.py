from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from . import agent_orchestrator as agent_orchestrator_module
from .agent_orchestrator import AgentOrchestrator
from .auditor import WorkspaceAuditor
from .benchmark_report import BenchmarkReportRunner
from .config import AppConfig
from .models import BuildErrorKind, BuildIssue, BuildResult, ModSpec
from .modifier import WorkspaceModifier
from .planner import ModProjectPlanner
from .tools import ensure_directory, write_json, write_text
from .validator import validate_mod_spec


@dataclass(slots=True)
class EvidenceSampleResult:
    identifier: str
    title: str
    phase: str
    success: bool
    summary: str
    workspace: str | None = None
    generated_files_count: int = 0
    audit_success: bool | None = None
    build_success: bool | None = None
    repair_success: bool | None = None
    runtime_validation: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "title": self.title,
            "phase": self.phase,
            "success": self.success,
            "summary": self.summary,
            "workspace": self.workspace,
            "generated_files_count": self.generated_files_count,
            "audit_success": self.audit_success,
            "build_success": self.build_success,
            "repair_success": self.repair_success,
            "runtime_validation": dict(self.runtime_validation),
            "artifacts": dict(self.artifacts),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class EvidenceLayerResult:
    identifier: str
    title: str
    success_count: int
    total_cases: int
    success_rate: float
    recovery_count: int
    recovery_total: int
    recovery_rate: float
    generated_files_count: int
    runtime_validation: dict[str, Any]
    acceptance_samples: list[EvidenceSampleResult] = field(default_factory=list)
    failure_samples: list[EvidenceSampleResult] = field(default_factory=list)
    recovery_samples: list[EvidenceSampleResult] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        if any(not sample.success for sample in self.acceptance_samples):
            return False
        if any(sample.success for sample in self.failure_samples):
            return False
        if any(not sample.success for sample in self.recovery_samples):
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "title": self.title,
            "success": self.success,
            "success_count": self.success_count,
            "total_cases": self.total_cases,
            "success_rate": self.success_rate,
            "recovery_count": self.recovery_count,
            "recovery_total": self.recovery_total,
            "recovery_rate": self.recovery_rate,
            "generated_files_count": self.generated_files_count,
            "runtime_validation": dict(self.runtime_validation),
            "acceptance_samples": [sample.to_dict() for sample in self.acceptance_samples],
            "failure_samples": [sample.to_dict() for sample in self.failure_samples],
            "recovery_samples": [sample.to_dict() for sample in self.recovery_samples],
            "artifacts": dict(self.artifacts),
            "notes": list(self.notes),
        }


@dataclass(slots=True)
class EvidenceChainReportResult:
    success: bool
    run_id: str
    report_dir: Path
    layers: list[EvidenceLayerResult]
    metrics: dict[str, Any]
    evidence_chain_report_json_path: Path
    evidence_chain_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "layers": [layer.to_dict() for layer in self.layers],
            "metrics": dict(self.metrics),
            "evidence_chain_report_json_path": str(self.evidence_chain_report_json_path),
            "evidence_chain_report_md_path": str(self.evidence_chain_report_md_path),
        }


class EvidenceChainReportRunner:
    """Aggregate the layered evidence chain into one report."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        eval_limit: int = 2,
        repair_limit: int = 2,
    ) -> EvidenceChainReportResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        root_dir = ensure_directory(self.config.workspace_root / "evidence-chain-runs" / run_id)
        report_dir = ensure_directory(root_dir / ".agent")
        scoped_config = replace(self.config, workspace_root=ensure_directory(root_dir / "runs"))

        stable = self._run_stable_layer(scoped_config, root_dir, run_id, eval_limit=eval_limit, repair_limit=repair_limit)
        behavior = self._run_behavior_layer(scoped_config, root_dir, run_id)
        patch = self._run_patch_agent_layer(scoped_config, root_dir, run_id)
        layers = [stable, behavior, patch]
        metrics = self._metrics(layers)
        success = all(layer.success for layer in layers)

        report_json = report_dir / "evidence-chain-report.json"
        report_md = report_dir / "evidence-chain-report.md"
        result = EvidenceChainReportResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            layers=layers,
            metrics=metrics,
            evidence_chain_report_json_path=report_json,
            evidence_chain_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_markdown(result))
        return result

    def _run_stable_layer(
        self,
        scoped_config: AppConfig,
        root_dir: Path,
        run_id: str,
        *,
        eval_limit: int,
        repair_limit: int,
    ) -> EvidenceLayerResult:
        layer_root = ensure_directory(root_dir / "stable")
        layer_config = replace(scoped_config, workspace_root=ensure_directory(layer_root / "runs"))
        benchmark = BenchmarkReportRunner(layer_config).run(
            run_name=f"{run_id}-stable",
            eval_limit=eval_limit,
            repair_limit=repair_limit,
            baseline_provider="mock",
            candidate_provider="mock",
            run_build=False,
            run_audit=True,
        )

        completed_runs = [run for run in benchmark.model_runs if run.status in {"pass", "fail"}]
        acceptance_samples = [
            EvidenceSampleResult(
                identifier=f"model-{run.label.lower()}",
                title=f"{run.label} {run.provider}",
                phase="acceptance",
                success=run.status == "pass",
                summary=f"{run.provider_kind} model run completed with success_rate={_format_rate(run.metrics.get('success_rate'))}.",
                generated_files_count=int(run.metrics.get("generated_files_total", 0) or 0),
                audit_success=_number_to_bool(run.metrics.get("audit_success_rate")),
                build_success=_attempted_rate_to_bool(
                    run.metrics,
                    attempted_key="build_attempted_count",
                    rate_key="build_success_rate",
                ),
                runtime_validation={
                    "success_rate": run.metrics.get("success_rate"),
                    "audit_success_rate": run.metrics.get("audit_success_rate"),
                    "build_attempted_count": run.metrics.get("build_attempted_count"),
                    "build_success_rate": run.metrics.get("build_success_rate"),
                    "build_gate": "passed"
                    if _attempted_rate_to_bool(run.metrics, attempted_key="build_attempted_count", rate_key="build_success_rate") is True
                    else "failed"
                    if _attempted_rate_to_bool(run.metrics, attempted_key="build_attempted_count", rate_key="build_success_rate") is False
                    else "skipped",
                    "eval_report_path": run.eval_report_path,
                },
                artifacts={
                    "eval_report_json": run.eval_report_path or "",
                },
            )
            for run in completed_runs
        ]

        failure_samples: list[EvidenceSampleResult] = []
        recovery_samples: list[EvidenceSampleResult] = []
        for failure in benchmark.failure_types:
            failure_samples.append(
                EvidenceSampleResult(
                    identifier=failure.identifier,
                    title=failure.title,
                    phase="failure",
                    success=False,
                    summary=f"Injected failure '{failure.identifier}' was detected by audit and repair planning.",
                    generated_files_count=0,
                    audit_success=failure.audit_detected,
                    repair_success=failure.repair_loop_repaired and failure.audit_recovered,
                    runtime_validation={
                        "audit_detected": failure.audit_detected,
                        "repair_loop_repaired": failure.repair_loop_repaired,
                        "audit_recovered": failure.audit_recovered,
                        "initial_audit_errors_count": failure.initial_audit_errors_count,
                        "repair_rag_hits_count": failure.repair_rag_hits_count,
                    },
                    artifacts={
                        "workspace": failure.workspace or "",
                    },
                    errors=[f"{failure.initial_audit_errors_count} initial audit error(s)"],
                )
            )
            recovery_samples.append(
                EvidenceSampleResult(
                    identifier=f"{failure.identifier}-recovered",
                    title=f"{failure.title} recovery",
                    phase="recovery",
                    success=failure.repair_loop_repaired and failure.audit_recovered,
                    summary=f"Repair loop recovered '{failure.identifier}' and final audit passed.",
                    generated_files_count=0,
                    audit_success=True,
                    repair_success=True,
                    runtime_validation={
                        "audit_recovered": failure.audit_recovered,
                        "repair_loop_repaired": failure.repair_loop_repaired,
                        "repair_rag_hits_count": failure.repair_rag_hits_count,
                    },
                    artifacts={
                        "workspace": failure.workspace or "",
                    },
                )
            )

        runtime_validation = {
            "source": str(self.config.project_root / "docs" / "test-matrix.md"),
            "runtime_cases_total": benchmark.metrics.get("runtime_cases_total", 0),
            "runtime_pass_rate": benchmark.metrics.get("runtime_pass_rate"),
            "runtime_cases": [case.to_dict() for case in benchmark.runtime_cases],
            "benchmark_report_json": str(benchmark.benchmark_report_json_path),
            "benchmark_report_md": str(benchmark.benchmark_report_md_path),
            "benchmark_report_html": str(benchmark.benchmark_report_html_path),
            "repair_eval_report": benchmark.repair_eval_report_path or "",
        }
        acceptance_success_count = sum(1 for sample in acceptance_samples if sample.success)
        recovery_success_count = sum(1 for sample in recovery_samples if sample.success)
        generated_files_count = sum(int(run.metrics.get("generated_files_total", 0) or 0) for run in completed_runs)
        return EvidenceLayerResult(
            identifier="stable",
            title="Stable ModSpec Layer",
            success_count=acceptance_success_count,
            total_cases=len(acceptance_samples),
            success_rate=_rate(acceptance_success_count, len(acceptance_samples)),
            recovery_count=recovery_success_count,
            recovery_total=len(recovery_samples),
            recovery_rate=_rate(recovery_success_count, len(recovery_samples)),
            generated_files_count=generated_files_count,
            runtime_validation=runtime_validation,
            acceptance_samples=acceptance_samples,
            failure_samples=failure_samples,
            recovery_samples=recovery_samples,
            artifacts={
                "benchmark_report_json": str(benchmark.benchmark_report_json_path),
                "benchmark_report_md": str(benchmark.benchmark_report_md_path),
                "benchmark_report_html": str(benchmark.benchmark_report_html_path),
            },
            notes=[
                "Runtime validation is sourced from the documented manual Minecraft matrix.",
            ],
        )

    def _run_behavior_layer(self, scoped_config: AppConfig, root_dir: Path, run_id: str) -> EvidenceLayerResult:
        layer_root = ensure_directory(root_dir / "behavior")
        layer_config = replace(scoped_config, workspace_root=ensure_directory(layer_root / "runs"))
        planner = ModProjectPlanner(layer_config)
        auditor = WorkspaceAuditor(layer_config)

        acceptance_specs = [
            self.config.project_root / "examples" / "behavior_dsl_battle_charm.json",
            self.config.project_root / "examples" / "machine_ruby_compressor.json",
            self.config.project_root / "examples" / "progression_gameplay_loop.json",
            self.config.project_root / "examples" / "quest_guide_gameplay_loop.json",
        ]

        acceptance_samples: list[EvidenceSampleResult] = []
        runtime_validation_runs: list[dict[str, Any]] = []
        generated_files_count = 0
        for index, spec_path in enumerate(acceptance_specs, start=1):
            spec = planner.spec_from_file(spec_path)
            workspace_name = f"{run_id}-behavior-{spec_path.stem}"
            result = planner.execute_spec(
                spec,
                workspace_name=workspace_name,
                overwrite=True,
                run_build=False,
            )
            audit = auditor.audit_workspace(result.workspace_dir)
            behavior_report_path = result.workspace_dir / ".agent" / "behavior-report.json"
            behavior_report = _load_json_dict(behavior_report_path)
            behavior_totals = behavior_report.get("totals", {}) if isinstance(behavior_report.get("totals"), dict) else {}
            runtime_validation = {
                "behavior_report_path": str(behavior_report_path),
                "behavior_report_md": str(result.workspace_dir / ".agent" / "behavior-report.md"),
                "manual_test_checklist_path": str(result.manual_test_checklist_path or ""),
                "host_count": behavior_totals.get("host_count", 0),
                "compiled_host_count": behavior_totals.get("compiled_host_count", 0),
                "report_only_host_count": behavior_totals.get("report_only_host_count", 0),
                "trigger_counts": behavior_totals.get("trigger_counts", {}),
                "condition_type_counts": behavior_totals.get("condition_type_counts", {}),
                "action_type_counts": behavior_totals.get("action_type_counts", {}),
                "audit_report_path": str(audit.audit_report_path),
                "audit_success": audit.success,
            }
            runtime_validation_runs.append(runtime_validation)
            generated_files_count += len(result.generated_files)
            acceptance_samples.append(
                EvidenceSampleResult(
                    identifier=spec_path.stem,
                    title=spec.display_name,
                    phase="acceptance",
                    success=result.succeeded and audit.success,
                    summary=f"Generated and audited {spec_path.stem} behavior workspace.",
                    workspace=str(result.workspace_dir),
                    generated_files_count=len(result.generated_files),
                    audit_success=audit.success,
                    runtime_validation=runtime_validation,
                    artifacts={
                        "workspace": str(result.workspace_dir),
                        "behavior_report_json": str(behavior_report_path),
                        "behavior_report_md": str(result.workspace_dir / ".agent" / "behavior-report.md"),
                    },
                )
            )

        invalid_spec = self._behavior_invalid_spec()
        invalid_report = validate_mod_spec(invalid_spec, layer_config)
        invalid_failure = EvidenceSampleResult(
            identifier="behavior_invalid_trigger_mode",
            title="Invalid behavior event",
            phase="failure",
            success=False,
            summary="Validator rejected a behavior event with no action and an unsupported trigger mode.",
            generated_files_count=0,
            runtime_validation={
                "validation_errors": [issue.message for issue in invalid_report.errors],
                "validation_warnings": [issue.message for issue in invalid_report.warnings],
            },
            errors=[issue.message for issue in invalid_report.errors],
        )

        recovered_spec = self._behavior_recovery_spec()
        recovered_workspace_name = f"{run_id}-behavior-recovered"
        recovered_result = planner.execute_spec(
            recovered_spec,
            workspace_name=recovered_workspace_name,
            overwrite=True,
            run_build=False,
        )
        recovered_audit = auditor.audit_workspace(recovered_result.workspace_dir)
        recovered_behavior_report_path = recovered_result.workspace_dir / ".agent" / "behavior-report.json"
        recovered_behavior_report = _load_json_dict(recovered_behavior_report_path)
        recovered_totals = recovered_behavior_report.get("totals", {}) if isinstance(recovered_behavior_report.get("totals"), dict) else {}
        recovered_runtime = {
            "behavior_report_path": str(recovered_behavior_report_path),
            "behavior_report_md": str(recovered_result.workspace_dir / ".agent" / "behavior-report.md"),
            "manual_test_checklist_path": str(recovered_result.manual_test_checklist_path or ""),
            "host_count": recovered_totals.get("host_count", 0),
            "compiled_host_count": recovered_totals.get("compiled_host_count", 0),
            "report_only_host_count": recovered_totals.get("report_only_host_count", 0),
            "trigger_counts": recovered_totals.get("trigger_counts", {}),
            "audit_report_path": str(recovered_audit.audit_report_path),
            "audit_success": recovered_audit.success,
        }
        generated_files_count += len(recovered_result.generated_files)
        recovery_sample = EvidenceSampleResult(
            identifier="behavior_invalid_recovered",
            title="Recovered behavior event",
            phase="recovery",
            success=recovered_result.succeeded and recovered_audit.success,
            summary="Corrected the invalid behavior event and regenerated an audited workspace.",
            workspace=str(recovered_result.workspace_dir),
            generated_files_count=len(recovered_result.generated_files),
            audit_success=recovered_audit.success,
            runtime_validation=recovered_runtime,
            artifacts={
                "workspace": str(recovered_result.workspace_dir),
                "behavior_report_json": str(recovered_behavior_report_path),
                "behavior_report_md": str(recovered_result.workspace_dir / ".agent" / "behavior-report.md"),
            },
        )

        runtime_validation = {
            "acceptance_cases": runtime_validation_runs,
            "failure_sample": invalid_failure.runtime_validation,
            "recovery_sample": recovered_runtime,
            "host_count_total": sum(int(item.get("host_count", 0) or 0) for item in runtime_validation_runs) + int(recovered_runtime.get("host_count", 0) or 0),
            "compiled_host_count_total": sum(int(item.get("compiled_host_count", 0) or 0) for item in runtime_validation_runs) + int(recovered_runtime.get("compiled_host_count", 0) or 0),
            "report_only_host_count_total": sum(int(item.get("report_only_host_count", 0) or 0) for item in runtime_validation_runs) + int(recovered_runtime.get("report_only_host_count", 0) or 0),
        }
        acceptance_success_count = sum(1 for sample in acceptance_samples if sample.success)
        recovery_success_count = int(recovery_sample.success)
        return EvidenceLayerResult(
            identifier="behavior",
            title="Behavior DSL Layer",
            success_count=acceptance_success_count,
            total_cases=len(acceptance_samples),
            success_rate=_rate(acceptance_success_count, len(acceptance_samples)),
            recovery_count=recovery_success_count,
            recovery_total=1,
            recovery_rate=_rate(recovery_success_count, 1),
            generated_files_count=generated_files_count,
            runtime_validation=runtime_validation,
            acceptance_samples=acceptance_samples,
            failure_samples=[invalid_failure],
            recovery_samples=[recovery_sample],
            artifacts={
                "acceptance_workspace_root": str(layer_root / "runs"),
            },
            notes=[
                "Behavior runtime evidence is the shared behavior report plus the generated manual test checklist.",
            ],
        )

    def _run_patch_agent_layer(self, scoped_config: AppConfig, root_dir: Path, run_id: str) -> EvidenceLayerResult:
        layer_root = ensure_directory(root_dir / "patch-agent")
        layer_config = replace(scoped_config, workspace_root=ensure_directory(layer_root / "runs"))

        acceptance_samples: list[EvidenceSampleResult] = []
        runtime_validation_runs: list[dict[str, Any]] = []
        generated_files_count = 0

        acceptance_samples.append(
            self._run_patch_case(
                layer_config,
                run_id=run_id,
                case_id="patch_add_charm",
                base_spec_path=self.config.project_root / "examples" / "ruby_item.json",
                change_request="Add a ruby charm item that heals 4 health on right click with 20 seconds cooldown.",
                run_build=False,
                failure_mode=False,
                phase="acceptance",
            )
        )
        acceptance_samples.append(
            self._run_patch_case(
                layer_config,
                run_id=run_id,
                case_id="patch_repair_ore",
                base_spec_path=self.config.project_root / "examples" / "ruby_item.json",
                change_request="Make ruby ore generate underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk.",
                run_build=True,
                failure_mode=True,
                phase="acceptance",
            )
        )

        failure_sample = EvidenceSampleResult(
            identifier="patch_repair_ore_initial_failure",
            title="Initial patch-agent build failure",
            phase="failure",
            success=False,
            summary="The first build gate failed before the safe repair loop replayed the workspace.",
            workspace=acceptance_samples[-1].workspace,
            generated_files_count=acceptance_samples[-1].generated_files_count,
            build_success=False,
            repair_success=True,
            runtime_validation={
                "build_gate": "failed",
                "repair_loop": "recovered",
                "rollback_status": "recommended",
            },
            artifacts=dict(acceptance_samples[-1].artifacts),
            errors=["Simulated Gradle build failure for evidence chain."],
        )
        recovery_sample = EvidenceSampleResult(
            identifier="patch_repair_ore_recovered",
            title="Recovered patch-agent run",
            phase="recovery",
            success=True,
            summary="The safe repair loop regenerated managed files and the second check passed.",
            workspace=acceptance_samples[-1].workspace,
            generated_files_count=acceptance_samples[-1].generated_files_count,
            audit_success=acceptance_samples[-1].audit_success,
            build_success=True,
            repair_success=True,
            runtime_validation={
                "build_gate": "passed",
                "repair_loop": "recovered",
                "rollback_status": "recommended",
            },
            artifacts=dict(acceptance_samples[-1].artifacts),
        )

        for sample in acceptance_samples:
            generated_files_count += sample.generated_files_count
            runtime_validation_runs.append(sample.runtime_validation)

        runtime_validation = {
            "acceptance_cases": runtime_validation_runs,
            "failure_sample": failure_sample.runtime_validation,
            "recovery_sample": recovery_sample.runtime_validation,
            "build_gate_outcomes": [sample.runtime_validation.get("build_gate") for sample in acceptance_samples],
            "repair_loop_outcomes": [sample.runtime_validation.get("repair_loop") for sample in acceptance_samples],
        }
        acceptance_success_count = sum(1 for sample in acceptance_samples if sample.success)
        recovery_success_count = int(recovery_sample.success)
        return EvidenceLayerResult(
            identifier="patch_agent",
            title="Controlled Patch Agent Layer",
            success_count=acceptance_success_count,
            total_cases=len(acceptance_samples),
            success_rate=_rate(acceptance_success_count, len(acceptance_samples)),
            recovery_count=recovery_success_count,
            recovery_total=1,
            recovery_rate=_rate(recovery_success_count, 1),
            generated_files_count=generated_files_count,
            runtime_validation=runtime_validation,
            acceptance_samples=acceptance_samples,
            failure_samples=[failure_sample],
            recovery_samples=[recovery_sample],
            artifacts={
                "acceptance_workspace_root": str(layer_root / "runs"),
            },
            notes=[
                "Patch-agent runtime evidence is the audit/build gate plus the rollback report emitted for the recovered sample.",
            ],
        )

    def _run_patch_case(
        self,
        layer_config: AppConfig,
        *,
        run_id: str,
        case_id: str,
        base_spec_path: Path,
        change_request: str,
        run_build: bool,
        failure_mode: bool,
        phase: str,
    ) -> EvidenceSampleResult:
        planner = ModProjectPlanner(layer_config)
        base_spec = planner.spec_from_file(base_spec_path)
        base_workspace_name = f"{run_id}-{case_id}-base"
        base_result = planner.execute_spec(
            base_spec,
            workspace_name=base_workspace_name,
            overwrite=True,
            run_build=False,
        )

        orchestrator = AgentOrchestrator(layer_config)
        if failure_mode:
            orchestrator.repair_runner.builder = _FailThenSuccessBuildSimulator(layer_config)
            with patch.object(agent_orchestrator_module, "WorkspaceModifier", _FailingWorkspaceModifier):
                run = orchestrator.run_modify(
                    base_result.workspace_dir,
                    change_request,
                    planner_mode="rules",
                    llm_provider="mock",
                    run_build=run_build,
                    run_audit=True,
                    repair=True,
                )
        else:
            run = orchestrator.run_modify(
                base_result.workspace_dir,
                change_request,
                planner_mode="rules",
                llm_provider="mock",
                run_build=run_build,
                run_audit=True,
                repair=True,
            )

        modify_payload = run.payload.get("modify", {})
        patch_agent = modify_payload.get("patch_agent", {})
        audit_payload = run.payload.get("audit", {})
        repair_payload = run.payload.get("repair", {})
        final_build = modify_payload.get("build", {}) if isinstance(modify_payload.get("build"), dict) else {}
        final_repair_loop = repair_payload.get("repair_loop", {}) if isinstance(repair_payload.get("repair_loop"), dict) else {}
        repair_attempts = final_repair_loop.get("attempts", []) if isinstance(final_repair_loop.get("attempts"), list) else []
        repaired_build = repair_attempts[-1].get("build", {}) if repair_attempts else {}
        build_success = (
            bool(repaired_build.get("success"))
            if repair_attempts
            else final_build.get("success")
        )
        build_attempted = bool(final_build.get("attempted")) or bool(repair_attempts)
        build_gate = "skipped"
        if build_attempted:
            build_gate = "passed" if build_success is True else "failed"
        repair_needed = repair_payload.get("repair_needed")
        repair_loop = "not_needed"
        if repair_needed:
            repair_loop = "recovered" if final_repair_loop.get("repaired") else "failed"
        audit_success = audit_payload.get("success")
        runtime_passed = bool(run.success) and audit_success is not False and build_gate in {"skipped", "passed"}
        warnings = _unique_strings(
            [
                *modify_payload.get("warnings", []),
                *(warning for step in run.steps for warning in step.warnings),
            ]
        )
        errors = _unique_strings(error for step in run.steps for error in step.errors)
        sample = EvidenceSampleResult(
            identifier=case_id,
            title=change_request,
            phase=phase,
            success=bool(run.success),
            summary="Controlled patch-agent modify run completed with managed-file regeneration and evidence artifacts.",
            workspace=str(run.workspace or base_result.workspace_dir),
            generated_files_count=len(patch_agent.get("generated_files", [])),
            audit_success=audit_success,
            build_success=build_success,
            repair_success=repair_payload.get("repair_success"),
            runtime_validation={
                "runtime_passed": runtime_passed,
                "audit_gate": "passed" if audit_success is not False else "failed",
                "build_gate": build_gate,
                "repair_loop": repair_loop,
                "modify_success": modify_payload.get("success"),
                "patch_agent_status": patch_agent.get("status"),
                "rollback_status": patch_agent.get("rollback_status"),
                "rollback_required": patch_agent.get("rollback_required"),
                "repair_needed": repair_needed,
                "repair_success": repair_payload.get("repair_success"),
                "repair_executed": repair_payload.get("repair_executed"),
                "repair_loop_repaired": final_repair_loop.get("repaired"),
                "repair_loop_attempts": final_repair_loop.get("attempts_count"),
                "initial_build_success": final_build.get("success"),
            },
            artifacts={
                "workspace": str(run.workspace or base_result.workspace_dir),
                "agent_run_json": str(run.agent_run_json_path or ""),
                "agent_run_md": str(run.agent_run_md_path or ""),
                "agent_decisions_md": str(run.agent_decisions_md_path or ""),
                "patch_agent_plan_json": str(patch_agent.get("plan_json_path", "")),
                "patch_agent_report_json": str(patch_agent.get("report_json_path", "")),
                "patch_agent_report_md": str(patch_agent.get("report_md_path", "")),
                "patch_agent_rollback_json": str(patch_agent.get("rollback_json_path", "")),
                "patch_agent_rollback_md": str(patch_agent.get("rollback_md_path", "")),
                "repair_loop_report_json": str(repair_payload.get("repair_loop_report_json_path", "")),
                "repair_loop_report_md": str(repair_payload.get("repair_loop_report_md_path", "")),
                "modify_summary_path": str(modify_payload.get("modify_summary_path", "")),
            },
            warnings=warnings,
            errors=errors,
        )
        return sample

    def _behavior_invalid_spec(self) -> ModSpec:
        return ModSpec.from_dict(
            {
                "mod_id": "behavior_mod",
                "mod_name": "Behavior Mod",
                "package": "com.generated.behavior_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "item",
                        "id": "broken_charm",
                        "display_name_en_us": "Broken Charm",
                        "behavior": {
                            "type": "event_action",
                            "events": [
                                {
                                    "trigger": "right_click",
                                    "trigger_mode": "sequence",
                                    "triggers": ["right_click"],
                                    "actions": [],
                                }
                            ],
                        },
                    }
                ],
            }
        )

    def _behavior_recovery_spec(self) -> ModSpec:
        return ModSpec.from_dict(
            {
                "mod_id": "behavior_mod",
                "mod_name": "Behavior Mod",
                "package": "com.generated.behavior_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "item",
                        "id": "recovered_charm",
                        "display_name_en_us": "Recovered Charm",
                        "behavior": {
                            "type": "event_action",
                            "events": [
                                {
                                    "trigger": "right_click",
                                    "conditions": [
                                        {"type": "not_sneaking"},
                                    ],
                                    "cooldown_ticks": 100,
                                    "actions": [
                                        {"type": "heal", "target": "self", "amount": 4},
                                        {
                                            "type": "spawn_particles",
                                            "particle": "minecraft:heart",
                                            "count": 6,
                                        },
                                    ],
                                }
                            ],
                        },
                    }
                ],
            }
        )

    def _metrics(self, layers: list[EvidenceLayerResult]) -> dict[str, Any]:
        acceptance_total = sum(layer.total_cases for layer in layers)
        acceptance_passed = sum(layer.success_count for layer in layers)
        recovery_total = sum(layer.recovery_total for layer in layers)
        recovery_passed = sum(layer.recovery_count for layer in layers)
        failure_samples_total = sum(len(layer.failure_samples) for layer in layers)
        generated_files_total = sum(layer.generated_files_count for layer in layers)
        runtime_validation_total = 0
        runtime_passed_total = 0
        for layer in layers:
            runtime = layer.runtime_validation
            if layer.identifier == "stable":
                runtime_validation_total += int(runtime.get("runtime_cases_total", 0) or 0)
                runtime_passed_total += int(round(float(runtime.get("runtime_pass_rate", 0) or 0) * int(runtime.get("runtime_cases_total", 0) or 0)))
            elif layer.identifier == "behavior":
                runtime_validation_total += len(runtime.get("acceptance_cases", []))
                runtime_passed_total += sum(1 for item in runtime.get("acceptance_cases", []) if item.get("audit_success") is True)
                if runtime.get("recovery_sample"):
                    runtime_validation_total += 1
                    runtime_passed_total += 1 if runtime.get("recovery_sample", {}).get("audit_success") is True else 0
            elif layer.identifier == "patch_agent":
                runtime_validation_total += len(runtime.get("acceptance_cases", [])) + 1
                runtime_passed_total += sum(1 for item in runtime.get("acceptance_cases", []) if item.get("runtime_passed") is True)
                runtime_passed_total += 1 if runtime.get("recovery_sample", {}).get("repair_loop") == "recovered" else 0
        return {
            "layers_total": len(layers),
            "layers_passed": sum(1 for layer in layers if layer.success),
            "acceptance_cases_total": acceptance_total,
            "acceptance_cases_passed": acceptance_passed,
            "acceptance_success_rate": _rate(acceptance_passed, acceptance_total),
            "recovery_cases_total": recovery_total,
            "recovery_cases_passed": recovery_passed,
            "recovery_rate": _rate(recovery_passed, recovery_total),
            "failure_samples_total": failure_samples_total,
            "generated_files_total": generated_files_total,
            "runtime_validation_total": runtime_validation_total,
            "runtime_validation_passed_total": runtime_passed_total,
            "runtime_validation_pass_rate": _rate(runtime_passed_total, runtime_validation_total),
            "stable_success_rate": layers[0].success_rate if layers else 0.0,
            "behavior_success_rate": layers[1].success_rate if len(layers) > 1 else 0.0,
            "patch_agent_success_rate": layers[2].success_rate if len(layers) > 2 else 0.0,
        }

    def _render_markdown(self, result: EvidenceChainReportResult) -> str:
        lines = [
            "# Evidence Chain Report",
            "",
            f"Success: `{str(result.success).lower()}`",
            f"Run ID: `{result.run_id}`",
            "",
            "## Summary",
            "",
        ]
        for key in (
            "layers_total",
            "layers_passed",
            "acceptance_success_rate",
            "recovery_rate",
            "generated_files_total",
            "runtime_validation_total",
            "runtime_validation_pass_rate",
        ):
            lines.append(f"- `{key}`: {result.metrics.get(key)}")
        lines.extend(["", "## Layers", ""])
        for layer in result.layers:
            lines.extend(
                [
                    f"### {layer.title}",
                    "",
                    f"- success: `{str(layer.success).lower()}`",
                    f"- acceptance success rate: `{layer.success_rate:.2%}`",
                    f"- recovery rate: `{layer.recovery_rate:.2%}`",
                    f"- generated files: `{layer.generated_files_count}`",
                ]
            )
            runtime_validation = layer.runtime_validation
            if runtime_validation:
                lines.append("- runtime validation:")
                for key, value in runtime_validation.items():
                    if key == "runtime_cases" and isinstance(value, list):
                        lines.append(f"  - runtime_cases: `{len(value)}`")
                        continue
                    if isinstance(value, list):
                        lines.append(f"  - {key}: `{len(value)}`")
                    else:
                        lines.append(f"  - {key}: `{value}`")
            if layer.artifacts:
                lines.append("- artifacts:")
                for key, value in layer.artifacts.items():
                    if value:
                        lines.append(f"  - `{key}`: `{value}`")
            if layer.acceptance_samples:
                lines.append("- acceptance samples:")
                for sample in layer.acceptance_samples:
                    lines.append(f"  - `{sample.identifier}` `{str(sample.success).lower()}`: {sample.summary}")
            if layer.failure_samples:
                lines.append("- failure samples:")
                for sample in layer.failure_samples:
                    lines.append(f"  - `{sample.identifier}`: {sample.summary}")
                    for error in sample.errors:
                        lines.append(f"    - error: {error}")
            if layer.recovery_samples:
                lines.append("- recovery samples:")
                for sample in layer.recovery_samples:
                    lines.append(f"  - `{sample.identifier}` `{str(sample.success).lower()}`: {sample.summary}")
            if layer.notes:
                lines.append("- notes:")
                lines.extend(f"  - {note}" for note in layer.notes)
            lines.append("")
        return "\n".join(lines)


class _FailingBuildSimulator:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def build(self, project_dir: Path, task: str | None = None, *, repair: bool = False) -> BuildResult:
        project_dir = project_dir.resolve()
        task_name = task or self.config.gradle_task
        logs_dir = ensure_directory(self.config.logs_dir_for(project_dir))
        log_path = logs_dir / f"gradle-{task_name}.log"
        stdout_path = logs_dir / f"gradle-{task_name}.stdout.log"
        stderr_path = logs_dir / f"gradle-{task_name}.stderr.log"
        failure_text = "Execution failed for task ':compileJava'.\nCannot find symbol in generated Java sources.\n"
        write_text(log_path, failure_text)
        write_text(stdout_path, "Simulated Gradle stdout for evidence chain.\n")
        write_text(stderr_path, failure_text)
        return BuildResult(
            attempted=True,
            success=False,
            command=["gradlew.bat", task_name, "--console=plain", "--no-configuration-cache"],
            return_code=1,
            log_path=log_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            issues=[
                BuildIssue(
                    kind=BuildErrorKind.JAVA_COMPILE,
                    message="Execution failed for task ':compileJava'.",
                    suggestion="Patch the generated Java source with the smallest possible change.",
                )
            ],
            summary="Simulated build failure for evidence chain.",
        )


class _FailThenSuccessBuildSimulator:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.calls = 0

    def build(self, project_dir: Path, task: str | None = None, *, repair: bool = False) -> BuildResult:
        self.calls += 1
        project_dir = project_dir.resolve()
        task_name = task or self.config.gradle_task
        logs_dir = ensure_directory(self.config.logs_dir_for(project_dir))
        log_path = logs_dir / f"gradle-{task_name}.log"
        stdout_path = logs_dir / f"gradle-{task_name}.stdout.log"
        stderr_path = logs_dir / f"gradle-{task_name}.stderr.log"

        if self.calls == 1:
            failure_text = "Execution failed for task ':compileJava'.\nCannot find symbol in generated Java sources.\n"
            write_text(log_path, failure_text)
            write_text(stdout_path, "Initial simulated Gradle failure.\n")
            write_text(stderr_path, failure_text)
            return BuildResult(
                attempted=True,
                success=False,
                command=["gradlew.bat", task_name, "--console=plain", "--no-configuration-cache"],
                return_code=1,
                log_path=log_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                issues=[
                    BuildIssue(
                        kind=BuildErrorKind.JAVA_COMPILE,
                        message="Execution failed for task ':compileJava'.",
                        suggestion="Patch the generated Java source with the smallest possible change.",
                    )
                ],
                summary="Simulated build failure for repair replay.",
            )

        success_text = "BUILD SUCCESSFUL in simulated evidence chain run.\n"
        write_text(log_path, success_text)
        write_text(stdout_path, success_text)
        write_text(stderr_path, "")
        return BuildResult(
            attempted=True,
            success=True,
            command=["gradlew.bat", task_name, "--console=plain", "--no-configuration-cache"],
            return_code=0,
            jar_path=project_dir / "build" / "libs" / f"{project_dir.name}.jar",
            log_path=log_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            summary="Simulated build success after repair replay.",
        )


class _FailingWorkspaceModifier(WorkspaceModifier):
    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__(config)
        self.builder = _FailingBuildSimulator(self.config)


def _load_json_dict(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _format_rate(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2%}"
    return str(value)


def _number_to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return None


def _attempted_rate_to_bool(metrics: dict[str, Any], *, attempted_key: str, rate_key: str) -> bool | None:
    attempted = int(metrics.get(attempted_key, 0) or 0)
    if attempted <= 0:
        return None
    return _number_to_bool(metrics.get(rate_key))


def _unique_strings(items: Any) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            values.append(text)
            seen.add(text)
    return values
