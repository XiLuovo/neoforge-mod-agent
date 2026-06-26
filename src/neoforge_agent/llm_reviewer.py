from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .agent_models import AgentPromptTrace
from .agentic_rag import sensitive_patch_paths
from .config import AppConfig
from .llm_client import LLMClient, create_llm_client


LLM_REVIEWER_SYSTEM_PROMPT = """LLM_REVIEWER
You are a constrained NeoForge reviewer. Respond with exactly one JSON object.
Review only the provided evidence. Do not invent files or runtime results.
The deterministic audit/build gates remain the final success authority.

Response schema:
{
  "coverage_status": "pass|partial|fail",
  "covered_requirements": ["short strings"],
  "missing_requirements": ["short strings"],
  "unsupported_or_risky_requests": ["short strings"],
  "patch_risks": ["short strings"],
  "recommended_checks": ["short strings"],
  "evidence_sufficiency": "sufficient|insufficient|not_required",
  "unsupported_citation_gaps": ["short strings"],
  "requires_more_rag": false,
  "decision": "approve|needs_repair|reject",
  "confidence": 0.0
}
"""

MAX_REVIEW_PROMPT_CHARS = 80_000
VALID_COVERAGE = {"pass", "partial", "fail"}
VALID_DECISIONS = {"approve", "needs_repair", "reject"}
VALID_EVIDENCE_SUFFICIENCY = {"sufficient", "insufficient", "not_required"}


@dataclass(slots=True)
class LLMReviewResult:
    success: bool
    reviewer_report: dict[str, Any]
    prompt_trace: AgentPromptTrace
    provider: str
    model: str
    warnings: list[str] = field(default_factory=list)

    @property
    def decision(self) -> str:
        return str(self.reviewer_report.get("decision", "needs_repair"))

    @property
    def coverage_status(self) -> str:
        return str(self.reviewer_report.get("coverage_status", "partial"))

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.reviewer_report)
        payload["success"] = self.success
        payload["status"] = "pass" if self.decision == "approve" else "warning" if self.decision == "needs_repair" else "fail"
        payload["checks"] = reviewer_checks(self.reviewer_report)
        payload["provider"] = self.provider
        payload["model"] = self.model
        payload["warnings"] = list(self.warnings)
        payload["source"] = "llm_reviewer"
        return payload


