from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .failure_lab import FailureLabCaseResult, FailureLabRunner
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class RepairEvalCaseResult:
    identifier: str
    title: str
    workspace: str | None
    audit_detected: bool
    repair_rag_relevant: bool
    repair_loop_repaired: bool
    audit_recovered: bool
    success: bool
    initial_audit_errors_count: int = 0
    repair_rag_hits_count: int = 0
    detected_issue_ids: list[str] = field(default_factory=list)
    expected_rag_capabilities: list[str] = field(default_factory=list)
    repair_rag_capabilities: list[str] = field(default_factory=list)
    repair_rag_knowledge_ids: list[str] = field(default_factory=list)
    artifacts: dict[str, str | None] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "title": self.title,
            "workspace": self.workspace,
            "success": self.success,
            "audit_detected": self.audit_detected,
            "repair_rag_relevant": self.repair_rag_relevant,
            "repair_loop_repaired": self.repair_loop_repaired,
            "audit_recovered": self.audit_recovered,
            "initial_audit_errors_count": self.initial_audit_errors_count,
            "repair_rag_hits_count": self.repair_rag_hits_count,
            "detected_issue_ids": list(self.detected_issue_ids),
            "expected_rag_capabilities": list(self.expected_rag_capabilities),
            "repair_rag_capabilities": list(self.repair_rag_capabilities),
            "repair_rag_knowledge_ids": list(self.repair_rag_knowledge_ids),
            "artifacts": dict(self.artifacts),
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class RepairEvalResult:
    success: bool
    run_id: str
    report_dir: Path
    metrics: dict[str, Any]
    cases: list[RepairEvalCaseResult]
    failure_lab_report_json_path: str | None
    failure_lab_report_md_path: str | None
    repair_eval_report_json_path: Path
    repair_eval_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "metrics": dict(self.metrics),
            "cases": [case.to_dict() for case in self.cases],
            "cases_count": len(self.cases),
            "failure_lab_report_json_path": self.failure_lab_report_json_path,
            "failure_lab_report_md_path": self.failure_lab_report_md_path,
            "repair_eval_report_json_path": str(self.repair_eval_report_json_path),
            "repair_eval_report_md_path": str(self.repair_eval_report_md_path),
        }


class RepairEvalRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        case_ids: list[str] | None = None,
        limit: int | None = None,
        run_build: bool = False,
    ) -> RepairEvalResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        run_root = ensure_directory(self.config.workspace_root / "repair-eval-runs" / run_id)
        report_dir = ensure_directory(run_root / ".agent")
        nested_config = replace(self.config, workspace_root=ensure_directory(run_root / "runs"))

        failure_lab = FailureLabRunner(nested_config).run(
            run_name="failure-lab",
            case_ids=case_ids,
            limit=limit,
            run_build=run_build,
        )
        cases = [_case_from_failure_lab(case) for case in failure_lab.cases]
        metrics = _metrics(cases)
        success = bool(cases) and metrics["full_success_count"] == metrics["total_cases"]

        report_json = report_dir / "repair-eval-report.json"
        report_md = report_dir / "repair-eval-report.md"
        result = RepairEvalResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            metrics=metrics,
            cases=cases,
            failure_lab_report_json_path=str(failure_lab.failure_lab_report_json_path),
            failure_lab_report_md_path=str(failure_lab.failure_lab_report_md_path),
            repair_eval_report_json_path=report_json,
            repair_eval_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_markdown(result))
        return result

    def _render_markdown(self, result: RepairEvalResult) -> str:
        metrics = result.metrics
        lines = [
            "# Repair Eval Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Run ID: `{result.run_id}`",
            f"Total cases: `{metrics['total_cases']}`",
            "",
            "## Metrics",
            "",
            f"- audit detected: `{metrics['audit_detected_count']}/{metrics['total_cases']}` ({metrics['audit_detected_rate']:.2%})",
            f"- repair RAG relevant: `{metrics['repair_rag_relevant_count']}/{metrics['total_cases']}` ({metrics['repair_rag_relevant_rate']:.2%})",
            f"- repair-loop repaired: `{metrics['repair_loop_repaired_count']}/{metrics['total_cases']}` ({metrics['repair_loop_repaired_rate']:.2%})",
            f"- audit recovered: `{metrics['audit_recovered_count']}/{metrics['total_cases']}` ({metrics['audit_recovered_rate']:.2%})",
            f"- full success: `{metrics['full_success_count']}/{metrics['total_cases']}` ({metrics['full_success_rate']:.2%})",
            f"- total repair RAG hits: `{metrics['repair_rag_hits_count']}`",
            "",
            "## Upstream Failure Lab",
            "",
            f"- json: `{result.failure_lab_report_json_path or ''}`",
            f"- report: `{result.failure_lab_report_md_path or ''}`",
            "",
            "## Cases",
            "",
        ]
        for case in result.cases:
            lines.extend(
                [
                    f"### {case.identifier}",
                    "",
                    f"- title: {case.title}",
                    f"- success: `{str(case.success).lower()}`",
                    f"- audit detected: `{str(case.audit_detected).lower()}`",
                    f"- repair RAG relevant: `{str(case.repair_rag_relevant).lower()}`",
                    f"- repair-loop repaired: `{str(case.repair_loop_repaired).lower()}`",
                    f"- audit recovered: `{str(case.audit_recovered).lower()}`",
                    f"- RAG hits: `{case.repair_rag_hits_count}`",
                    f"- expected RAG capabilities: `{', '.join(case.expected_rag_capabilities)}`",
                    f"- actual RAG capabilities: `{', '.join(case.repair_rag_capabilities)}`",
                    f"- workspace: `{case.workspace or ''}`",
                    f"- audit report: `{case.artifacts.get('audit_report') or ''}`",
                    f"- repair RAG report: `{case.artifacts.get('repair_rag_report_md') or ''}`",
                    f"- repair loop report: `{case.artifacts.get('repair_loop_report_md') or ''}`",
                    "",
                ]
            )
            if case.detected_issue_ids:
                lines.append("Detected issue ids:")
                lines.extend(f"- `{issue_id}`" for issue_id in case.detected_issue_ids)
                lines.append("")
            if case.repair_rag_knowledge_ids:
                lines.append("Repair RAG knowledge ids:")
                lines.extend(f"- `{knowledge_id}`" for knowledge_id in case.repair_rag_knowledge_ids)
                lines.append("")
            if case.errors:
                lines.append("Errors:")
                lines.extend(f"- {error}" for error in case.errors)
                lines.append("")
        return "\n".join(lines)


