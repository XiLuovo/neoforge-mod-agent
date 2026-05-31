from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from .config import AppConfig
from .evaluator import BenchmarkEvaluator, EvalRunResult
from .llm_client import get_llm_provider_metadata, inspect_llm_provider_config
from .repair_eval import RepairEvalResult, RepairEvalRunner
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class BenchmarkModelRun:
    label: str
    provider: str
    model: str
    status: str
    provider_kind: str
    eval_report_path: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    provider_config: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "provider_kind": self.provider_kind,
            "eval_report_path": self.eval_report_path,
            "metrics": dict(self.metrics),
            "provider_config": dict(self.provider_config),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class BenchmarkFailureType:
    identifier: str
    title: str
    success: bool
    audit_detected: bool
    repair_loop_repaired: bool
    audit_recovered: bool
    repair_rag_hits_count: int
    initial_audit_errors_count: int
    capabilities: list[str] = field(default_factory=list)
    workspace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "title": self.title,
            "success": self.success,
            "audit_detected": self.audit_detected,
            "repair_loop_repaired": self.repair_loop_repaired,
            "audit_recovered": self.audit_recovered,
            "repair_rag_hits_count": self.repair_rag_hits_count,
            "initial_audit_errors_count": self.initial_audit_errors_count,
            "capabilities": list(self.capabilities),
            "workspace": self.workspace,
        }


@dataclass(slots=True)
class BenchmarkRuntimeCase:
    identifier: str
    workspace: str
    status: str
    passed: bool
    source: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "workspace": self.workspace,
            "status": self.status,
            "passed": self.passed,
            "source": self.source,
            "notes": self.notes,
        }


@dataclass(slots=True)
class BenchmarkPageResult:
    success: bool
    run_id: str
    report_dir: Path
    model_runs: list[BenchmarkModelRun]
    failure_types: list[BenchmarkFailureType]
    runtime_cases: list[BenchmarkRuntimeCase]
    repair_eval_report_path: str | None
    metrics: dict[str, Any]
    benchmark_report_json_path: Path
    benchmark_report_md_path: Path
    benchmark_report_html_path: Path
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "model_runs": [run.to_dict() for run in self.model_runs],
            "failure_types": [failure.to_dict() for failure in self.failure_types],
            "runtime_cases": [case.to_dict() for case in self.runtime_cases],
            "repair_eval_report_path": self.repair_eval_report_path,
            "metrics": dict(self.metrics),
            "benchmark_report_json_path": str(self.benchmark_report_json_path),
            "benchmark_report_md_path": str(self.benchmark_report_md_path),
            "benchmark_report_html_path": str(self.benchmark_report_html_path),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "warnings_count": len(self.warnings),
            "errors_count": len(self.errors),
        }


