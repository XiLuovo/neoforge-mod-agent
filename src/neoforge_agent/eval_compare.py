from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .tools import ensure_directory, write_json, write_text


MONITORED_RATE_METRICS = [
    "success_rate",
    "feature_expectation_success_rate",
    "expected_feature_match_rate",
    "category_expectation_success_rate",
    "expected_category_match_rate",
    "planning_success_rate",
    "audit_success_rate",
    "build_success_rate",
    "agent_artifacts_complete_rate",
    "agent_trace_present_rate",
    "agent_decisions_present_rate",
    "prompt_trace_present_rate",
    "repeat_modify_success_rate",
]


@dataclass(slots=True)
class EvalMetricComparison:
    name: str
    baseline: float | int | None
    candidate: float | int | None
    delta: float | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "baseline": self.baseline,
            "candidate": self.candidate,
            "delta": self.delta,
            "status": self.status,
        }


@dataclass(slots=True)
class EvalCaseComparison:
    identifier: str
    baseline_success: bool | None
    candidate_success: bool | None
    status: str
    baseline_errors: list[str] = field(default_factory=list)
    candidate_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "baseline_success": self.baseline_success,
            "candidate_success": self.candidate_success,
            "status": self.status,
            "baseline_errors": list(self.baseline_errors),
            "candidate_errors": list(self.candidate_errors),
        }


@dataclass(slots=True)
class EvalComparisonResult:
    success: bool
    run_id: str
    baseline_report_path: Path
    candidate_report_path: Path
    report_dir: Path
    metric_comparisons: list[EvalMetricComparison]
    case_comparisons: list[EvalCaseComparison]
    regressions: list[str]
    improvements: list[str]
    warnings: list[str]
    eval_compare_report_json_path: Path
    eval_compare_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "baseline_report_path": str(self.baseline_report_path),
            "candidate_report_path": str(self.candidate_report_path),
            "report_dir": str(self.report_dir),
            "metric_comparisons": [item.to_dict() for item in self.metric_comparisons],
            "case_comparisons": [item.to_dict() for item in self.case_comparisons],
            "regressions": list(self.regressions),
            "improvements": list(self.improvements),
            "warnings": list(self.warnings),
            "regressions_count": len(self.regressions),
            "improvements_count": len(self.improvements),
            "warnings_count": len(self.warnings),
            "eval_compare_report_json_path": str(self.eval_compare_report_json_path),
            "eval_compare_report_md_path": str(self.eval_compare_report_md_path),
        }


class EvalComparisonRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def compare(
        self,
        baseline: str | Path,
        candidate: str | Path,
        *,
        run_name: str | None = None,
        tolerance: float = 0.0,
    ) -> EvalComparisonResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        baseline_path = self._resolve_report_path(baseline)
        candidate_path = self._resolve_report_path(candidate)
        baseline_payload = self._load_report(baseline_path)
        candidate_payload = self._load_report(candidate_path)

        metric_comparisons = self._compare_metrics(
            baseline_payload.get("metrics", {}),
            candidate_payload.get("metrics", {}),
            tolerance=max(0.0, tolerance),
        )
        case_comparisons = self._compare_cases(
            baseline_payload.get("cases", []),
            candidate_payload.get("cases", []),
        )

        regressions = [
            f"metric:{item.name} {item.baseline} -> {item.candidate}"
            for item in metric_comparisons
            if item.status == "regression"
        ]
        regressions.extend(
            f"case:{item.identifier} {item.baseline_success} -> {item.candidate_success}"
            for item in case_comparisons
            if item.status == "regression"
        )
        improvements = [
            f"metric:{item.name} {item.baseline} -> {item.candidate}"
            for item in metric_comparisons
            if item.status == "improvement"
        ]
        improvements.extend(
            f"case:{item.identifier} {item.baseline_success} -> {item.candidate_success}"
            for item in case_comparisons
            if item.status == "improvement"
        )
        warnings = [
            f"case:{item.identifier} status={item.status}"
            for item in case_comparisons
            if item.status in {"new", "removed"}
        ]

        report_dir = ensure_directory(self.config.workspace_root / "eval-comparisons" / run_id / ".agent")
        report_json = report_dir / "eval-compare-report.json"
        report_md = report_dir / "eval-compare-report.md"
        result = EvalComparisonResult(
            success=not regressions,
            run_id=run_id,
            baseline_report_path=baseline_path,
            candidate_report_path=candidate_path,
            report_dir=report_dir,
            metric_comparisons=metric_comparisons,
            case_comparisons=case_comparisons,
            regressions=regressions,
            improvements=improvements,
            warnings=warnings,
            eval_compare_report_json_path=report_json,
            eval_compare_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_markdown(result))
        return result

    def _resolve_report_path(self, value: str | Path) -> Path:
        raw = Path(value)
        candidates = [
            raw,
            raw / ".agent" / "eval-report.json",
            raw / "eval-report.json",
            self.config.workspace_root / "eval-runs" / str(value) / ".agent" / "eval-report.json",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        raise FileNotFoundError(f"Eval report not found: {value}")

    def _load_report(self, path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Eval report must be a JSON object: {path}")
        if "metrics" not in data or "cases" not in data:
            raise ValueError(f"Eval report is missing metrics or cases: {path}")
        return data

    def _compare_metrics(
        self,
        baseline_metrics: dict[str, Any],
        candidate_metrics: dict[str, Any],
        *,
        tolerance: float,
    ) -> list[EvalMetricComparison]:
        comparisons: list[EvalMetricComparison] = []
        for metric_name in MONITORED_RATE_METRICS:
            baseline_value = _number_or_none(baseline_metrics.get(metric_name))
            candidate_value = _number_or_none(candidate_metrics.get(metric_name))
            if baseline_value is None and candidate_value is None:
                status = "missing"
                delta = None
            elif baseline_value is None:
                status = "new"
                delta = None
            elif candidate_value is None:
                status = "regression"
                delta = None
            else:
                delta = round(float(candidate_value) - float(baseline_value), 4)
                if delta < -tolerance:
                    status = "regression"
                elif delta > tolerance:
                    status = "improvement"
                else:
                    status = "same"
            comparisons.append(
                EvalMetricComparison(
                    name=metric_name,
                    baseline=baseline_value,
                    candidate=candidate_value,
                    delta=delta,
                    status=status,
                )
            )
        return comparisons

    def _compare_cases(
        self,
        baseline_cases: list[Any],
        candidate_cases: list[Any],
    ) -> list[EvalCaseComparison]:
        baseline_by_id = _cases_by_id(baseline_cases)
        candidate_by_id = _cases_by_id(candidate_cases)
        comparisons: list[EvalCaseComparison] = []
        for identifier in sorted(set(baseline_by_id) | set(candidate_by_id)):
            baseline_case = baseline_by_id.get(identifier)
            candidate_case = candidate_by_id.get(identifier)
            baseline_success = _case_success(baseline_case)
            candidate_success = _case_success(candidate_case)
            if baseline_case is None:
                status = "new"
            elif candidate_case is None:
                status = "regression" if baseline_success else "removed"
            elif baseline_success and not candidate_success:
                status = "regression"
            elif not baseline_success and candidate_success:
                status = "improvement"
            else:
                status = "same"
            comparisons.append(
                EvalCaseComparison(
                    identifier=identifier,
                    baseline_success=baseline_success,
                    candidate_success=candidate_success,
                    status=status,
                    baseline_errors=_case_errors(baseline_case),
                    candidate_errors=_case_errors(candidate_case),
                )
            )
        return comparisons

    def _render_markdown(self, result: EvalComparisonResult) -> str:
        lines = [
            "# Eval Compare Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Run ID: `{result.run_id}`",
            f"Baseline: `{result.baseline_report_path}`",
            f"Candidate: `{result.candidate_report_path}`",
            f"Regressions: {len(result.regressions)}",
            f"Improvements: {len(result.improvements)}",
            f"Warnings: {len(result.warnings)}",
            "",
            "## Metric Comparisons",
            "",
        ]
        for item in result.metric_comparisons:
            lines.append(
                f"- `{item.name}` `{item.status}`: "
                f"{item.baseline} -> {item.candidate} (delta={item.delta})"
            )
        lines.extend(["", "## Case Comparisons", ""])
        for item in result.case_comparisons:
            lines.append(
                f"- `{item.identifier}` `{item.status}`: "
                f"{item.baseline_success} -> {item.candidate_success}"
            )
            if item.candidate_errors:
                lines.append(f"  - candidate errors: {'; '.join(item.candidate_errors)}")
        if result.regressions:
            lines.extend(["", "## Regressions", ""])
            lines.extend(f"- {item}" for item in result.regressions)
        if result.improvements:
            lines.extend(["", "## Improvements", ""])
            lines.extend(f"- {item}" for item in result.improvements)
        if result.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {item}" for item in result.warnings)
        lines.append("")
        return "\n".join(lines)


def _number_or_none(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return value
    return None


def _cases_by_id(cases: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in cases:
        if isinstance(item, dict):
            identifier = item.get("id", item.get("identifier"))
            if identifier:
                result[str(identifier)] = item
    return result


def _case_success(case: dict[str, Any] | None) -> bool | None:
    if case is None:
        return None
    return bool(case.get("success"))


def _case_errors(case: dict[str, Any] | None) -> list[str]:
    if case is None:
        return []
    errors = case.get("errors", [])
    if not isinstance(errors, list):
        return [str(errors)]
    return [str(item) for item in errors]
