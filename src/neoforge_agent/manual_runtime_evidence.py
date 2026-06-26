from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANUAL_RUNTIME_EVIDENCE_SCHEMA_VERSION = "manual-runtime-evidence/v1"
MANUAL_RUNTIME_EVIDENCE_KIND = "manual_minecraft_runtime"
MANUAL_RUNTIME_EVIDENCE_SCOPE = (
    "Manual runtime evidence records human-checked Minecraft client/server behavior. "
    "It complements workspace audit/build gates and never turns those gates into automatic runtime acceptance."
)


@dataclass(slots=True)
class ManualRuntimeEvidenceCase:
    identifier: str
    workspace: str
    status: str
    passed: bool
    source: str
    notes: str = ""
    evidence_kind: str = MANUAL_RUNTIME_EVIDENCE_KIND
    schema_version: str = MANUAL_RUNTIME_EVIDENCE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evidence_kind": self.evidence_kind,
            "id": self.identifier,
            "workspace": self.workspace,
            "status": self.status,
            "passed": self.passed,
            "source": self.source,
            "notes": self.notes,
        }


@dataclass(slots=True)
class ManualRuntimeEvidenceSummary:
    cases: list[ManualRuntimeEvidenceCase]
    scope: str = MANUAL_RUNTIME_EVIDENCE_SCOPE
    evidence_kind: str = MANUAL_RUNTIME_EVIDENCE_KIND
    schema_version: str = MANUAL_RUNTIME_EVIDENCE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        total = len(self.cases)
        passed = sum(1 for case in self.cases if case.passed)
        failed = sum(1 for case in self.cases if _manual_runtime_status_failed(case.status))
        blocked = sum(1 for case in self.cases if _manual_runtime_status_blocked(case.status))
        return {
            "schema_version": self.schema_version,
            "evidence_kind": self.evidence_kind,
            "scope": self.scope,
            "runtime_cases_total": total,
            "runtime_passed_count": passed,
            "runtime_failed_count": failed,
            "runtime_blocked_count": blocked,
            "runtime_pass_rate": _rate(passed, total),
            "runtime_cases": [case.to_dict() for case in self.cases],
        }


def load_manual_runtime_evidence_cases(
    runtime_evidence_path: Path | None,
    *,
    markdown_heading: str | None = None,
) -> list[ManualRuntimeEvidenceCase]:
    if runtime_evidence_path is None or not runtime_evidence_path.exists():
        return []
    text = runtime_evidence_path.read_text(encoding="utf-8")
    source = str(runtime_evidence_path)
    if runtime_evidence_path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("runtime_evidence_cases", data.get("runtime_cases", data.get("cases", [])))
        if not isinstance(data, list):
            raise ValueError("Runtime evidence JSON must contain a list or an object with a runtime evidence list.")
        return [
            manual_runtime_evidence_case_from_dict(item, source=source)
            for item in data
            if isinstance(item, dict)
        ]
    return manual_runtime_evidence_cases_from_markdown(text, source=source, markdown_heading=markdown_heading)


def summarize_manual_runtime_evidence(cases: list[ManualRuntimeEvidenceCase]) -> ManualRuntimeEvidenceSummary:
    return ManualRuntimeEvidenceSummary(cases=list(cases))


def manual_runtime_evidence_case_from_dict(data: dict[str, Any], *, source: str) -> ManualRuntimeEvidenceCase:
    status = str(data.get("status", data.get("result", ""))).strip()
    passed_value = data.get("passed", data.get("success"))
    passed = manual_runtime_status_passed(status) if passed_value is None else _bool_value(passed_value)
    if not status:
        status = "passed" if passed else "runtime_unverified"
    return ManualRuntimeEvidenceCase(
        identifier=str(data.get("id", data.get("identifier", data.get("case", "runtime_case")))),
        workspace=str(data.get("workspace", "")),
        status=status,
        passed=passed,
        source=str(data.get("source") or source),
        notes=str(data.get("notes", data.get("manual_runtime_checks", data.get("checks", "")))),
        evidence_kind=str(data.get("evidence_kind", data.get("kind", MANUAL_RUNTIME_EVIDENCE_KIND))),
        schema_version=str(data.get("schema_version", data.get("schema", MANUAL_RUNTIME_EVIDENCE_SCHEMA_VERSION))),
    )


def manual_runtime_evidence_cases_from_markdown(
    text: str,
    *,
    source: str,
    markdown_heading: str | None = None,
) -> list[ManualRuntimeEvidenceCase]:
    if markdown_heading:
        text = _section_after_heading(text, markdown_heading)
    cases: list[ManualRuntimeEvidenceCase] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        columns = [column.strip() for column in stripped.strip("|").split("|")]
        if len(columns) < 4 or columns[0].lower() in {"case", "id", "identifier"}:
            continue
        case_name, workspace, status, notes = columns[:4]
        if not case_name:
            continue
        cases.append(
            ManualRuntimeEvidenceCase(
                identifier=case_name,
                workspace=workspace.strip("`"),
                status=status,
                passed=manual_runtime_status_passed(status),
                source=source,
                notes=notes,
            )
        )
    return cases


def manual_runtime_status_passed(status: str) -> bool:
    normalized = status.strip().lower()
    if not normalized:
        return False
    if _manual_runtime_status_failed(normalized) or _manual_runtime_status_blocked(normalized):
        return False
    return any(token in normalized for token in ("passed", "pass", "success", "通过", "閫氳繃"))


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "passed", "pass", "success", "通过", "閫氳繃"}
    return bool(value)


def _manual_runtime_status_failed(status: str) -> bool:
    normalized = status.strip().lower()
    return any(token in normalized for token in ("not pass", "failed", "fail", "未通过", "失败", "鏈€氳繃"))


def _manual_runtime_status_blocked(status: str) -> bool:
    normalized = status.strip().lower()
    return any(token in normalized for token in ("blocked", "runtime_unverified", "unverified", "阻塞", "未验证"))


def _section_after_heading(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    rest = text[start + len(heading) :]
    next_heading = rest.find("\n## ")
    if next_heading >= 0:
        return rest[:next_heading]
    return rest


def _rate(count: int, total: int) -> float:
    return float(count / total) if total else 0.0
