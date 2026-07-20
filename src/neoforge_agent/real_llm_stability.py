from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent_orchestrator import AgentOrchestrator
from .config import AppConfig
from .evaluator import EvalCase, default_eval_cases
from .llm_client import check_llm_provider_health, inspect_llm_provider_config
from .manual_runtime_evidence import (
    ManualRuntimeEvidenceCase as RealLLMRuntimeEvidenceCase,
    load_manual_runtime_evidence_cases,
)
from .models import RequestOverrides
from .semantic_coverage import evaluate_semantic_coverage
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class RealLLMStabilityCaseResult:
    identifier: str
    request: str
    outcome: str
    strict_success: bool
    real_llm_success: bool
    fallback_used: bool
    fallback_success: bool
    failure_type: str | None = None
    workspace: str | None = None
    fallback_workspace: str | None = None
    planner_mode_used: str = ""
    provider: str = ""
    model: str = ""
    audit_attempted: bool = False
    audit_success: bool | None = None
    build_attempted: bool = False
    build_success: bool | None = None
    runtime_checked: bool = False
    runtime_success: bool | None = None
    runtime_status: str = "not_checked"
    runtime_evidence_source: str | None = None
    runtime_evidence_notes: str = ""
    retry_attempts: int = 0
    schema_retry_attempts: int = 0
    json_repair_applied: bool = False
    latency_ms: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    prompt_trace_present: bool = False
    agent_run_json_path: str | None = None
    prompt_trace_json_path: str | None = None
    diagnostic_dir: str | None = None
    raw_output_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    fallback_errors: list[str] = field(default_factory=list)
    expected_features: list[str] = field(default_factory=list)
    matched_expected_features: list[str] = field(default_factory=list)
    missing_expected_features: list[str] = field(default_factory=list)
    expected_categories: list[str] = field(default_factory=list)
    matched_expected_categories: list[str] = field(default_factory=list)
    missing_expected_categories: list[str] = field(default_factory=list)
    semantic_success: bool = False
    ignored_feature_warnings: list[str] = field(default_factory=list)
    removed_behavior_warnings: list[str] = field(default_factory=list)
    semantic_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "request": self.request,
            "outcome": self.outcome,
            "strict_success": self.strict_success,
            "real_llm_success": self.real_llm_success,
            "fallback_used": self.fallback_used,
            "fallback_success": self.fallback_success,
            "failure_type": self.failure_type,
            "workspace": self.workspace,
            "fallback_workspace": self.fallback_workspace,
            "planner_mode_used": self.planner_mode_used,
            "provider": self.provider,
            "model": self.model,
            "audit_attempted": self.audit_attempted,
            "audit_success": self.audit_success,
            "build_attempted": self.build_attempted,
            "build_success": self.build_success,
            "runtime_checked": self.runtime_checked,
            "runtime_success": self.runtime_success,
            "runtime_status": self.runtime_status,
            "runtime_evidence_source": self.runtime_evidence_source,
            "runtime_evidence_notes": self.runtime_evidence_notes,
            "retry_attempts": self.retry_attempts,
            "schema_retry_attempts": self.schema_retry_attempts,
            "json_repair_applied": self.json_repair_applied,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "prompt_trace_present": self.prompt_trace_present,
            "agent_run_json_path": self.agent_run_json_path,
            "prompt_trace_json_path": self.prompt_trace_json_path,
            "diagnostic_dir": self.diagnostic_dir,
            "raw_output_path": self.raw_output_path,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "fallback_errors": list(self.fallback_errors),
            "expected_features": list(self.expected_features),
            "matched_expected_features": list(self.matched_expected_features),
            "missing_expected_features": list(self.missing_expected_features),
            "expected_categories": list(self.expected_categories),
            "matched_expected_categories": list(self.matched_expected_categories),
            "missing_expected_categories": list(self.missing_expected_categories),
            "semantic_success": self.semantic_success,
            "ignored_feature_warnings": list(self.ignored_feature_warnings),
            "removed_behavior_warnings": list(self.removed_behavior_warnings),
            "semantic_warnings": list(self.semantic_warnings),
        }