class LLMReviewer:
    def __init__(self, config: AppConfig | None = None, *, llm_client: LLMClient | None = None) -> None:
        self.config = config or AppConfig.default()
        self.llm_client = llm_client

    def review(
        self,
        *,
        workspace: Path | None,
        user_goal: str,
        llm_provider: str,
        review_stage: str,
        intent_contract: dict[str, Any] | None = None,
        modspec: dict[str, Any] | None = None,
        rag: dict[str, Any] | None = None,
        tool_call_trace: list[dict[str, Any]] | None = None,
        changed_files: list[str] | None = None,
        audit_result: dict[str, Any] | None = None,
        build_result: dict[str, Any] | None = None,
        prior_reviewer_observation: dict[str, Any] | None = None,
    ) -> LLMReviewResult:
        client = self.llm_client or create_llm_client(llm_provider, self.config.project_root)
        user_prompt = self._build_prompt(
            workspace=workspace,
            user_goal=user_goal,
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
        completion = client.complete_json(LLM_REVIEWER_SYSTEM_PROMPT, user_prompt)
        report, warnings = normalize_reviewer_payload(completion.parsed_json)
        warnings.extend(
            enforce_evidence_sufficiency(
                report,
                rag=rag or {},
                tool_call_trace=tool_call_trace or [],
                changed_files=changed_files or [],
            )
        )
        trace = AgentPromptTrace(
            role="reviewer_agent",
            planner_mode="llm_reviewer",
            provider=completion.provider,
            prompt_kind=f"reviewer_{review_stage}",
            system_prompt=LLM_REVIEWER_SYSTEM_PROMPT,
            input_text=user_prompt,
            raw_text=completion.raw_text,
            raw_json=completion.parsed_json,
            normalized_json=report,
            warnings=warnings,
            completion_usage=completion.telemetry_dict(),
        )
        success = report["decision"] == "approve" and report["coverage_status"] == "pass"
        return LLMReviewResult(
            success=success,
            reviewer_report=report,
            prompt_trace=trace,
            provider=completion.provider,
            model=completion.model,
            warnings=warnings,
        )

    def _build_prompt(
        self,
        *,
        workspace: Path | None,
        user_goal: str,
        review_stage: str,
        intent_contract: dict[str, Any] | None,
        modspec: dict[str, Any] | None,
        rag: dict[str, Any] | None,
        tool_call_trace: list[dict[str, Any]] | None,
        changed_files: list[str] | None,
        audit_result: dict[str, Any] | None,
        build_result: dict[str, Any] | None,
        prior_reviewer_observation: dict[str, Any] | None,
    ) -> str:
        payload = {
            "review_stage": review_stage,
            "user_goal": user_goal,
            "workspace": str(workspace or ""),
            "intent_contract": _compact(intent_contract or {}),
            "modspec": _compact(modspec or {}),
            "rag_snippets": _compact(_rag_snippets(rag or {})),
            "tool_call_trace_summary": _compact(_tool_trace_summary(tool_call_trace or [])),
            "rag_evidence_summary": _compact(_rag_evidence_summary(rag or {}, tool_call_trace or [])),
            "changed_files_summary": list(changed_files or []),
            "audit_result": _compact(audit_result or {}),
            "build_result": _compact(build_result or {}),
            "prior_reviewer_observation": _compact(prior_reviewer_observation or {}),
            "review_rules": {
                "final_gate_authority": "deterministic audit/build",
                "reviewer_can_recommend_repair": True,
                "reviewer_can_override_failed_gate": False,
                "sensitive_patch_requires_rag_or_file_evidence": True,
                "hidden_chain_of_thought": "do not include",
            },
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return text[:MAX_REVIEW_PROMPT_CHARS]


def normalize_reviewer_payload(raw: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if not isinstance(raw, dict):
        raw = {}
        warnings.append("Reviewer LLM response was not a JSON object.")
    coverage_status = str(raw.get("coverage_status", "partial")).strip().lower()
    if coverage_status not in VALID_COVERAGE:
        warnings.append(f"Invalid reviewer coverage_status: {coverage_status}")
        coverage_status = "partial"
    decision = str(raw.get("decision", "needs_repair")).strip().lower()
    if decision not in VALID_DECISIONS:
        warnings.append(f"Invalid reviewer decision: {decision}")
        decision = "needs_repair"
    confidence = raw.get("confidence", 0.0)
    try:
        confidence_float = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence_float = 0.0
        warnings.append("Reviewer confidence was not numeric.")
    evidence_sufficiency = str(raw.get("evidence_sufficiency", "") or "").strip().lower()
    if evidence_sufficiency not in VALID_EVIDENCE_SUFFICIENCY:
        evidence_sufficiency = "insufficient" if raw.get("requires_more_rag") else "sufficient"
        warnings.append("Reviewer evidence_sufficiency was missing or invalid; a safe default was used.")
    requires_more_rag = bool(raw.get("requires_more_rag")) or evidence_sufficiency == "insufficient"
    if requires_more_rag and decision == "approve":
        decision = "needs_repair"
        coverage_status = "partial" if coverage_status == "pass" else coverage_status
        warnings.append("Reviewer requested more RAG; decision was downgraded to needs_repair.")
    report = {
        "coverage_status": coverage_status,
        "covered_requirements": _string_list(raw.get("covered_requirements")),
        "missing_requirements": _string_list(raw.get("missing_requirements")),
        "unsupported_or_risky_requests": _string_list(raw.get("unsupported_or_risky_requests")),
        "patch_risks": _string_list(raw.get("patch_risks")),
        "recommended_checks": _string_list(raw.get("recommended_checks")),
        "evidence_sufficiency": evidence_sufficiency,
        "unsupported_citation_gaps": _string_list(raw.get("unsupported_citation_gaps")),
        "requires_more_rag": requires_more_rag,
        "decision": decision,
        "confidence": confidence_float,
    }
    return report, warnings


def enforce_evidence_sufficiency(
    report: dict[str, Any],
    *,
    rag: dict[str, Any],
    tool_call_trace: list[dict[str, Any]],
    changed_files: list[str],
) -> list[str]:
    warnings: list[str] = []
    patch_paths = _changed_files_from_trace(tool_call_trace)
    sensitive_paths = sensitive_patch_paths(patch_paths)
    if not sensitive_paths:
        if report.get("evidence_sufficiency") not in VALID_EVIDENCE_SUFFICIENCY:
            report["evidence_sufficiency"] = "not_required"
        return warnings

    if _has_rag_citation_evidence(rag, tool_call_trace) or _has_file_evidence(tool_call_trace, sensitive_paths):
        if report.get("evidence_sufficiency") == "insufficient" and not report.get("requires_more_rag"):
            report["evidence_sufficiency"] = "sufficient"
        return warnings

    gap = "Sensitive NeoForge patch lacks RAG citation or file-read evidence: " + ", ".join(sensitive_paths)
    gaps = report.get("unsupported_citation_gaps")
    if not isinstance(gaps, list):
        gaps = []
    if gap not in gaps:
        gaps.append(gap)
    report["unsupported_citation_gaps"] = gaps
    report["evidence_sufficiency"] = "insufficient"
    report["requires_more_rag"] = True
    if report.get("decision") == "approve":
        report["decision"] = "needs_repair"
        if report.get("coverage_status") == "pass":
            report["coverage_status"] = "partial"
    warnings.append("Reviewer evidence sufficiency gate required more RAG for a sensitive patch.")
    return warnings


def reviewer_checks(report: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "id": "coverage_status",
            "status": str(report.get("coverage_status", "partial")),
            "summary": f"Coverage status: {report.get('coverage_status', 'partial')}",
        },
        {
            "id": "missing_requirements",
            "status": "pass" if not report.get("missing_requirements") else "fail",
            "summary": f"Missing requirements: {len(report.get('missing_requirements') or [])}",
        },
        {
            "id": "patch_risks",
            "status": "pass" if not report.get("patch_risks") else "warning",
            "summary": f"Patch risks: {len(report.get('patch_risks') or [])}",
        },
        {
            "id": "evidence_sufficiency",
            "status": str(report.get("evidence_sufficiency", "sufficient")),
            "summary": f"Evidence sufficiency: {report.get('evidence_sufficiency', 'sufficient')}",
        },
        {
            "id": "unsupported_citation_gaps",
            "status": "pass" if not report.get("unsupported_citation_gaps") else "warning",
            "summary": f"Unsupported citation gaps: {len(report.get('unsupported_citation_gaps') or [])}",
        },
        {
            "id": "decision",
            "status": str(report.get("decision", "needs_repair")),
            "summary": f"Reviewer decision: {report.get('decision', 'needs_repair')}",
        },
    ]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _rag_snippets(rag: dict[str, Any]) -> dict[str, Any]:
    hits = rag.get("hits")
    if not isinstance(hits, list):
        hits = []
    return {
        "hits_count": rag.get("hits_count", len(hits)),
        "hits": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "category": item.get("category"),
                "capability": item.get("capability"),
                "summary": item.get("summary"),
            }
            for item in hits[:8]
            if isinstance(item, dict)
        ],
        "queries": rag.get("queries") if isinstance(rag.get("queries"), list) else [],
        "citations": rag.get("citations") if isinstance(rag.get("citations"), list) else [],
        "sufficiency": rag.get("sufficiency"),
    }


