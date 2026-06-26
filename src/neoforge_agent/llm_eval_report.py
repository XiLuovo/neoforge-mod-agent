from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .eval_compare import EvalComparisonRunner
from .evaluator import BenchmarkEvaluator
from .llm_client import inspect_llm_provider_config
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class LLMEvalReportResult:
    success: bool
    run_id: str
    report_dir: Path
    baseline_status: str
    candidate_status: str
    comparison_status: str
    baseline_eval_report_path: Path | None
    candidate_eval_report_path: Path | None
    eval_compare_report_path: Path | None
    llm_eval_report_json_path: Path
    llm_eval_report_md_path: Path
    baseline_provider: str
    candidate_provider: str
    provider_config: dict[str, Any]
    metrics_summary: dict[str, Any]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "baseline_status": self.baseline_status,
            "candidate_status": self.candidate_status,
            "comparison_status": self.comparison_status,
            "baseline_eval_report_path": str(self.baseline_eval_report_path) if self.baseline_eval_report_path else None,
            "candidate_eval_report_path": str(self.candidate_eval_report_path) if self.candidate_eval_report_path else None,
            "eval_compare_report_path": str(self.eval_compare_report_path) if self.eval_compare_report_path else None,
            "llm_eval_report_json_path": str(self.llm_eval_report_json_path),
            "llm_eval_report_md_path": str(self.llm_eval_report_md_path),
            "baseline_provider": self.baseline_provider,
            "candidate_provider": self.candidate_provider,
            "provider_config": dict(self.provider_config),
            "metrics_summary": dict(self.metrics_summary),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "warnings_count": len(self.warnings),
            "errors_count": len(self.errors),
        }