@dataclass(slots=True)
class RealLLMStabilityResult:
    success: bool
    run_id: str
    report_dir: Path
    llm_provider: str
    planner_mode: str
    provider_config: dict[str, Any]
    provider_health: dict[str, Any]
    run_build: bool
    run_audit: bool
    fallback_probe: bool
    require_runtime: bool
    runtime_evidence_path: str | None
    runtime_evidence_cases: list[RealLLMRuntimeEvidenceCase]
    cases: list[RealLLMStabilityCaseResult]
    metrics: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    real_llm_stability_json_path: Path
    real_llm_stability_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "llm_provider": self.llm_provider,
            "planner_mode": self.planner_mode,
            "provider_config": dict(self.provider_config),
            "provider_health": dict(self.provider_health),
            "run_build": self.run_build,
            "run_audit": self.run_audit,
            "fallback_probe": self.fallback_probe,
            "require_runtime": self.require_runtime,
            "runtime_evidence_path": self.runtime_evidence_path,
            "runtime_evidence_cases": [case.to_dict() for case in self.runtime_evidence_cases],
            "cases": [case.to_dict() for case in self.cases],
            "metrics": dict(self.metrics),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "warnings_count": len(self.warnings),
            "errors_count": len(self.errors),
            "real_llm_stability_json_path": str(self.real_llm_stability_json_path),
            "real_llm_stability_md_path": str(self.real_llm_stability_md_path),
        }


class RealLLMStabilityRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        cases_path: Path | None = None,
        limit: int | None = 10,
        llm_provider: str = "openai-compatible",
        planner_mode: str = "decomposed",
        run_build: bool = False,
        run_audit: bool = True,
        fallback_probe: bool = True,
        require_real: bool = False,
        runtime_evidence_path: Path | None = None,
        require_runtime: bool = False,
    ) -> RealLLMStabilityResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        root_dir = ensure_directory(self.config.workspace_root / "real-llm-stability-runs" / run_id)
        report_dir = ensure_directory(root_dir / ".agent")
        run_workspace_root = ensure_directory(root_dir / "runs")
        scoped_config = replace(self.config, workspace_root=run_workspace_root)

        provider_config = inspect_llm_provider_config(llm_provider).to_dict()
        provider_health = check_llm_provider_health(llm_provider).to_dict()
        cases = _load_generate_cases(cases_path)
        if limit is not None:
            cases = cases[: max(0, limit)]
        runtime_evidence_cases = load_manual_runtime_evidence_cases(runtime_evidence_path)

        warnings: list[str] = []
        errors: list[str] = []
        if runtime_evidence_path is not None and not runtime_evidence_path.exists():
            warnings.append(f"Runtime evidence path was not found: {runtime_evidence_path}")
        if llm_provider != "mock" and not provider_config.get("valid"):
            message = (
                f"Provider `{llm_provider}` is not configured; strict real LLM attempts will fail "
                "or be skipped by --require-llm preflight."
            )
            if require_real:
                errors.append(message)
            else:
                warnings.append(message)
        if require_runtime and not runtime_evidence_cases:
            errors.append(
                "Runtime evidence was required, but no runtime evidence cases were loaded. "
                "Pass --runtime-evidence with documented manual or automated runtime results."
            )

        orchestrator = AgentOrchestrator(scoped_config)
        results: list[RealLLMStabilityCaseResult] = []
        for index, case in enumerate(cases, start=1):
            results.append(
                self._run_case(
                    index,
                    case,
                    orchestrator=orchestrator,
                    llm_provider=llm_provider,
                    planner_mode=planner_mode,
                    run_build=run_build,
                    run_audit=run_audit,
                    fallback_probe=fallback_probe,
                    runtime_evidence_cases=runtime_evidence_cases,
                )
            )

        metrics = _compute_metrics(results)
        success = not errors
        if require_real:
            success = success and metrics["real_llm_success_count"] == metrics["total_cases"]
        if require_runtime:
            success = success and metrics["runtime_success_count"] == metrics["total_cases"]

        result = RealLLMStabilityResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            llm_provider=llm_provider,
            planner_mode=planner_mode,
            provider_config=provider_config,
            provider_health=provider_health,
            run_build=run_build,
            run_audit=run_audit,
            fallback_probe=fallback_probe,
            require_runtime=require_runtime,
            runtime_evidence_path=str(runtime_evidence_path) if runtime_evidence_path else None,
            runtime_evidence_cases=runtime_evidence_cases,
            cases=results,
            metrics=metrics,
            warnings=warnings,
            errors=errors,
            real_llm_stability_json_path=report_dir / "real-llm-stability.json",
            real_llm_stability_md_path=report_dir / "real-llm-stability.md",
        )
        write_json(result.real_llm_stability_json_path, result.to_dict())
        write_text(result.real_llm_stability_md_path, self._render_markdown(result))
        return result

    def _run_case(
        self,
        index: int,
        case: EvalCase,
        *,
        orchestrator: AgentOrchestrator,
        llm_provider: str,
        planner_mode: str,
        run_build: bool,
        run_audit: bool,
        fallback_probe: bool,
        runtime_evidence_cases: list[RealLLMRuntimeEvidenceCase],
    ) -> RealLLMStabilityCaseResult:
        workspace_name = f"{index:02d}-{case.identifier}-strict"
        try:
            strict_run = orchestrator.run_generate(
                case.request,
                overrides=RequestOverrides(),
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                workspace_name=workspace_name,
                overwrite=True,
                run_build=run_build,
                run_audit=run_audit,
                repair=True,
                require_llm=True,
            )
            strict_payload = strict_run.to_dict()
        except Exception as exc:  # noqa: BLE001 - stability reports should keep moving.
            strict_payload = {
                "success": False,
                "planner_mode": planner_mode,
                "llm_provider": llm_provider,
                "request": case.request,
                "errors": [f"{type(exc).__name__}: {exc}"],
            }

        result = _case_result_from_payload(case, strict_payload, llm_provider=llm_provider)
        if not result.strict_success and result.workspace is None:
            self._write_strict_failure_diagnostics(index, case, strict_payload, result, orchestrator=orchestrator)
        _attach_runtime_evidence(result, runtime_evidence_cases)
        if fallback_probe and not result.real_llm_success:
            fallback_payload = self._run_fallback_probe(
                index,
                case,
                orchestrator=orchestrator,
                llm_provider=llm_provider,
                planner_mode=planner_mode,
                run_build=run_build,
                run_audit=run_audit,
            )
            result.fallback_workspace = fallback_payload.get("workspace")
            result.fallback_used = _detect_fallback(fallback_payload)
            result.fallback_success = bool(fallback_payload.get("success")) and result.fallback_used
            result.fallback_errors = _payload_errors(fallback_payload)
            if result.fallback_success:
                result.outcome = "fallback_success"
            elif result.fallback_used:
                result.outcome = "fallback_failure"
        return result

    def _write_strict_failure_diagnostics(
        self,
        index: int,
        case: EvalCase,
        payload: dict[str, Any],
        result: RealLLMStabilityCaseResult,
        *,
        orchestrator: AgentOrchestrator,
    ) -> None:
        trace = _first_prompt_trace(payload)
        if not trace:
            return

        safe_id = "".join(char.lower() if char.isalnum() else "_" for char in case.identifier).strip("_")
        safe_id = safe_id or "case"
        diagnostic_dir = ensure_directory(
            orchestrator.config.workspace_root / f"{index:02d}-{safe_id}-strict-diagnostics" / ".agent"
        )
        prompt_trace_path = diagnostic_dir / "prompt-trace.json"
        raw_output_path = diagnostic_dir / "llm-raw-output.txt"
        parse_attempts_path = diagnostic_dir / "llm-parse-attempts.json"
        stability_path = diagnostic_dir / "llm-stability.json"

        write_json(prompt_trace_path, [trace])
        has_raw_text = "raw_text" in trace
        raw_text = str(trace.get("raw_text", ""))
        if has_raw_text:
            write_text(raw_output_path, raw_text)
        write_json(parse_attempts_path, trace.get("parse_attempts", []) or [])
        write_json(
            stability_path,
            {
                "provider": trace.get("provider"),
                "planner_mode": trace.get("planner_mode"),
                "error": trace.get("error"),
                "warnings": trace.get("warnings", []),
                "retry_attempts": trace.get("retry_attempts", 0),
                "schema_retry_attempts": trace.get("schema_retry_attempts", 0),
                "json_repair_applied": trace.get("json_repair_applied", False),
                "completion_usage": trace.get("completion_usage"),
                "completion_attempts": trace.get("completion_attempts", []),
                "parse_attempts": trace.get("parse_attempts", []),
                "raw_output_path": str(raw_output_path) if has_raw_text else None,
            },
        )
        result.diagnostic_dir = str(diagnostic_dir)
        result.prompt_trace_json_path = str(prompt_trace_path)
        result.raw_output_path = str(raw_output_path) if has_raw_text else None
        result.prompt_trace_present = True

    def _run_fallback_probe(
        self,
        index: int,
        case: EvalCase,
        *,
        orchestrator: AgentOrchestrator,
        llm_provider: str,
        planner_mode: str,
        run_build: bool,
        run_audit: bool,
    ) -> dict[str, Any]:
        workspace_name = f"{index:02d}-{case.identifier}-fallback"
        try:
            return orchestrator.run_generate(
                case.request,
                overrides=RequestOverrides(),
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                workspace_name=workspace_name,
                overwrite=True,
                run_build=run_build,
                run_audit=run_audit,
                repair=True,
                require_llm=False,
            ).to_dict()
        except Exception as exc:  # noqa: BLE001 - fallback failures are evidence.
            return {
                "success": False,
                "planner_mode": planner_mode,
                "llm_provider": llm_provider,
                "request": case.request,
                "errors": [f"{type(exc).__name__}: {exc}"],
            }

    def _render_markdown(self, result: RealLLMStabilityResult) -> str:
        metrics = result.metrics
        lines = [
            "# Real LLM Stability Report",
            "",
            f"Success: `{result.success}`",
            f"Run ID: `{result.run_id}`",
            f"Provider: `{result.llm_provider}`",
            f"Planner: `{result.planner_mode}`",
            f"Model: `{result.provider_config.get('model', '')}`",
            f"Provider config valid: `{result.provider_config.get('valid')}`",
            f"Build enabled: `{result.run_build}`",
            f"Audit enabled: `{result.run_audit}`",
            f"Fallback probe: `{result.fallback_probe}`",
            f"Runtime evidence: `{result.runtime_evidence_path or 'none'}`",
            f"Require runtime: `{result.require_runtime}`",
            "",
            "## Metrics",
            "",
            f"- total cases: `{metrics.get('total_cases')}`",
            f"- strict success: `{metrics.get('strict_success_count')}`",
            f"- real LLM success: `{metrics.get('real_llm_success_count')}`",
            f"- semantic success: `{metrics.get('semantic_success_count')}`",
            f"- expected feature match: `{metrics.get('expected_features_matched')}/{metrics.get('expected_features_total')}`",
            f"- expected category match: `{metrics.get('expected_categories_matched')}/{metrics.get('expected_categories_total')}`",
            f"- ignored feature warning messages: `{metrics.get('ignored_feature_warning_count')}`",
            f"- removed behavior warning messages: `{metrics.get('removed_behavior_warning_count')}`",
            f"- semantic warning messages: `{metrics.get('semantic_warning_count')}`",
            f"- provider failure: `{metrics.get('provider_failure_count')}`",
            f"- schema failure: `{metrics.get('schema_failure_count')}`",
            f"- audit failure: `{metrics.get('audit_failure_count')}`",
            f"- build failure: `{metrics.get('build_failure_count')}`",
            f"- runtime failure: `{metrics.get('runtime_failure_count')}`",
            f"- runtime checked: `{metrics.get('runtime_checked_count')}`",
            f"- runtime success: `{metrics.get('runtime_success_count')}`",
            f"- runtime unverified: `{metrics.get('runtime_unverified_count')}`",
            f"- fallback success: `{metrics.get('fallback_success_count')}`",
            f"- fallback failure: `{metrics.get('fallback_failure_count')}`",
            f"- JSON repair applied: `{metrics.get('json_repair_applied_count')}`",
            f"- retry attempts: `{metrics.get('retry_attempts_total')}`",
            f"- schema retry attempts: `{metrics.get('schema_retry_attempts_total')}`",
            f"- total tokens: `{metrics.get('total_tokens')}`",
            f"- estimated cost USD: `{metrics.get('estimated_cost_usd')}`",
            f"- average latency ms: `{metrics.get('average_latency_ms')}`",
            "",
            "## Cases",
            "",
        ]
        for case in result.cases:
            lines.append(
                f"- `{case.identifier}`: `{case.outcome}`"
                f" strict={str(case.strict_success).lower()}"
                f" semantic={str(case.semantic_success).lower()}"
                f" fallback={str(case.fallback_success).lower()}"
                f" failure={case.failure_type or 'none'}"
                f" runtime={case.runtime_status}"
            )
            if case.workspace:
                lines.append(f"  - workspace: `{case.workspace}`")
            if case.fallback_workspace:
                lines.append(f"  - fallback workspace: `{case.fallback_workspace}`")
            if case.errors:
                lines.append(f"  - error: {case.errors[0]}")
            if case.missing_expected_features:
                lines.append(
                    f"  - missing expected features: {', '.join(case.missing_expected_features)}"
                )
            if case.missing_expected_categories:
                lines.append(
                    f"  - missing expected categories: {', '.join(case.missing_expected_categories)}"
                )
            if case.semantic_warnings:
                lines.append(f"  - semantic warnings: {len(case.semantic_warnings)} unique message(s)")
            if case.runtime_evidence_notes:
                lines.append(f"  - runtime evidence: {case.runtime_evidence_notes}")
        if result.runtime_evidence_cases:
            lines.extend(["", "## Runtime Evidence Cases", ""])
            for case in result.runtime_evidence_cases:
                lines.append(
                    f"- `{case.identifier}`: `{case.status}` "
                    f"passed={str(case.passed).lower()} source=`{case.source}`"
                )
        if result.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in result.warnings)
        if result.errors:
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- {error}" for error in result.errors)
        lines.extend(
            [
                "",
                "## Interview Note",
                "",
                "Mock runs prove the deterministic engineering path. This report separates strict provider-backed success from provider/schema/audit/build/runtime failures and records fallback success without counting it as real LLM success.",
                "",
            ]
        )
        return "\n".join(lines)


