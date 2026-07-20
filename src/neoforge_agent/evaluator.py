from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent_orchestrator import AgentOrchestrator
from .config import AppConfig
from .models import RequestOverrides
from .semantic_coverage import evaluate_semantic_coverage, normalize_category as _normalize_category
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class EvalModifyStep:
    identifier: str
    request: str
    repeat_request: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "request": self.request,
            "repeat_request": self.repeat_request,
        }


@dataclass(slots=True)
class EvalCase:
    identifier: str
    mode: str
    request: str
    setup_request: str | None = None
    expected_features: list[str] = field(default_factory=list)
    expected_categories: list[str] = field(default_factory=list)
    repeat_request: bool = False
    modify_steps: list[EvalModifyStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "mode": self.mode,
            "request": self.request,
            "setup_request": self.setup_request,
            "expected_features": list(self.expected_features),
            "expected_categories": list(self.expected_categories),
            "repeat_request": self.repeat_request,
            "modify_steps": [step.to_dict() for step in self.modify_steps],
        }


@dataclass(slots=True)
class EvalCaseResult:
    identifier: str
    mode: str
    request: str
    success: bool
    workspace: str | None = None
    expected_features: list[str] = field(default_factory=list)
    matched_expected_features: list[str] = field(default_factory=list)
    missing_expected_features: list[str] = field(default_factory=list)
    expected_categories: list[str] = field(default_factory=list)
    matched_expected_categories: list[str] = field(default_factory=list)
    missing_expected_categories: list[str] = field(default_factory=list)
    planning_success: bool = False
    audit_attempted: bool = False
    audit_success: bool | None = None
    build_attempted: bool = False
    build_success: bool | None = None
    generated_files_count: int = 0
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    agent_run_json_path: str | None = None
    agent_run_md_path: str | None = None
    agent_decisions_md_path: str | None = None
    prompt_trace_json_path: str | None = None
    agent_trace_summary_json_path: str | None = None
    agent_trace_present: bool = False
    agent_decisions_present: bool = False
    prompt_trace_present: bool = False
    agent_trace_summary_present: bool = False
    rag_hits_count: int = 0
    rag_categories: list[str] = field(default_factory=list)
    rag_capabilities: list[str] = field(default_factory=list)
    repeat_modify_success: bool | None = None
    repeat_modify_skipped: list[str] = field(default_factory=list)
    modify_llm_calls: int = 0
    modify_total_tokens: int = 0
    modify_max_input_tokens_per_call: int = 0
    modify_average_input_tokens_per_call: float = 0.0
    decomposed_modify_used: bool = False
    modify_context_compaction_ratio: float | None = None
    modify_step_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "mode": self.mode,
            "request": self.request,
            "success": self.success,
            "workspace": self.workspace,
            "expected_features": list(self.expected_features),
            "matched_expected_features": list(self.matched_expected_features),
            "missing_expected_features": list(self.missing_expected_features),
            "expected_categories": list(self.expected_categories),
            "matched_expected_categories": list(self.matched_expected_categories),
            "missing_expected_categories": list(self.missing_expected_categories),
            "planning_success": self.planning_success,
            "audit_attempted": self.audit_attempted,
            "audit_success": self.audit_success,
            "build_attempted": self.build_attempted,
            "build_success": self.build_success,
            "generated_files_count": self.generated_files_count,
            "added": list(self.added),
            "updated": list(self.updated),
            "skipped": list(self.skipped),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "agent_run_json_path": self.agent_run_json_path,
            "agent_run_md_path": self.agent_run_md_path,
            "agent_decisions_md_path": self.agent_decisions_md_path,
            "prompt_trace_json_path": self.prompt_trace_json_path,
            "agent_trace_summary_json_path": self.agent_trace_summary_json_path,
            "agent_trace_present": self.agent_trace_present,
            "agent_decisions_present": self.agent_decisions_present,
            "prompt_trace_present": self.prompt_trace_present,
            "agent_trace_summary_present": self.agent_trace_summary_present,
            "rag_hits_count": self.rag_hits_count,
            "rag_categories": list(self.rag_categories),
            "rag_capabilities": list(self.rag_capabilities),
            "repeat_modify_success": self.repeat_modify_success,
            "repeat_modify_skipped": list(self.repeat_modify_skipped),
            "modify_llm_calls": self.modify_llm_calls,
            "modify_total_tokens": self.modify_total_tokens,
            "modify_max_input_tokens_per_call": self.modify_max_input_tokens_per_call,
            "modify_average_input_tokens_per_call": self.modify_average_input_tokens_per_call,
            "decomposed_modify_used": self.decomposed_modify_used,
            "modify_context_compaction_ratio": self.modify_context_compaction_ratio,
            "modify_step_results": [dict(step) for step in self.modify_step_results],
        }