class RealLLMEvalReportRunner:
    """Run a mock baseline, optional real/candidate eval, and a comparison report."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        cases_path: Path | None = None,
        limit: int | None = None,
        baseline_provider: str = "mock",
        candidate_provider: str = "openai-compatible",
        run_build: bool = False,
        run_audit: bool = True,
        tolerance: float = 0.0,
        require_real: bool = False,
    ) -> LLMEvalReportResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        root_dir = ensure_directory(self.config.workspace_root / "llm-eval-runs" / run_id)
        report_dir = ensure_directory(root_dir / ".agent")
        scoped_config = replace(self.config, workspace_root=ensure_directory(root_dir / "runs"))

        warnings: list[str] = []
        errors: list[str] = []
        provider_config = inspect_llm_provider_config(candidate_provider).to_dict()

        baseline = BenchmarkEvaluator(scoped_config).run(
            cases_path=cases_path,
            planner_mode="llm",
            llm_provider=baseline_provider,
            run_build=run_build,
            run_audit=run_audit,
            run_name=f"{run_id}-baseline-{baseline_provider}",
            limit=limit,
        )
        baseline_status = "pass" if baseline.success else "fail"

        candidate = None
        comparison = None
        candidate_status = "skip"
        comparison_status = "skip"

        can_run_candidate = self._candidate_can_run(candidate_provider, provider_config)
        if not can_run_candidate:
            message = (
                f"Candidate provider `{candidate_provider}` is not configured; "
                "skipping real LLM eval. Pass --candidate-provider mock for offline compare "
                "or configure NEOFORGE_AGENT_LLM_* / OPENAI_* variables."
            )
            if require_real:
                errors.append(message)
            else:
                warnings.append(message)
        else:
            candidate = BenchmarkEvaluator(scoped_config).run(
                cases_path=cases_path,
                planner_mode="llm",
                llm_provider=candidate_provider,
                run_build=run_build,
                run_audit=run_audit,
                run_name=f"{run_id}-candidate-{candidate_provider}",
                limit=limit,
            )
            candidate_status = "pass" if candidate.success else "fail"
            comparison = EvalComparisonRunner(scoped_config).compare(
                baseline.eval_report_json_path,
                candidate.eval_report_json_path,
                run_name=f"{run_id}-compare",
                tolerance=tolerance,
            )
            comparison_status = "pass" if comparison.success else "fail"

        success = baseline.success and not errors
        if candidate is not None:
            success = success and candidate.success
        if comparison is not None:
            success = success and comparison.success

        result = LLMEvalReportResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            baseline_status=baseline_status,
            candidate_status=candidate_status,
            comparison_status=comparison_status,
            baseline_eval_report_path=baseline.eval_report_json_path,
            candidate_eval_report_path=candidate.eval_report_json_path if candidate else None,
            eval_compare_report_path=comparison.eval_compare_report_json_path if comparison else None,
            llm_eval_report_json_path=report_dir / "llm-eval-report.json",
            llm_eval_report_md_path=report_dir / "llm-eval-report.md",
            baseline_provider=baseline_provider,
            candidate_provider=candidate_provider,
            provider_config=provider_config,
            metrics_summary=self._metrics_summary(
                baseline.to_dict(),
                candidate.to_dict() if candidate else None,
                comparison.to_dict() if comparison else None,
            ),
            warnings=warnings,
            errors=errors,
        )
        write_json(result.llm_eval_report_json_path, result.to_dict())
        write_text(result.llm_eval_report_md_path, self._render_markdown(result))
        return result

    def _candidate_can_run(self, provider: str, provider_config: dict[str, Any]) -> bool:
        if provider == "mock":
            return True
        return bool(provider_config.get("valid"))

    def _metrics_summary(
        self,
        baseline: dict[str, Any],
        candidate: dict[str, Any] | None,
        comparison: dict[str, Any] | None,
    ) -> dict[str, Any]:
        baseline_metrics = baseline.get("metrics", {})
        candidate_metrics = candidate.get("metrics", {}) if candidate else {}
        summary = {
            "baseline_success_rate": baseline_metrics.get("success_rate"),
            "baseline_planning_success_rate": baseline_metrics.get("planning_success_rate"),
            "baseline_audit_success_rate": baseline_metrics.get("audit_success_rate"),
            "baseline_rag_hit_rate": baseline_metrics.get("rag_hit_rate"),
            "candidate_success_rate": candidate_metrics.get("success_rate") if candidate else None,
            "candidate_planning_success_rate": candidate_metrics.get("planning_success_rate") if candidate else None,
            "candidate_audit_success_rate": candidate_metrics.get("audit_success_rate") if candidate else None,
            "candidate_rag_hit_rate": candidate_metrics.get("rag_hit_rate") if candidate else None,
            "regressions_count": comparison.get("regressions_count") if comparison else None,
            "improvements_count": comparison.get("improvements_count") if comparison else None,
            "warnings_count": comparison.get("warnings_count") if comparison else None,
        }
        if summary["baseline_success_rate"] is not None and summary["candidate_success_rate"] is not None:
            summary["success_rate_delta"] = round(
                float(summary["candidate_success_rate"]) - float(summary["baseline_success_rate"]),
                4,
            )
        else:
            summary["success_rate_delta"] = None
        return summary

    def _render_markdown(self, result: LLMEvalReportResult) -> str:
        lines = [
            "# Real LLM Eval Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Run ID: `{result.run_id}`",
            f"Baseline provider: `{result.baseline_provider}`",
            f"Candidate provider: `{result.candidate_provider}`",
            f"Baseline status: `{result.baseline_status}`",
            f"Candidate status: `{result.candidate_status}`",
            f"Comparison status: `{result.comparison_status}`",
            "",
            "## Provider Config",
            "",
            f"- provider: `{result.provider_config.get('provider')}`",
            f"- valid: `{result.provider_config.get('valid')}`",
            f"- api key present: `{result.provider_config.get('api_key_present')}`",
            f"- base url: `{result.provider_config.get('base_url')}`",
            f"- model: `{result.provider_config.get('model')}`",
            "",
            "## Metrics Summary",
            "",
        ]
        for key, value in result.metrics_summary.items():
            lines.append(f"- `{key}`: {value}")
        lines.extend(
            [
                "",
                "## Artifacts",
                "",
                f"- baseline eval: `{result.baseline_eval_report_path or ''}`",
                f"- candidate eval: `{result.candidate_eval_report_path or ''}`",
                f"- comparison: `{result.eval_compare_report_path or ''}`",
                f"- json: `{result.llm_eval_report_json_path}`",
            ]
        )
        if result.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {item}" for item in result.warnings)
        if result.errors:
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- {item}" for item in result.errors)
        lines.append("")
        return "\n".join(lines)