def _case_from_failure_lab(case: FailureLabCaseResult) -> RepairEvalCaseResult:
    audit_detected = case.initial_audit_success is False and case.detected_expected_failure
    repair_rag_relevant = bool(case.repair_rag_attempted and case.repair_rag_hits_count > 0 and case.repair_rag_relevant)
    repair_loop_repaired = case.repair_success is True
    audit_recovered = case.final_audit_success is True
    success = audit_detected and repair_rag_relevant and repair_loop_repaired and audit_recovered
    return RepairEvalCaseResult(
        identifier=case.identifier,
        title=case.title,
        workspace=str(case.workspace) if case.workspace else None,
        audit_detected=audit_detected,
        repair_rag_relevant=repair_rag_relevant,
        repair_loop_repaired=repair_loop_repaired,
        audit_recovered=audit_recovered,
        success=success,
        initial_audit_errors_count=case.initial_audit_errors_count,
        repair_rag_hits_count=case.repair_rag_hits_count,
        detected_issue_ids=list(case.detected_issue_ids),
        expected_rag_capabilities=list(case.expected_rag_capabilities),
        repair_rag_capabilities=list(case.repair_rag_capabilities),
        repair_rag_knowledge_ids=list(case.repair_rag_knowledge_ids),
        artifacts={
            "audit_report": case.initial_audit_report_path,
            "repair_rag_report_json": case.repair_rag_report_json_path,
            "repair_rag_report_md": case.repair_rag_report_md_path,
            "repair_loop_report_json": case.repair_loop_report_json_path,
            "repair_loop_report_md": case.repair_loop_report_md_path,
        },
        errors=list(case.errors),
    )


def _metrics(cases: list[RepairEvalCaseResult]) -> dict[str, Any]:
    total = len(cases)
    audit_detected = sum(1 for case in cases if case.audit_detected)
    repair_rag_relevant = sum(1 for case in cases if case.repair_rag_relevant)
    repair_loop_repaired = sum(1 for case in cases if case.repair_loop_repaired)
    audit_recovered = sum(1 for case in cases if case.audit_recovered)
    full_success = sum(1 for case in cases if case.success)
    return {
        "total_cases": total,
        "audit_detected_count": audit_detected,
        "audit_detected_rate": _rate(audit_detected, total),
        "repair_rag_relevant_count": repair_rag_relevant,
        "repair_rag_relevant_rate": _rate(repair_rag_relevant, total),
        "repair_loop_repaired_count": repair_loop_repaired,
        "repair_loop_repaired_rate": _rate(repair_loop_repaired, total),
        "audit_recovered_count": audit_recovered,
        "audit_recovered_rate": _rate(audit_recovered, total),
        "full_success_count": full_success,
        "full_success_rate": _rate(full_success, total),
        "repair_rag_hits_count": sum(case.repair_rag_hits_count for case in cases),
    }


def _rate(count: int, total: int) -> float:
    return float(count / total) if total else 0.0