class BenchmarkReportRunner:
    """Aggregate model, repair, build, and runtime evidence into one benchmark page."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        cases_path: Path | None = None,
        eval_limit: int | None = 3,
        repair_limit: int | None = 3,
        baseline_provider: str = "mock",
        candidate_provider: str = "openai-compatible",
        run_build: bool = False,
        run_audit: bool = True,
        run_real: bool = False,
        require_real: bool = False,
        runtime_evidence_path: Path | None = None,
    ) -> BenchmarkPageResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        root_dir = ensure_directory(self.config.workspace_root / "benchmark-runs" / run_id)
        report_dir = ensure_directory(root_dir / ".agent")
        scoped_config = replace(self.config, workspace_root=ensure_directory(root_dir / "runs"))

        warnings: list[str] = []
        errors: list[str] = []
        model_runs: list[BenchmarkModelRun] = []

        baseline = self._run_eval(
            "A",
            provider=baseline_provider,
            scoped_config=scoped_config,
            cases_path=cases_path,
            eval_limit=eval_limit,
            run_build=run_build,
            run_audit=run_audit,
            run_id=run_id,
        )
        model_runs.append(baseline)
        errors.extend(baseline.errors)

        candidate_config = inspect_llm_provider_config(candidate_provider).to_dict()
        should_run_candidate = candidate_provider == "mock" or run_real or require_real
        if should_run_candidate and self._can_run_provider(candidate_provider, candidate_config):
            candidate = self._run_eval(
                "B",
                provider=candidate_provider,
                scoped_config=scoped_config,
                cases_path=cases_path,
                eval_limit=eval_limit,
                run_build=run_build,
                run_audit=run_audit,
                run_id=run_id,
            )
            model_runs.append(candidate)
            errors.extend(candidate.errors)
        else:
            if should_run_candidate:
                message = (
                    f"Candidate provider `{candidate_provider}` is not configured; "
                    "benchmark page records it as skipped without calling the network."
                )
            else:
                message = (
                    f"Candidate provider `{candidate_provider}` was preflighted but not executed; "
                    "pass --run-real or --require-real to include real provider calls."
                )
            if require_real:
                errors.append(message)
            else:
                warnings.append(message)
            model_runs.append(
                BenchmarkModelRun(
                    label="B",
                    provider=candidate_provider,
                    model=str(candidate_config.get("model", "")),
                    status="skip",
                    provider_kind=_provider_kind(candidate_provider),
                    provider_config=candidate_config,
                    warnings=[message],
                )
            )

        repair_eval = RepairEvalRunner(scoped_config).run(
            run_name=f"{run_id}-repair",
            limit=repair_limit,
            run_build=run_build,
        )
        failure_types = [_failure_from_repair_case(case) for case in repair_eval.cases]
        if not repair_eval.success:
            warnings.append("Repair eval did not reach full success for every selected failure type.")

        runtime_cases = self._load_runtime_cases(runtime_evidence_path)
        metrics = self._metrics(model_runs, failure_types, runtime_cases)
        success = not errors and bool(model_runs) and baseline.status == "pass" and repair_eval.success

        result = BenchmarkPageResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            model_runs=model_runs,
            failure_types=failure_types,
            runtime_cases=runtime_cases,
            repair_eval_report_path=str(repair_eval.repair_eval_report_json_path),
            metrics=metrics,
            benchmark_report_json_path=report_dir / "benchmark-report.json",
            benchmark_report_md_path=report_dir / "benchmark-report.md",
            benchmark_report_html_path=report_dir / "benchmark-report.html",
            warnings=warnings,
            errors=errors,
        )
        write_json(result.benchmark_report_json_path, result.to_dict())
        write_text(result.benchmark_report_md_path, self._render_markdown(result))
        write_text(result.benchmark_report_html_path, self._render_html(result))
        return result

    def _run_eval(
        self,
        label: str,
        *,
        provider: str,
        scoped_config: AppConfig,
        cases_path: Path | None,
        eval_limit: int | None,
        run_build: bool,
        run_audit: bool,
        run_id: str,
    ) -> BenchmarkModelRun:
        provider_config = inspect_llm_provider_config(provider).to_dict()
        metadata = get_llm_provider_metadata(provider).to_dict()
        model = str(metadata.get("model") or provider_config.get("model") or provider)
        try:
            eval_result = BenchmarkEvaluator(scoped_config).run(
                cases_path=cases_path,
                planner_mode="llm",
                llm_provider=provider,
                run_build=run_build,
                run_audit=run_audit,
                run_name=f"{run_id}-model-{label.lower()}-{provider}",
                limit=eval_limit,
            )
        except Exception as exc:  # keep the aggregate report alive
            return BenchmarkModelRun(
                label=label,
                provider=provider,
                model=model,
                status="fail",
                provider_kind=_provider_kind(provider),
                provider_config=provider_config,
                errors=[f"{type(exc).__name__}: {exc}"],
            )
        return BenchmarkModelRun(
            label=label,
            provider=provider,
            model=model,
            status="pass" if eval_result.success else "fail",
            provider_kind=_provider_kind(provider),
            eval_report_path=str(eval_result.eval_report_json_path),
            metrics=dict(eval_result.metrics),
            provider_config=provider_config,
        )

    def _can_run_provider(self, provider: str, provider_config: dict[str, Any]) -> bool:
        if provider == "mock":
            return True
        return bool(provider_config.get("valid"))

    def _load_runtime_cases(self, runtime_evidence_path: Path | None) -> list[BenchmarkRuntimeCase]:
        path = runtime_evidence_path or self.config.project_root / "docs" / "test-matrix.md"
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        section = _section_after_heading(text, "## 2026-05-13 Real LLM Natural Prompt Runtime Validation")
        cases: list[BenchmarkRuntimeCase] = []
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|") or "---" in stripped or "Case" in stripped:
                continue
            columns = [column.strip() for column in stripped.strip("|").split("|")]
            if len(columns) < 4:
                continue
            case_name, workspace, status, notes = columns[:4]
            clean_workspace = workspace.strip("`")
            passed = "通过" in status and "未通过" not in status
            cases.append(
                BenchmarkRuntimeCase(
                    identifier=case_name,
                    workspace=clean_workspace,
                    status=status,
                    passed=passed,
                    source=str(path),
                    notes=notes,
                )
            )
        return cases

    def _metrics(
        self,
        model_runs: list[BenchmarkModelRun],
        failure_types: list[BenchmarkFailureType],
        runtime_cases: list[BenchmarkRuntimeCase],
    ) -> dict[str, Any]:
        completed_model_runs = [run for run in model_runs if run.status in {"pass", "fail"}]
        build_attempted = sum(int(run.metrics.get("build_attempted_count", 0) or 0) for run in completed_model_runs)
        build_success = sum(int(run.metrics.get("build_success_count", 0) or 0) for run in completed_model_runs)
        repair_total = len(failure_types)
        repair_success = sum(1 for failure in failure_types if failure.success)
        runtime_total = len(runtime_cases)
        runtime_success = sum(1 for case in runtime_cases if case.passed)
        return {
            "model_runs_total": len(model_runs),
            "model_runs_completed": len(completed_model_runs),
            "model_runs_skipped": sum(1 for run in model_runs if run.status == "skip"),
            "mock_runs": sum(1 for run in model_runs if run.provider_kind == "mock"),
            "real_runs": sum(1 for run in model_runs if run.provider_kind == "real"),
            "best_success_rate": max((float(run.metrics.get("success_rate", 0) or 0) for run in completed_model_runs), default=0.0),
            "build_attempted_count": build_attempted,
            "build_success_count": build_success,
            "build_pass_rate": _rate(build_success, build_attempted) if build_attempted else None,
            "failure_types_total": repair_total,
            "failure_types_repaired": repair_success,
            "repair_rate": _rate(repair_success, repair_total),
            "audit_detection_rate": _rate(sum(1 for failure in failure_types if failure.audit_detected), repair_total),
            "runtime_cases_total": runtime_total,
            "runtime_passed_count": runtime_success,
            "runtime_pass_rate": _rate(runtime_success, runtime_total),
        }

    def _render_markdown(self, result: BenchmarkPageResult) -> str:
        lines = [
            "# Benchmark Report",
            "",
            f"Success: `{str(result.success).lower()}`",
            f"Run ID: `{result.run_id}`",
            f"HTML: `{result.benchmark_report_html_path}`",
            "",
            "## Metrics",
            "",
        ]
        for key, value in result.metrics.items():
            lines.append(f"- `{key}`: {value}")
        lines.extend(["", "## Model A/B", ""])
        for run in result.model_runs:
            lines.append(
                f"- `{run.label}` `{run.provider}` `{run.model}` `{run.status}`: "
                f"success_rate={run.metrics.get('success_rate')}, "
                f"audit={run.metrics.get('audit_success_rate')}, "
                f"build={run.metrics.get('build_success_rate')}"
            )
        lines.extend(["", "## Failure Types", ""])
        for failure in result.failure_types:
            lines.append(
                f"- `{failure.identifier}`: repair={str(failure.success).lower()}, "
                f"audit_detected={str(failure.audit_detected).lower()}, "
                f"recovered={str(failure.audit_recovered).lower()}"
            )
        lines.extend(["", "## Runtime Evidence", ""])
        for case in result.runtime_cases:
            lines.append(f"- `{case.identifier}` `{case.status}`: `{case.workspace}`")
        if result.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in result.warnings)
        if result.errors:
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- {error}" for error in result.errors)
        lines.append("")
        return "\n".join(lines)

    def _render_html(self, result: BenchmarkPageResult) -> str:
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Benchmark Report</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #172033;
      --muted: #667085;
      --line: #d8dee8;
      --blue: #2563eb;
      --green: #16803c;
      --amber: #a16207;
      --red: #c2410c;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.55 "Segoe UI", "Microsoft YaHei", Arial, sans-serif; }}
    header {{ background: var(--panel); border-bottom: 1px solid var(--line); }}
    .wrap {{ max-width: 1220px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; letter-spacing: 0; }}
    p {{ margin: 0; color: var(--muted); }}
    .grid {{ display: grid; gap: 12px; }}
    .metrics {{ grid-template-columns: repeat(6, minmax(0, 1fr)); margin: 18px 0; }}
    .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .card, .metric, table {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
    .card, .metric {{ padding: 14px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 18px; overflow-wrap: anywhere; }}
    section {{ margin-top: 22px; }}
    table {{ width: 100%; border-collapse: separate; border-spacing: 0; overflow: hidden; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; background: #fbfcfe; }}
    tr:last-child td {{ border-bottom: 0; }}
    code {{ overflow-wrap: anywhere; }}
    .badge {{ display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 650; border: 1px solid var(--line); }}
    .pass {{ color: var(--green); background: #ecfdf3; border-color: #b7e4ca; }}
    .fail {{ color: var(--red); background: #fff1ec; border-color: #ffc6b5; }}
    .skip {{ color: var(--amber); background: #fffbeb; border-color: #fde68a; }}
    .note {{ color: var(--muted); }}
    .notice {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; margin-top: 12px; }}
    @media (max-width: 980px) {{ .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .cards {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 640px) {{ .wrap {{ padding: 14px; }} .metrics {{ grid-template-columns: 1fr; }} h1 {{ font-size: 24px; }} }}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <h1>Benchmark Report</h1>
      <p>模型 A/B、mock/real provider、失败类型、修复率、build/runtime 通过率的统一 benchmark 页面。默认不会因为 real provider 未配置而联网。</p>
    </div>
  </header>
  <main class="wrap">
    <section>
      <h2>Summary</h2>
      <div class="grid metrics">
        {self._metric_cards(result.metrics)}
      </div>
    </section>
    <section class="grid cards">
      <div class="card">
        <h2>Model A/B</h2>
        {self._model_table(result.model_runs)}
      </div>
      <div class="card">
        <h2>Failure Types</h2>
        {self._failure_table(result.failure_types)}
      </div>
    </section>
    <section class="card">
      <h2>Runtime Evidence</h2>
      {self._runtime_table(result.runtime_cases)}
      <p class="note">Runtime pass rate comes from documented manual Minecraft runtime validation evidence. Fast benchmark runs still keep build/runtime execution optional.</p>
    </section>
    <section class="card">
      <h2>Artifacts</h2>
      <table>
        <tr><th>Name</th><th>Path</th></tr>
        <tr><td>Benchmark JSON</td><td><code>{escape(str(result.benchmark_report_json_path))}</code></td></tr>
        <tr><td>Benchmark Markdown</td><td><code>{escape(str(result.benchmark_report_md_path))}</code></td></tr>
        <tr><td>Repair Eval</td><td><code>{escape(result.repair_eval_report_path or "")}</code></td></tr>
      </table>
    </section>
    {self._notices("Warnings", result.warnings, "skip")}
    {self._notices("Errors", result.errors, "fail")}
  </main>
</body>
</html>
"""

    def _metric_cards(self, metrics: dict[str, Any]) -> str:
        keys = [
            "model_runs_completed",
            "model_runs_skipped",
            "best_success_rate",
            "build_pass_rate",
            "repair_rate",
            "runtime_pass_rate",
            "failure_types_total",
            "runtime_cases_total",
        ]
        return "\n".join(
            f'<div class="metric"><span>{escape(key)}</span><strong>{escape(_format_value(metrics.get(key)))}</strong></div>'
            for key in keys
        )

    def _model_table(self, model_runs: list[BenchmarkModelRun]) -> str:
        rows = [
            "<table><tr><th>Label</th><th>Provider</th><th>Model</th><th>Status</th><th>Success</th><th>Audit</th><th>Build</th></tr>"
        ]
        for run in model_runs:
            rows.append(
                "<tr>"
                f"<td>{escape(run.label)}</td>"
                f"<td>{escape(run.provider_kind)}<br><code>{escape(run.provider)}</code></td>"
                f"<td><code>{escape(run.model)}</code></td>"
                f'<td><span class="badge {escape(run.status)}">{escape(run.status)}</span></td>'
                f"<td>{escape(_format_value(run.metrics.get('success_rate')))}</td>"
                f"<td>{escape(_format_value(run.metrics.get('audit_success_rate')))}</td>"
                f"<td>{escape(_format_value(run.metrics.get('build_success_rate')))}</td>"
                "</tr>"
            )
        rows.append("</table>")
        return "\n".join(rows)

    def _failure_table(self, failures: list[BenchmarkFailureType]) -> str:
        rows = [
            "<table><tr><th>Failure</th><th>Status</th><th>Audit</th><th>Repair</th><th>Recovered</th><th>RAG Hits</th></tr>"
        ]
        for failure in failures:
            status = "pass" if failure.success else "fail"
            rows.append(
                "<tr>"
                f"<td><code>{escape(failure.identifier)}</code><br>{escape(failure.title)}</td>"
                f'<td><span class="badge {status}">{status}</span></td>'
                f"<td>{escape(str(failure.audit_detected).lower())}</td>"
                f"<td>{escape(str(failure.repair_loop_repaired).lower())}</td>"
                f"<td>{escape(str(failure.audit_recovered).lower())}</td>"
                f"<td>{failure.repair_rag_hits_count}</td>"
                "</tr>"
            )
        rows.append("</table>")
        return "\n".join(rows)

    def _runtime_table(self, cases: list[BenchmarkRuntimeCase]) -> str:
        if not cases:
            return '<p class="note">No runtime validation evidence was found.</p>'
        rows = [
            "<table><tr><th>Case</th><th>Status</th><th>Workspace</th><th>Evidence</th></tr>"
        ]
        for case in cases:
            status = "pass" if case.passed else "fail"
            rows.append(
                "<tr>"
                f"<td>{escape(case.identifier)}</td>"
                f'<td><span class="badge {status}">{escape(case.status)}</span></td>'
                f"<td><code>{escape(case.workspace)}</code></td>"
                f"<td>{escape(case.notes)}</td>"
                "</tr>"
            )
        rows.append("</table>")
        return "\n".join(rows)

    def _notices(self, title: str, items: list[str], status: str) -> str:
        if not items:
            return ""
        body = "".join(f"<li>{escape(item)}</li>" for item in items)
        return f'<section class="notice"><span class="badge {status}">{escape(title)}</span><ul>{body}</ul></section>'


def _failure_from_repair_case(case: Any) -> BenchmarkFailureType:
    return BenchmarkFailureType(
        identifier=str(case.identifier),
        title=str(case.title),
        success=bool(case.success),
        audit_detected=bool(case.audit_detected),
        repair_loop_repaired=bool(case.repair_loop_repaired),
        audit_recovered=bool(case.audit_recovered),
        repair_rag_hits_count=int(case.repair_rag_hits_count),
        initial_audit_errors_count=int(case.initial_audit_errors_count),
        capabilities=list(case.repair_rag_capabilities),
        workspace=case.workspace,
    )


def _section_after_heading(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    rest = text[start + len(heading) :]
    next_heading = rest.find("\n## ")
    if next_heading >= 0:
        return rest[:next_heading]
    return rest


def _provider_kind(provider: str) -> str:
    return "mock" if provider == "mock" else "real"


def _rate(count: int, total: int) -> float:
    return float(count / total) if total else 0.0


def _format_value(value: Any) -> str:
    if value is None:
        return "not run"
    if isinstance(value, float):
        return f"{value:.2%}" if 0 <= value <= 1 else f"{value:.4f}"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)