@dataclass(slots=True)
class EvalRunResult:
    success: bool
    run_id: str
    eval_dir: Path
    planner_mode: str
    llm_provider: str
    require_llm: bool
    build_enabled: bool
    audit_enabled: bool
    cases: list[EvalCaseResult]
    metrics: dict[str, Any]
    eval_report_json_path: Path
    eval_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "eval_dir": str(self.eval_dir),
            "planner_mode": self.planner_mode,
            "llm_provider": self.llm_provider,
            "require_llm": self.require_llm,
            "build_enabled": self.build_enabled,
            "audit_enabled": self.audit_enabled,
            "cases": [case.to_dict() for case in self.cases],
            "metrics": dict(self.metrics),
            "eval_report_json_path": str(self.eval_report_json_path),
            "eval_report_md_path": str(self.eval_report_md_path),
        }


class BenchmarkEvaluator:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        cases: list[EvalCase] | None = None,
        cases_path: Path | None = None,
        planner_mode: str = "llm",
        llm_provider: str = "mock",
        require_llm: bool = False,
        run_build: bool = False,
        run_audit: bool = True,
        run_name: str | None = None,
        limit: int | None = None,
    ) -> EvalRunResult:
        loaded_cases = cases or self._load_cases(cases_path)
        if limit is not None:
            loaded_cases = loaded_cases[: max(0, limit)]

        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        eval_dir = ensure_directory(self.config.workspace_root / "eval-runs" / run_id)
        eval_config = replace(self.config, workspace_root=eval_dir)
        orchestrator = AgentOrchestrator(eval_config)

        results: list[EvalCaseResult] = []
        for index, case in enumerate(loaded_cases, start=1):
            workspace_name = f"{index:02d}-{case.identifier}"
            try:
                if case.mode == "modify":
                    result = self._run_modify_case(
                        case,
                        orchestrator=orchestrator,
                        planner_mode=planner_mode,
                        llm_provider=llm_provider,
                        require_llm=require_llm,
                        run_build=run_build,
                        run_audit=run_audit,
                        workspace_name=workspace_name,
                    )
                else:
                    result = self._run_generate_case(
                        case,
                        orchestrator=orchestrator,
                        planner_mode=planner_mode,
                        llm_provider=llm_provider,
                        require_llm=require_llm,
                        run_build=run_build,
                        run_audit=run_audit,
                        workspace_name=workspace_name,
                    )
            except Exception as exc:  # Keep benchmark runs moving across failed cases.
                result = EvalCaseResult(
                    identifier=case.identifier,
                    mode=case.mode,
                    request=case.request,
                    success=False,
                    expected_features=list(case.expected_features),
                    missing_expected_features=list(case.expected_features),
                    errors=[f"{type(exc).__name__}: {exc}"],
                )
            results.append(result)

        metrics = self._compute_metrics(results)
        success = all(result.success for result in results)
        agent_dir = ensure_directory(eval_dir / ".agent")
        write_json(agent_dir / "eval-cases.json", [case.to_dict() for case in loaded_cases])
        report_json = agent_dir / "eval-report.json"
        report_md = agent_dir / "eval-report.md"
        run_result = EvalRunResult(
            success=success,
            run_id=run_id,
            eval_dir=eval_dir,
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            require_llm=require_llm,
            build_enabled=run_build,
            audit_enabled=run_audit,
            cases=results,
            metrics=metrics,
            eval_report_json_path=report_json,
            eval_report_md_path=report_md,
        )
        write_json(report_json, run_result.to_dict())
        write_text(report_md, self._render_report_md(run_result))
        return run_result

    def _run_generate_case(
        self,
        case: EvalCase,
        *,
        orchestrator: AgentOrchestrator,
        planner_mode: str,
        llm_provider: str,
        require_llm: bool,
        run_build: bool,
        run_audit: bool,
        workspace_name: str,
    ) -> EvalCaseResult:
        run = orchestrator.run_generate(
            case.request,
            overrides=RequestOverrides(),
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            require_llm=require_llm,
            workspace_name=workspace_name,
            overwrite=True,
            run_build=run_build,
            run_audit=run_audit,
            repair=True,
        )
        return self._case_result_from_agent(case, run.to_dict())

    def _run_modify_case(
        self,
        case: EvalCase,
        *,
        orchestrator: AgentOrchestrator,
        planner_mode: str,
        llm_provider: str,
        require_llm: bool,
        run_build: bool,
        run_audit: bool,
        workspace_name: str,
    ) -> EvalCaseResult:
        if not case.setup_request:
            raise ValueError(f"Modify eval case '{case.identifier}' is missing setup_request.")

        setup_run = orchestrator.run_generate(
            case.setup_request,
            overrides=RequestOverrides(),
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            require_llm=require_llm,
            workspace_name=f"{workspace_name}-base",
            overwrite=True,
            run_build=False,
            run_audit=True,
            repair=True,
        )
        if not setup_run.success or setup_run.workspace is None:
            result = self._case_result_from_agent(case, setup_run.to_dict())
            result.errors.append("Modify setup generation failed.")
            return result

        steps = case.modify_steps or [EvalModifyStep(identifier="modify", request=case.request, repeat_request=case.repeat_request)]
        step_results: list[EvalCaseResult] = []
        step_evidence_dirs: list[str | None] = []
        repeat_successes: list[bool] = []
        repeat_skipped: list[str] = []
        last_payload: dict[str, Any] | None = None

        for index, step in enumerate(steps, start=1):
            modify_run = orchestrator.run_modify(
                setup_run.workspace,
                step.request,
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                require_llm=require_llm,
                run_build=run_build,
                run_audit=run_audit,
                repair=True,
            )
            payload = modify_run.to_dict()
            last_payload = payload
            step_case = EvalCase(
                identifier=f"{case.identifier}:{step.identifier or index}",
                mode="modify",
                request=step.request,
            )
            step_result = self._case_result_from_agent(step_case, payload)
            step_results.append(step_result)
            step_evidence_dirs.append(self._snapshot_modify_step_evidence(setup_run.workspace, step.identifier or f"step_{index}"))

            should_repeat = step.repeat_request or (case.repeat_request and index == len(steps))
            if should_repeat:
                if step_result.success:
                    repeat_run = orchestrator.run_modify(
                        setup_run.workspace,
                        step.request,
                        planner_mode=planner_mode,
                        llm_provider=llm_provider,
                        require_llm=require_llm,
                        run_build=run_build,
                        run_audit=run_audit,
                        repair=True,
                    )
                    self._attach_repeat_modify_result(step_result, repeat_run.to_dict())
                    repeat_successes.append(bool(step_result.repeat_modify_success))
                    repeat_skipped.extend(step_result.repeat_modify_skipped)
                else:
                    step_result.repeat_modify_success = False
                    repeat_successes.append(False)

            if not step_result.success:
                break

        if last_payload is None:
            raise RuntimeError(f"Modify eval case '{case.identifier}' did not execute any modify step.")

        result = self._case_result_from_agent(case, last_payload)
        self._attach_modify_steps_result(result, step_results, step_evidence_dirs, repeat_successes, repeat_skipped)
        return result

    def _case_result_from_agent(self, case: EvalCase, payload: dict[str, Any]) -> EvalCaseResult:
        steps = payload.get("steps", [])
        planner_step = next((step for step in steps if step.get("role") == "planner_agent"), {})
        audit_payload = payload.get("payload", {}).get("audit", {})
        generation_payload = payload.get("payload", {}).get("generation", {})
        modify_payload = payload.get("payload", {}).get("modify", {})
        build_payload = generation_payload.get("build") or modify_payload.get("build") or {}

        warnings: list[str] = []
        errors: list[str] = []
        for step in steps:
            warnings.extend(str(item) for item in step.get("warnings", []))
            errors.extend(str(item) for item in step.get("errors", []))
        warnings = _unique_strings(warnings)
        errors = _unique_strings(errors)
        prompt_traces = payload.get("prompt_traces", [])
        rag_hits = [
            hit
            for trace in prompt_traces
            for hit in trace.get("rag_hits", [])
            if isinstance(hit, dict)
        ]
        rag_categories = sorted({str(hit.get("category", "")) for hit in rag_hits if hit.get("category")})
        rag_capabilities = sorted({str(hit.get("capability", hit.get("category", ""))) for hit in rag_hits if hit.get("capability") or hit.get("category")})

        result = EvalCaseResult(
            identifier=case.identifier,
            mode=case.mode,
            request=case.request,
            success=bool(payload.get("success")),
            workspace=payload.get("workspace"),
            expected_features=list(case.expected_features),
            expected_categories=list(case.expected_categories),
            planning_success=planner_step.get("status") == "pass",
            audit_attempted=bool(audit_payload.get("attempted")),
            audit_success=audit_payload.get("success"),
            build_attempted=bool(build_payload.get("attempted")),
            build_success=build_payload.get("success"),
            generated_files_count=len(generation_payload.get("generated_files", [])),
            added=list(modify_payload.get("added", [])),
            updated=list(modify_payload.get("updated", [])),
            skipped=list(modify_payload.get("skipped", [])),
            warnings=warnings,
            errors=errors,
            agent_run_json_path=payload.get("agent_run_json_path"),
            agent_run_md_path=payload.get("agent_run_md_path"),
            agent_decisions_md_path=payload.get("agent_decisions_md_path"),
            prompt_trace_json_path=payload.get("prompt_trace_json_path"),
            agent_trace_summary_json_path=payload.get("agent_trace_summary_json_path"),
            rag_hits_count=len(rag_hits),
            rag_categories=rag_categories,
            rag_capabilities=rag_capabilities,
            **self._modify_planner_metrics(case, payload, prompt_traces),
        )
        self._attach_agent_artifact_expectations(result)
        self._attach_semantic_expectations(result)
        return result

    def _attach_modify_steps_result(
        self,
        result: EvalCaseResult,
        step_results: list[EvalCaseResult],
        step_evidence_dirs: list[str | None],
        repeat_successes: list[bool],
        repeat_skipped: list[str],
    ) -> None:
        if not step_results:
            return
        result.modify_step_results = [
            {
                "id": step.identifier,
                "request": step.request,
                "success": step.success,
                "workspace": step.workspace,
                "added": list(step.added),
                "updated": list(step.updated),
                "skipped": list(step.skipped),
                "audit_attempted": step.audit_attempted,
                "audit_success": step.audit_success,
                "build_attempted": step.build_attempted,
                "build_success": step.build_success,
                "decomposed_modify_used": step.decomposed_modify_used,
                "modify_llm_calls": step.modify_llm_calls,
                "modify_total_tokens": step.modify_total_tokens,
                "modify_max_input_tokens_per_call": step.modify_max_input_tokens_per_call,
                "modify_context_compaction_ratio": step.modify_context_compaction_ratio,
                "evidence_dir": step_evidence_dirs[index] if index < len(step_evidence_dirs) else None,
                "repeat_modify_success": step.repeat_modify_success,
                "repeat_modify_skipped": list(step.repeat_modify_skipped),
                "errors": list(step.errors),
            }
            for index, step in enumerate(step_results)
        ]
        result.added = _unique_strings([item for step in step_results for item in step.added])
        result.updated = _unique_strings([item for step in step_results for item in step.updated])
        result.skipped = _unique_strings([item for step in step_results for item in step.skipped])
        result.warnings = _unique_strings([*result.warnings, *[item for step in step_results for item in step.warnings]])
        result.errors = _unique_strings([*result.errors, *[item for step in step_results for item in step.errors]])
        result.modify_llm_calls = sum(step.modify_llm_calls for step in step_results)
        result.modify_total_tokens = sum(step.modify_total_tokens for step in step_results)
        result.modify_max_input_tokens_per_call = max((step.modify_max_input_tokens_per_call for step in step_results), default=0)
        average_inputs = [step.modify_average_input_tokens_per_call for step in step_results if step.modify_average_input_tokens_per_call]
        result.modify_average_input_tokens_per_call = round(sum(average_inputs) / len(average_inputs), 2) if average_inputs else 0.0
        result.decomposed_modify_used = all(step.decomposed_modify_used for step in step_results)
        compaction_ratios = [step.modify_context_compaction_ratio for step in step_results if step.modify_context_compaction_ratio is not None]
        result.modify_context_compaction_ratio = round(sum(compaction_ratios) / len(compaction_ratios), 4) if compaction_ratios else None
        result.audit_attempted = any(step.audit_attempted for step in step_results)
        result.audit_success = all(step.audit_success is True for step in step_results if step.audit_attempted) if result.audit_attempted else None
        result.build_attempted = any(step.build_attempted for step in step_results)
        result.build_success = all(step.build_success is True for step in step_results if step.build_attempted) if result.build_attempted else None
        result.success = result.success and all(step.success for step in step_results)
        if repeat_successes:
            result.repeat_modify_success = all(repeat_successes)
            result.repeat_modify_skipped = _unique_strings(repeat_skipped)
            if not result.repeat_modify_success:
                result.success = False
                result.errors.append("At least one repeated modify step was not idempotent.")

    def _snapshot_modify_step_evidence(self, workspace: Path, step_identifier: str) -> str | None:
        agent_dir = self.config.agent_dir_for(workspace)
        if not agent_dir.exists():
            return None
        step_dir = ensure_directory(agent_dir / "eval-modify-steps" / _safe_step_identifier(step_identifier))
        for file_name in (
            "agent-run.json",
            "agent-run.md",
            "agent-decisions.md",
            "agent-trace-summary.json",
            "agent-trace-summary.md",
            "prompt-trace.json",
            "modify-summary.json",
            "modspec.before.json",
            "modspec.after.json",
            "patch-agent-plan.json",
            "patch-agent-report.json",
            "audit-report.json",
            "audit-report.md",
            "behavior-report.json",
            "progression-report.json",
        ):
            source = agent_dir / file_name
            if source.exists():
                shutil.copy2(source, step_dir / file_name)
        decomposed_dir = agent_dir / "decomposed-modify"
        if decomposed_dir.exists():
            target = step_dir / "decomposed-modify"
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(decomposed_dir, target)
        return str(step_dir)

    def _modify_planner_metrics(
        self,
        case: EvalCase,
        payload: dict[str, Any],
        prompt_traces: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if case.mode != "modify":
            return {}
        modify_payload = payload.get("payload", {}).get("modify", {})
        planner_used = ""
        if isinstance(modify_payload, dict):
            planner_used = str(modify_payload.get("planner_mode_used", ""))
        modify_traces = [
            trace
            for trace in prompt_traces
            if isinstance(trace, dict) and str(trace.get("prompt_kind", "")).startswith("modify")
        ]
        if not modify_traces:
            modify_traces = [
                trace
                for trace in prompt_traces
                if isinstance(trace, dict) and trace.get("role") == "planner_agent"
            ]
        calls = 0
        total_tokens = 0
        input_tokens: list[int] = []
        for trace in modify_traces:
            attempts = trace.get("completion_attempts") if isinstance(trace.get("completion_attempts"), list) else []
            if not attempts:
                attempts = [trace.get("completion_usage")] if isinstance(trace.get("completion_usage"), dict) else []
            for attempt in attempts:
                if not isinstance(attempt, dict):
                    continue
                usage = attempt.get("usage") if isinstance(attempt.get("usage"), dict) else {}
                if not usage:
                    continue
                calls += 1
                total_tokens += _int_metric(usage.get("total_tokens"))
                input_tokens.append(_int_metric(usage.get("input_tokens")))
        trace_modes = [
            str(trace.get("planner_mode", ""))
            for trace in modify_traces
            if isinstance(trace, dict)
        ]
        decomposed_used = planner_used == "decomposed" or any(mode == "modify:decomposed" for mode in trace_modes)
        compaction_ratio = self._modify_context_compaction_ratio(payload.get("workspace"), decomposed_used=decomposed_used)
        average_input = round(sum(input_tokens) / len(input_tokens), 2) if input_tokens else 0.0
        return {
            "modify_llm_calls": calls,
            "modify_total_tokens": total_tokens,
            "modify_max_input_tokens_per_call": max(input_tokens, default=0),
            "modify_average_input_tokens_per_call": average_input,
            "decomposed_modify_used": decomposed_used,
            "modify_context_compaction_ratio": compaction_ratio,
        }

    def _modify_context_compaction_ratio(self, workspace: str | None, *, decomposed_used: bool) -> float | None:
        if not workspace or not decomposed_used:
            return None
        workspace_path = Path(workspace)
        modspec_path = workspace_path / ".agent" / "modspec.before.json"
        context_path = workspace_path / ".agent" / "decomposed-modify" / "existing-context.json"
        if not modspec_path.exists() or not context_path.exists():
            return None
        try:
            modspec_len = len(modspec_path.read_text(encoding="utf-8"))
            context_len = len(context_path.read_text(encoding="utf-8"))
        except OSError:
            return None
        if modspec_len <= 0:
            return None
        return round(context_len / modspec_len, 4)

    def _attach_agent_artifact_expectations(self, result: EvalCaseResult) -> None:
        result.agent_trace_present = _path_exists(result.agent_run_json_path) and _path_exists(result.agent_run_md_path)
        result.agent_decisions_present = _path_exists(result.agent_decisions_md_path)
        result.prompt_trace_present = _path_exists(result.prompt_trace_json_path)
        result.agent_trace_summary_present = _path_exists(result.agent_trace_summary_json_path)

        missing = []
        if not result.agent_trace_present:
            missing.append("agent run json/md")
        if not result.agent_decisions_present:
            missing.append("agent decisions md")
        if not result.prompt_trace_present:
            missing.append("prompt trace json")
        if not result.agent_trace_summary_present:
            missing.append("agent trace summary json")
        if missing:
            result.success = False
            result.errors.append("Missing agent trace artifact(s): " + ", ".join(missing))

    def _attach_semantic_expectations(self, result: EvalCaseResult) -> None:
        coverage = evaluate_semantic_coverage(
            expected_features=result.expected_features,
            expected_categories=result.expected_categories,
            modspec=self._load_workspace_modspec(result.workspace),
            mode=result.mode,
            process_success=result.success,
            warnings=result.warnings,
        )
        result.matched_expected_features = coverage.matched_expected_features
        result.missing_expected_features = coverage.missing_expected_features
        result.matched_expected_categories = coverage.matched_expected_categories
        result.missing_expected_categories = coverage.missing_expected_categories
        if result.missing_expected_features:
            result.success = False
            result.errors.append(
                "Missing expected feature(s): " + ", ".join(result.missing_expected_features)
            )
        if result.missing_expected_categories:
            result.success = False
            result.errors.append(
                "Missing expected category/capability: "
                + ", ".join(result.missing_expected_categories)
            )

    def _attach_repeat_modify_result(self, result: EvalCaseResult, payload: dict[str, Any]) -> None:
        modify_payload = payload.get("payload", {}).get("modify", {})
        repeat_added = list(modify_payload.get("added", []))
        repeat_updated = list(modify_payload.get("updated", []))
        result.repeat_modify_skipped = list(modify_payload.get("skipped", []))
        result.repeat_modify_success = bool(payload.get("success")) and not repeat_added and not repeat_updated
        if not result.repeat_modify_success:
            result.success = False
            result.errors.append(
                "Repeat modify was not idempotent: "
                f"added={repeat_added}, updated={repeat_updated}, skipped={result.repeat_modify_skipped}"
            )

    def _load_workspace_modspec(self, workspace: str | None) -> dict[str, Any] | None:
        if not workspace:
            return None
        modspec_path = Path(workspace) / ".agent" / "modspec.json"
        if not modspec_path.exists():
            return None
        try:
            payload = json.loads(modspec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _load_cases(self, cases_path: Path | None) -> list[EvalCase]:
        if cases_path is None:
            return default_eval_cases()
        data = json.loads(cases_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("cases", [])
        if not isinstance(data, list):
            raise ValueError("Eval cases file must contain a list or an object with a 'cases' list.")
        return [_case_from_dict(item) for item in data if isinstance(item, dict)]

    def _compute_metrics(self, results: list[EvalCaseResult]) -> dict[str, Any]:
        total = len(results)
        planning_success = sum(1 for result in results if result.planning_success)
        audit_attempted = sum(1 for result in results if result.audit_attempted)
        audit_success = sum(1 for result in results if result.audit_success is True)
        build_attempted = sum(1 for result in results if result.build_attempted)
        build_success = sum(1 for result in results if result.build_success is True)
        success_count = sum(1 for result in results if result.success)
        generated_files_total = sum(result.generated_files_count for result in results)
        modify_cases = [result for result in results if result.mode == "modify"]
        modify_step_total = sum(len(result.modify_step_results) or (1 if result.mode == "modify" else 0) for result in modify_cases)
        multi_step_modify_cases = [result for result in modify_cases if len(result.modify_step_results) > 1]
        expected_total = sum(len(result.expected_features) for result in results)
        expected_matched = sum(len(result.matched_expected_features) for result in results)
        expectation_cases = [result for result in results if result.expected_features]
        expectation_success = sum(1 for result in expectation_cases if not result.missing_expected_features)
        category_total = sum(len(result.expected_categories) for result in results)
        category_matched = sum(len(result.matched_expected_categories) for result in results)
        category_cases = [result for result in results if result.expected_categories]
        category_success = sum(1 for result in category_cases if not result.missing_expected_categories)
        expected_category_set = sorted(
            {
                _normalize_category(category)
                for result in results
                for category in result.expected_categories
            }
        )
        matched_category_set = sorted(
            {
                _normalize_category(category)
                for result in results
                for category in result.matched_expected_categories
            }
        )
        missing_category_set = sorted(set(expected_category_set) - set(matched_category_set))
        trace_present = sum(1 for result in results if result.agent_trace_present)
        decisions_present = sum(1 for result in results if result.agent_decisions_present)
        prompt_trace_present = sum(1 for result in results if result.prompt_trace_present)
        trace_summary_present = sum(1 for result in results if result.agent_trace_summary_present)
        complete_trace = sum(
            1
            for result in results
            if result.agent_trace_present and result.agent_decisions_present and result.prompt_trace_present and result.agent_trace_summary_present
        )
        repeat_cases = [result for result in results if result.repeat_modify_success is not None]
        repeat_success = sum(1 for result in repeat_cases if result.repeat_modify_success)
        rag_hit_cases = sum(1 for result in results if result.rag_hits_count > 0)
        rag_hits_total = sum(result.rag_hits_count for result in results)
        rag_categories_covered = sorted({category for result in results for category in result.rag_categories})
        rag_capabilities_covered = sorted({capability for result in results for capability in result.rag_capabilities})
        modify_llm_calls_total = sum(result.modify_llm_calls for result in modify_cases)
        modify_total_tokens = sum(result.modify_total_tokens for result in modify_cases)
        modify_max_input = max((result.modify_max_input_tokens_per_call for result in modify_cases), default=0)
        modify_avg_inputs = [result.modify_average_input_tokens_per_call for result in modify_cases if result.modify_average_input_tokens_per_call]
        decomposed_modify_used = sum(1 for result in modify_cases if result.decomposed_modify_used)
        compaction_ratios = [
            result.modify_context_compaction_ratio
            for result in modify_cases
            if result.modify_context_compaction_ratio is not None
        ]
        return {
            "total_cases": total,
            "success_count": success_count,
            "success_rate": _rate(success_count, total),
            "feature_expectation_cases": len(expectation_cases),
            "feature_expectation_success_count": expectation_success,
            "feature_expectation_success_rate": _rate(expectation_success, len(expectation_cases)),
            "expected_features_total": expected_total,
            "expected_features_matched": expected_matched,
            "expected_feature_match_rate": _rate(expected_matched, expected_total),
            "category_expectation_cases": len(category_cases),
            "category_expectation_success_count": category_success,
            "category_expectation_success_rate": _rate(category_success, len(category_cases)),
            "expected_categories_total": category_total,
            "expected_categories_matched": category_matched,
            "expected_category_match_rate": _rate(category_matched, category_total),
            "content_categories_expected": expected_category_set,
            "content_categories_covered": matched_category_set,
            "content_categories_missing": missing_category_set,
            "content_coverage_rate": _rate(len(matched_category_set), len(expected_category_set)),
            "planning_success_count": planning_success,
            "planning_success_rate": _rate(planning_success, total),
            "audit_attempted_count": audit_attempted,
            "audit_success_count": audit_success,
            "audit_success_rate": _rate(audit_success, audit_attempted),
            "build_attempted_count": build_attempted,
            "build_success_count": build_success,
            "build_success_rate": _rate(build_success, build_attempted),
            "generated_files_total": generated_files_total,
            "average_generated_files": round(generated_files_total / total, 2) if total else 0,
            "modify_cases": len(modify_cases),
            "modify_step_total": modify_step_total,
            "multi_step_modify_cases": len(multi_step_modify_cases),
            "multi_step_modify_success_count": sum(1 for result in multi_step_modify_cases if result.success),
            "multi_step_modify_success_rate": _rate(sum(1 for result in multi_step_modify_cases if result.success), len(multi_step_modify_cases)),
            "modify_added_total": sum(len(result.added) for result in modify_cases),
            "modify_updated_total": sum(len(result.updated) for result in modify_cases),
            "modify_skipped_total": sum(len(result.skipped) for result in modify_cases),
            "modify_llm_calls_total": modify_llm_calls_total,
            "modify_total_tokens": modify_total_tokens,
            "modify_max_input_tokens_per_call": modify_max_input,
            "modify_average_input_tokens_per_call": round(sum(modify_avg_inputs) / len(modify_avg_inputs), 2) if modify_avg_inputs else 0,
            "decomposed_modify_used_count": decomposed_modify_used,
            "decomposed_modify_used_rate": _rate(decomposed_modify_used, len(modify_cases)),
            "modify_context_compaction_ratio": round(sum(compaction_ratios) / len(compaction_ratios), 4) if compaction_ratios else None,
            "agent_trace_present_count": trace_present,
            "agent_trace_present_rate": _rate(trace_present, total),
            "agent_decisions_present_count": decisions_present,
            "agent_decisions_present_rate": _rate(decisions_present, total),
            "prompt_trace_present_count": prompt_trace_present,
            "prompt_trace_present_rate": _rate(prompt_trace_present, total),
            "agent_trace_summary_present_count": trace_summary_present,
            "agent_trace_summary_present_rate": _rate(trace_summary_present, total),
            "agent_artifacts_complete_count": complete_trace,
            "agent_artifacts_complete_rate": _rate(complete_trace, total),
            "rag_hit_cases": rag_hit_cases,
            "rag_hit_rate": _rate(rag_hit_cases, total),
            "rag_hits_total": rag_hits_total,
            "average_rag_hits": round(rag_hits_total / total, 2) if total else 0,
            "rag_categories_covered": rag_categories_covered,
            "rag_capabilities_covered": rag_capabilities_covered,
            "repeat_modify_cases": len(repeat_cases),
            "repeat_modify_success_count": repeat_success,
            "repeat_modify_success_rate": _rate(repeat_success, len(repeat_cases)),
        }

    def _render_report_md(self, result: EvalRunResult) -> str:
        lines = [
            "# Eval Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Run ID: `{result.run_id}`",
            f"Planner: `{result.planner_mode}`",
            f"LLM provider: `{result.llm_provider}`",
            f"Require LLM: {str(result.require_llm).lower()}",
            f"Build enabled: {str(result.build_enabled).lower()}",
            f"Audit enabled: {str(result.audit_enabled).lower()}",
            "",
            "## Metrics",
            "",
        ]
        for key, value in result.metrics.items():
            lines.append(f"- `{key}`: {value}")
        lines.extend(["", "## Cases", ""])
        for case in result.cases:
            lines.append(f"- `{case.identifier}` `{case.mode}`: {'pass' if case.success else 'fail'}")
            if case.workspace:
                lines.append(f"  - workspace: `{case.workspace}`")
            if case.added or case.updated or case.skipped:
                lines.append(
                    f"  - merge: added={len(case.added)}, updated={len(case.updated)}, skipped={len(case.skipped)}"
                )
            if case.modify_step_results:
                lines.append(f"  - modify steps: {len(case.modify_step_results)}")
                for step in case.modify_step_results:
                    lines.append(
                        "    - "
                        f"`{step.get('id')}`: {'pass' if step.get('success') else 'fail'}, "
                        f"added={len(step.get('added', []))}, "
                        f"updated={len(step.get('updated', []))}, "
                        f"skipped={len(step.get('skipped', []))}, "
                        f"decomposed={str(step.get('decomposed_modify_used')).lower()}"
                    )
            if case.expected_features:
                lines.append(
                    "  - expected features: "
                    f"matched={len(case.matched_expected_features)}/{len(case.expected_features)}"
                )
            if case.expected_categories:
                lines.append(
                    "  - expected categories: "
                    f"matched={len(case.matched_expected_categories)}/{len(case.expected_categories)}"
                )
            lines.append(
                "  - agent artifacts: "
                f"run={str(case.agent_trace_present).lower()}, "
                f"decisions={str(case.agent_decisions_present).lower()}, "
                f"prompt_trace={str(case.prompt_trace_present).lower()}, "
                f"trace_summary={str(case.agent_trace_summary_present).lower()}"
            )
            lines.append(
                "  - rag: "
                f"hits={case.rag_hits_count}, "
                f"categories={', '.join(case.rag_categories) or 'none'}, "
                f"capabilities={', '.join(case.rag_capabilities) or 'none'}"
            )
            if case.repeat_modify_success is not None:
                lines.append(
                    "  - repeat modify: "
                    f"success={str(case.repeat_modify_success).lower()}, "
                    f"skipped={len(case.repeat_modify_skipped)}"
                )
            if case.missing_expected_features:
                lines.append(f"  - missing: {', '.join(case.missing_expected_features)}")
            if case.missing_expected_categories:
                lines.append(f"  - missing categories: {', '.join(case.missing_expected_categories)}")
            for error in case.errors:
                lines.append(f"  - error: {error}")
        lines.append("")
        return "\n".join(lines)


def default_eval_cases() -> list[EvalCase]:
    return [
        EvalCase(
            identifier="basic_ruby",
            mode="generate",
            request="Create a ruby mod with ruby.",
            expected_features=["ruby"],
            expected_categories=["item"],
        ),
        EvalCase(
            identifier="ruby_charm_behavior",
            mode="generate",
            request="Create a ruby mod with a ruby charm item.",
            expected_features=["ruby_charm"],
            expected_categories=["item", "behavior", "right_click_heal"],
        ),
        EvalCase(
            identifier="speed_crystal_behavior",
            mode="generate",
            request="Create a speed crystal item that grants speed II for 10 seconds.",
            expected_features=["speed_crystal"],
            expected_categories=["item", "behavior", "right_click_effect"],
        ),
        EvalCase(
            identifier="ruby_apple_effect",
            mode="generate",
            request="Create a ruby apple that grants regeneration II for 5 seconds.",
            expected_features=["ruby_apple"],
            expected_categories=["food", "behavior", "food_effect"],
        ),
        EvalCase(
            identifier="ruby_sword_ignite",
            mode="generate",
            request="Create a ruby sword that ignites enemies for 5 seconds.",
            expected_features=["ruby_sword"],
            expected_categories=["sword", "behavior", "sword_ignite"],
        ),
        EvalCase(
            identifier="ruby_pickaxe_tool",
            mode="generate",
            request="Create a ruby mod with ruby pickaxe.",
            expected_features=["ruby_pickaxe"],
            expected_categories=["tool"],
        ),
        EvalCase(
            identifier="ruby_tool_set",
            mode="generate",
            request="Create a ruby mod with ruby tool set.",
            expected_features=["ruby_sword", "ruby_pickaxe", "ruby_axe", "ruby_shovel", "ruby_hoe"],
            expected_categories=["item", "sword", "tool", "recipe"],
        ),
        EvalCase(
            identifier="ruby_armor_set",
            mode="generate",
            request="Create a ruby mod with ruby armor set.",
            expected_features=["ruby_helmet", "ruby_chestplate", "ruby_leggings", "ruby_boots"],
            expected_categories=["item", "armor", "recipe"],
        ),
        EvalCase(
            identifier="ruby_block_variants",
            mode="generate",
            request="Create a ruby mod with ruby block variants.",
            expected_features=["ruby_block", "ruby_stairs", "ruby_slab", "ruby_wall", "ruby_button", "ruby_pressure_plate", "ruby_fence", "ruby_fence_gate", "ruby_door", "ruby_trapdoor"],
            expected_categories=["item", "block", "recipe", "block_variants", "interactive_blocks"],
        ),
        EvalCase(
            identifier="ruby_ore_worldgen",
            mode="generate",
            request="Create a ruby mod where ruby ore generates underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk.",
            expected_features=["ruby", "ruby_ore"],
            expected_categories=["item", "ore", "worldgen"],
        ),
        EvalCase(
            identifier="modify_add_behavior",
            mode="modify",
            setup_request="Create a ruby mod with ruby.",
            request="Add a ruby charm item that heals 4 health on right click with 20 seconds cooldown.",
            expected_features=["ruby_charm"],
            expected_categories=["item", "behavior", "right_click_heal", "modify"],
            repeat_request=True,
        ),
        EvalCase(
            identifier="modify_ore_worldgen",
            mode="modify",
            setup_request="Create a ruby mod with ruby and ruby ore.",
            request="Make ruby ore generate underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk.",
            expected_features=["ruby_ore"],
            expected_categories=["ore", "worldgen", "modify"],
            repeat_request=True,
        ),
    ]


def _case_from_dict(data: dict[str, Any]) -> EvalCase:
    raw_modify_steps = data.get("modify_steps") or []
    modify_steps = [_modify_step_from_dict(item, index) for index, item in enumerate(raw_modify_steps, start=1)]
    return EvalCase(
        identifier=str(data.get("id", data.get("identifier", "eval_case"))),
        mode=str(data.get("mode", "generate")).lower(),
        request=str(data.get("request", "")),
        setup_request=str(data["setup_request"]) if data.get("setup_request") is not None else None,
        expected_features=[str(item) for item in data.get("expected_features", [])],
        expected_categories=[str(item) for item in data.get("expected_categories", [])],
        repeat_request=bool(data.get("repeat_request", False)),
        modify_steps=modify_steps,
    )


def _modify_step_from_dict(data: Any, index: int) -> EvalModifyStep:
    if isinstance(data, str):
        return EvalModifyStep(identifier=f"step_{index}", request=data)
    if isinstance(data, dict):
        return EvalModifyStep(
            identifier=str(data.get("id", data.get("identifier", f"step_{index}"))),
            request=str(data.get("request", "")),
            repeat_request=bool(data.get("repeat_request", False)),
        )
    return EvalModifyStep(identifier=f"step_{index}", request=str(data))


def _safe_step_identifier(value: str) -> str:
    normalized = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value.strip().lower())
    normalized = "-".join(part for part in normalized.split("-") if part)
    return normalized or "step"


def _path_exists(value: str | None) -> bool:
    return bool(value) and Path(value).exists()


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _int_metric(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