def _tool_trace_summary(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for entry in trace[-12:]:
        if not isinstance(entry, dict):
            continue
        observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
        summary.append(
            {
                "iteration": entry.get("iteration"),
                "source": entry.get("source"),
                "action": entry.get("action"),
                "summary": observation.get("summary"),
                "success": observation.get("success"),
                "citations": observation.get("citations") or observation.get("citation_ids") or [],
                "sufficiency": observation.get("sufficiency"),
            }
        )
    return summary


def _rag_evidence_summary(rag: dict[str, Any], tool_call_trace: list[dict[str, Any]]) -> dict[str, Any]:
    retrieve_steps = []
    patch_steps = []
    for entry in tool_call_trace:
        if not isinstance(entry, dict):
            continue
        observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
        if entry.get("action") == "retrieve_rag":
            retrieve_steps.append(
                {
                    "iteration": entry.get("iteration"),
                    "query": observation.get("query"),
                    "queries": observation.get("queries") or [],
                    "citations": observation.get("citations") or [],
                    "sufficiency": observation.get("sufficiency"),
                    "rag_required": observation.get("rag_required"),
                }
            )
        if entry.get("action") == "apply_structured_patch":
            patch_steps.append(
                {
                    "iteration": entry.get("iteration"),
                    "changed_files": observation.get("changed_files") or [],
                    "citation_ids": observation.get("citation_ids") or observation.get("citations") or [],
                    "success": observation.get("success"),
                }
            )
    return {
        "rag_hits_count": rag.get("hits_count", 0),
        "rag_citations": rag.get("citations") or [],
        "retrieve_steps": retrieve_steps[-6:],
        "patch_steps": patch_steps[-6:],
    }


def _changed_files_from_trace(trace: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for entry in trace:
        if not isinstance(entry, dict) or entry.get("action") != "apply_structured_patch":
            continue
        observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
        for path in observation.get("changed_files") or []:
            text = str(path).strip()
            if text and text not in paths:
                paths.append(text)
    return paths


def _has_rag_citation_evidence(rag: dict[str, Any], trace: list[dict[str, Any]]) -> bool:
    if isinstance(rag.get("citations"), list) and any(str(item).strip() for item in rag["citations"]):
        return True
    for entry in trace:
        if not isinstance(entry, dict):
            continue
        observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
        citations = observation.get("citation_ids") or observation.get("citations")
        if isinstance(citations, list) and any(str(item).strip() for item in citations):
            return True
    return False


def _has_file_evidence(trace: list[dict[str, Any]], sensitive_paths: list[str]) -> bool:
    sensitive_set = {path.replace("\\", "/") for path in sensitive_paths}
    for entry in trace:
        if not isinstance(entry, dict) or entry.get("action") not in {"read_file", "search_files"}:
            continue
        observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
        path = str(observation.get("path") or "").replace("\\", "/")
        if path in sensitive_set:
            return True
        matches = observation.get("matches") if isinstance(observation.get("matches"), list) else []
        for match in matches:
            if isinstance(match, dict) and str(match.get("path") or "").replace("\\", "/") in sensitive_set:
                return True
    return False


def _compact(value: Any, *, max_string: int = 2000) -> Any:
    if isinstance(value, dict):
        return {str(key): _compact(item, max_string=max_string) for key, item in value.items()}
    if isinstance(value, list):
        return [_compact(item, max_string=max_string) for item in value[:30]]
    if isinstance(value, str):
        return value[:max_string]
    return value