def _load_generate_cases(cases_path: Path | None) -> list[EvalCase]:
    if cases_path is None:
        cases = default_eval_cases()
    else:
        data = json.loads(cases_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("cases", [])
        if not isinstance(data, list):
            raise ValueError("Stability cases file must contain a list or an object with a 'cases' list.")
        cases = [_case_from_dict(item) for item in data if isinstance(item, dict)]
    return [case for case in cases if case.mode == "generate"]


def _case_from_dict(data: dict[str, Any]) -> EvalCase:
    return EvalCase(
        identifier=str(data.get("id", data.get("identifier", "real_llm_case"))),
        mode=str(data.get("mode", "generate")).lower(),
        request=str(data.get("request", "")),
        setup_request=str(data["setup_request"]) if data.get("setup_request") is not None else None,
        expected_features=[str(item) for item in data.get("expected_features", [])],
        expected_categories=[str(item) for item in data.get("expected_categories", [])],
        repeat_request=bool(data.get("repeat_request", False)),
    )


def _case_result_from_payload(
    case: EvalCase,
    payload: dict[str, Any],
    *,
    llm_provider: str,
) -> RealLLMStabilityCaseResult:
    trace = _first_prompt_trace(payload)
    completion = _dict(trace.get("completion_usage"))
    usage = _dict(completion.get("usage"))
    provider_metadata = _dict(trace.get("provider_metadata"))
    audit_payload = _dict(_dict(payload.get("payload")).get("audit"))
    generation_payload = _dict(_dict(payload.get("payload")).get("generation"))
    build_payload = _dict(generation_payload.get("build"))
    strict_success = bool(payload.get("success"))
    fallback_used = _detect_fallback(payload)
    failure_type = _failure_type(payload)
    real_llm_success = strict_success and not fallback_used and llm_provider != "mock"
    outcome = "real_success" if real_llm_success else _outcome_from_failure(failure_type)
    if llm_provider == "mock" and strict_success:
        outcome = "mock_success"
    workspace = payload.get("workspace")
    warnings = _payload_warnings(payload)
    coverage = evaluate_semantic_coverage(
        expected_features=case.expected_features,
        expected_categories=case.expected_categories,
        modspec=_load_workspace_modspec(workspace),
        mode=case.mode,
        process_success=strict_success,
        warnings=warnings,
    )

    return RealLLMStabilityCaseResult(
        identifier=case.identifier,
        request=case.request,
        outcome=outcome,
        strict_success=strict_success,
        real_llm_success=real_llm_success,
        fallback_used=fallback_used,
        fallback_success=False,
        failure_type=failure_type,
        workspace=workspace,
        planner_mode_used=str(payload.get("planner_mode", "")),
        provider=str(trace.get("provider") or payload.get("llm_provider") or llm_provider),
        model=str(provider_metadata.get("model") or completion.get("model", "")),
        audit_attempted=bool(audit_payload.get("attempted")),
        audit_success=audit_payload.get("success"),
        build_attempted=bool(build_payload.get("attempted")),
        build_success=build_payload.get("success"),
        retry_attempts=int(trace.get("retry_attempts", 0) or 0),
        schema_retry_attempts=int(trace.get("schema_retry_attempts", 0) or 0),
        json_repair_applied=bool(trace.get("json_repair_applied")),
        latency_ms=_optional_int(completion.get("latency_ms")),
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
        total_tokens=int(usage.get("total_tokens", 0) or 0),
        estimated_cost_usd=_optional_float(completion.get("estimated_cost_usd")),
        prompt_trace_present=bool(payload.get("prompt_trace_json_path")) or bool(trace),
        agent_run_json_path=payload.get("agent_run_json_path"),
        prompt_trace_json_path=payload.get("prompt_trace_json_path"),
        warnings=warnings,
        errors=_payload_errors(payload),
        expected_features=coverage.expected_features,
        matched_expected_features=coverage.matched_expected_features,
        missing_expected_features=coverage.missing_expected_features,
        expected_categories=coverage.expected_categories,
        matched_expected_categories=coverage.matched_expected_categories,
        missing_expected_categories=coverage.missing_expected_categories,
        semantic_success=coverage.semantic_success,
        ignored_feature_warnings=coverage.ignored_feature_warnings,
        removed_behavior_warnings=coverage.removed_behavior_warnings,
        semantic_warnings=coverage.semantic_warnings,
    )


def _failure_type(payload: dict[str, Any]) -> str | None:
    if bool(payload.get("success")) and not _detect_fallback(payload):
        return None
    if _detect_fallback(payload):
        return "fallback"

    trace = _first_prompt_trace(payload)
    joined_errors = " ".join(_payload_errors(payload) + [str(trace.get("error") or "")]).lower()
    provider_health = _dict(trace.get("provider_health"))
    if provider_health and provider_health.get("healthy") is False:
        return "provider_failure"
    if any(token in joined_errors for token in ("provider", "http ", "timeout", "api key", "base url", "request failed")):
        return "provider_failure"
    if _schema_failed(trace) or any(token in joined_errors for token in ("invalid modspec", "invalid json", "schema")):
        return "schema_failure"

    audit_payload = _dict(_dict(payload.get("payload")).get("audit"))
    if audit_payload.get("attempted") and audit_payload.get("success") is False:
        return "audit_failure"
    generation_payload = _dict(_dict(payload.get("payload")).get("generation"))
    build_payload = _dict(generation_payload.get("build"))
    if build_payload.get("attempted") and build_payload.get("success") is False:
        return "build_failure"
    return "agent_failure"


def _attach_runtime_evidence(
    result: RealLLMStabilityCaseResult,
    runtime_evidence_cases: list[RealLLMRuntimeEvidenceCase],
) -> None:
    if not result.strict_success or not result.workspace:
        return
    evidence = _match_runtime_evidence(result, runtime_evidence_cases)
    if evidence is None:
        return
    result.runtime_checked = True
    result.runtime_success = evidence.passed
    result.runtime_status = "runtime_passed" if evidence.passed else "runtime_failure"
    result.runtime_evidence_source = evidence.source
    result.runtime_evidence_notes = evidence.notes
    if not evidence.passed:
        result.failure_type = "runtime_failure"
        result.outcome = "runtime_failure"
        result.real_llm_success = False


def _match_runtime_evidence(
    result: RealLLMStabilityCaseResult,
    runtime_evidence_cases: list[RealLLMRuntimeEvidenceCase],
) -> RealLLMRuntimeEvidenceCase | None:
    result_key = _normalized_runtime_key(result.identifier)
    result_tokens = _runtime_tokens(result.identifier)
    workspace_text = str(result.workspace or "").lower().replace("\\", "/")
    for evidence in runtime_evidence_cases:
        evidence_key = _normalized_runtime_key(evidence.identifier)
        if evidence_key == result_key:
            return evidence
        evidence_tokens = _runtime_tokens(evidence.identifier)
        if result_tokens and result_tokens == evidence_tokens:
            return evidence
        if result_tokens and evidence_tokens:
            result_token_set = set(result_tokens)
            evidence_token_set = set(evidence_tokens)
            if evidence_token_set.issubset(result_token_set) or result_token_set.issubset(evidence_token_set):
                return evidence
        evidence_workspace = evidence.workspace.lower().replace("\\", "/")
        if evidence_workspace and workspace_text and evidence_workspace in workspace_text:
            return evidence
    return None


def _normalized_runtime_key(value: str) -> str:
    return "_".join(_runtime_tokens(value))


def _runtime_tokens(value: str) -> list[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in value)
    aliases = {
        "basic": "basic",
        "ruby": "ruby",
        "machine": "machine",
        "progression": "progression",
    }
    tokens = [aliases.get(token, token) for token in normalized.split() if token]
    return sorted(tokens)


def _outcome_from_failure(failure_type: str | None) -> str:
    if failure_type is None:
        return "strict_success"
    return failure_type


def _schema_failed(trace: dict[str, Any]) -> bool:
    attempts = trace.get("schema_validation_attempts")
    if not isinstance(attempts, list) or not attempts:
        return False
    last = attempts[-1]
    return isinstance(last, dict) and last.get("valid") is False


def _detect_fallback(payload: dict[str, Any]) -> bool:
    planner_mode = str(payload.get("planner_mode", "")).lower()
    if "->rules" in planner_mode:
        return True
    warnings = " ".join(_payload_warnings(payload)).lower()
    return "fallback" in warnings or "fell back" in warnings or "fall back" in warnings


def _first_prompt_trace(payload: dict[str, Any]) -> dict[str, Any]:
    traces = payload.get("prompt_traces")
    if isinstance(traces, list):
        for trace in traces:
            if isinstance(trace, dict):
                return trace
    return {}


def _payload_warnings(payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for step in payload.get("steps", []) or []:
        if isinstance(step, dict):
            warnings.extend(str(item) for item in step.get("warnings", []) or [])
    for warning in payload.get("warnings", []) or []:
        warnings.append(str(warning))
    for trace in payload.get("prompt_traces", []) or []:
        if isinstance(trace, dict):
            warnings.extend(str(item) for item in trace.get("warnings", []) or [])
    return [item for item in warnings if item]


def _payload_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for step in payload.get("steps", []) or []:
        if isinstance(step, dict):
            errors.extend(str(item) for item in step.get("errors", []) or [])
    for error in payload.get("errors", []) or []:
        errors.append(str(error))
    planning_error = _dict(payload.get("payload")).get("planning_error")
    if planning_error:
        errors.append(str(planning_error))
    for trace in payload.get("prompt_traces", []) or []:
        if isinstance(trace, dict) and trace.get("error"):
            errors.append(str(trace["error"]))
    return [item for item in errors if item]


def _load_workspace_modspec(workspace: str | None) -> dict[str, Any] | None:
    if not workspace:
        return None
    path = Path(workspace) / ".agent" / "modspec.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _compute_metrics(results: list[RealLLMStabilityCaseResult]) -> dict[str, Any]:
    total = len(results)
    estimated_costs = [
        result.estimated_cost_usd
        for result in results
        if isinstance(result.estimated_cost_usd, (int, float))
    ]
    latencies = [result.latency_ms for result in results if isinstance(result.latency_ms, int)]
    semantic_success_count = sum(1 for result in results if result.semantic_success)
    expected_features_total = sum(len(result.expected_features) for result in results)
    expected_features_matched = sum(len(result.matched_expected_features) for result in results)
    expected_categories_total = sum(len(result.expected_categories) for result in results)
    expected_categories_matched = sum(len(result.matched_expected_categories) for result in results)
    return {
        "total_cases": total,
        "strict_success_count": sum(1 for result in results if result.strict_success),
        "real_llm_success_count": sum(1 for result in results if result.real_llm_success),
        "fallback_used_count": sum(1 for result in results if result.fallback_used),
        "fallback_success_count": sum(1 for result in results if result.fallback_success),
        "fallback_failure_count": sum(
            1 for result in results if result.fallback_used and not result.fallback_success
        ),
        "provider_failure_count": _failure_count(results, "provider_failure"),
        "schema_failure_count": _failure_count(results, "schema_failure"),
        "audit_failure_count": _failure_count(results, "audit_failure"),
        "build_failure_count": _failure_count(results, "build_failure"),
        "runtime_failure_count": _failure_count(results, "runtime_failure"),
        "agent_failure_count": _failure_count(results, "agent_failure"),
        "semantic_success_count": semantic_success_count,
        "expected_features_total": expected_features_total,
        "expected_features_matched": expected_features_matched,
        "expected_categories_total": expected_categories_total,
        "expected_categories_matched": expected_categories_matched,
        "ignored_feature_warning_count": sum(len(result.ignored_feature_warnings) for result in results),
        "removed_behavior_warning_count": sum(len(result.removed_behavior_warnings) for result in results),
        "semantic_warning_count": sum(len(result.semantic_warnings) for result in results),
        "runtime_checked_count": sum(1 for result in results if result.runtime_checked),
        "runtime_success_count": sum(1 for result in results if result.runtime_success is True),
        "runtime_unverified_count": sum(1 for result in results if not result.runtime_checked),
        "json_repair_applied_count": sum(1 for result in results if result.json_repair_applied),
        "retry_attempts_total": sum(result.retry_attempts for result in results),
        "schema_retry_attempts_total": sum(result.schema_retry_attempts for result in results),
        "input_tokens": sum(result.input_tokens for result in results),
        "output_tokens": sum(result.output_tokens for result in results),
        "total_tokens": sum(result.total_tokens for result in results),
        "estimated_cost_usd": round(sum(float(item) for item in estimated_costs), 8) if estimated_costs else None,
        "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "strict_success_rate": _rate(sum(1 for result in results if result.strict_success), total),
        "real_llm_success_rate": _rate(sum(1 for result in results if result.real_llm_success), total),
        "fallback_success_rate": _rate(sum(1 for result in results if result.fallback_success), total),
        "semantic_success_rate": _rate(semantic_success_count, total),
        "expected_feature_match_rate": _rate(expected_features_matched, expected_features_total),
        "expected_category_match_rate": _rate(expected_categories_matched, expected_categories_total),
    }


def _failure_count(results: list[RealLLMStabilityCaseResult], failure_type: str) -> int:
    return sum(1 for result in results if result.failure_type == failure_type)


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
