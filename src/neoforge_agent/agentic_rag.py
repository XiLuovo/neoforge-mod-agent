from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .knowledge_base import KnowledgeHit, NeoForgeKnowledgeBase, summarize_knowledge_hits
from .tools import ensure_directory, write_json


SENSITIVE_RAG_PATTERNS = (
    "src/main/templates/META-INF/neoforge.mods.toml",
    "src/main/resources/pack.mcmeta",
    "src/main/resources/data/**",
    "src/main/resources/assets/**",
    "src/main/java/**/*Registry*.java",
    "src/main/java/**/*Registr*.java",
    "src/main/java/**/*Recipe*.java",
    "src/main/java/**/*Worldgen*.java",
    "src/main/java/**/*Loot*.java",
    "src/main/java/**/*Tag*.java",
)


@dataclass(slots=True)
class AgenticRAGDecision:
    decision_id: str
    rag_required: bool
    reason: str
    triggers: list[str] = field(default_factory=list)
    query: str = ""
    skipped: bool = False
    would_require_rag: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "rag_required": self.rag_required,
            "reason": self.reason,
            "triggers": list(self.triggers),
            "query": self.query,
            "skipped": self.skipped,
            "would_require_rag": self.would_require_rag,
        }


@dataclass(slots=True)
class AgenticRAGTrace:
    decision: AgenticRAGDecision
    queries: list[str]
    hops: list[dict[str, Any]]
    hits: list[dict[str, Any]]
    citations: list[str]
    sufficiency: str
    used_by_patch: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = self.decision.to_dict()
        payload.update(
            {
                "queries": list(self.queries),
                "hops": list(self.hops),
                "hits": list(self.hits),
                "hits_count": len(self.hits),
                "citations": list(self.citations),
                "sufficiency": self.sufficiency,
                "used_by_patch": self.used_by_patch,
            }
        )
        return payload


class AgenticRAGPolicy:
    def decide(
        self,
        *,
        reason: str,
        query: str,
        build: dict[str, Any] | None = None,
        audit: dict[str, Any] | None = None,
        changed_files: list[str] | None = None,
        reviewer_observation: dict[str, Any] | None = None,
        rag_mode: str = "auto",
        sequence: int = 1,
    ) -> AgenticRAGDecision:
        normalized_reason = (reason or "").strip() or "agent_requested_retrieval"
        triggers: list[str] = []
        if _gate_failed(build or {}):
            triggers.append("build_failure")
        if _gate_failed(audit or {}):
            triggers.append("audit_failure")
        if any(_is_sensitive_path(path) for path in changed_files or []):
            triggers.append("sensitive_patch")
        if _reviewer_requires_more_rag(reviewer_observation or {}):
            triggers.append("reviewer_evidence_insufficient")
        text = " ".join([normalized_reason, query or "", _gate_text(build or {}), _gate_text(audit or {})]).lower()
        if "unsupported" in text:
            triggers.append("unsupported_request")
        if any(token in text for token in ("unknown", "uncertain", "registry", "register", "resource path", "neoforge api")):
            triggers.append("neoforge_uncertainty")
        forced_on = rag_mode == "on"
        would_require = forced_on or bool(triggers)
        forced_off = rag_mode == "off"
        required = would_require and not forced_off
        if forced_off:
            triggers.append("rag_disabled")
        rewritten = rewrite_rag_query(
            query=query,
            reason=normalized_reason,
            build=build or {},
            audit=audit or {},
            changed_files=changed_files or [],
        )
        return AgenticRAGDecision(
            decision_id=f"rag-{sequence:03d}",
            rag_required=required,
            reason=normalized_reason,
            triggers=_dedupe(triggers),
            query=rewritten,
            skipped=forced_off,
            would_require_rag=would_require,
        )


class AgenticRAGRetriever:
    def __init__(self, knowledge_base: NeoForgeKnowledgeBase | None = None) -> None:
        self.knowledge_base = knowledge_base or NeoForgeKnowledgeBase()

    def retrieve(
        self,
        *,
        decision: AgenticRAGDecision,
        limit: int = 5,
        max_hops: int = 2,
    ) -> AgenticRAGTrace:
        if decision.skipped:
            return AgenticRAGTrace(
                decision=decision,
                queries=[decision.query] if decision.query else [],
                hops=[],
                hits=[],
                citations=[],
                sufficiency="insufficient" if decision.would_require_rag else "not_required",
            )
        resolved_limit = max(1, min(int(limit or 5), 12))
        resolved_hops = max(1, min(int(max_hops or 2), 3))
        queries: list[str] = []
        hops: list[dict[str, Any]] = []
        hits_by_id: dict[str, dict[str, Any]] = {}
        current_query = decision.query or "NeoForge repair audit build failure"
        for hop_index in range(1, resolved_hops + 1):
            if current_query in queries:
                break
            queries.append(current_query)
            hop_hits = [hit.to_dict() for hit in self.knowledge_base.query(current_query, limit=resolved_limit)]
            for hit in hop_hits:
                hit_id = str(hit.get("id") or "")
                if hit_id and hit_id not in hits_by_id:
                    hits_by_id[hit_id] = hit
            hops.append(
                {
                    "hop": hop_index,
                    "query": current_query,
                    "hits": hop_hits,
                    "hits_count": len(hop_hits),
                    "categories": summarize_knowledge_hits(hop_hits)["categories"],
                    "capabilities": summarize_knowledge_hits(hop_hits)["capabilities"],
                }
            )
            current_query = followup_query(current_query, hop_hits)
            if not current_query:
                break
        hits = list(hits_by_id.values())
        citations = [str(hit.get("id")) for hit in hits[:resolved_limit] if hit.get("id")]
        if citations:
            sufficiency = "sufficient"
        else:
            sufficiency = "insufficient" if decision.rag_required else "not_required"
        return AgenticRAGTrace(
            decision=decision,
            queries=queries,
            hops=hops,
            hits=hits,
            citations=citations,
            sufficiency=sufficiency,
        )


def rewrite_rag_query(
    *,
    query: str,
    reason: str,
    build: dict[str, Any],
    audit: dict[str, Any],
    changed_files: list[str],
) -> str:
    text = " ".join([query or "", reason or "", _gate_text(build), _gate_text(audit), " ".join(changed_files)]).lower()
    if "pack.mcmeta" in text or "pack_format" in text:
        return "NeoForge resource pack metadata pack.mcmeta pack_format rules"
    if "neoforge.mods.toml" in text or "mods.toml" in text:
        return "NeoForge mod metadata neoforge.mods.toml required fields"
    if "deferredregister" in text or "deferred register" in text or "registry" in text or "register" in text:
        return "NeoForge DeferredRegister registry object registration rules"
    if "recipe" in text or "data/" in text or "resource path" in text:
        return "Minecraft NeoForge recipe JSON data pack schema"
    if query.strip():
        return query.strip()
    return "NeoForge audit build repair generated workspace rules"


def followup_query(query: str, hits: list[dict[str, Any]]) -> str:
    if not hits:
        return ""
    top = hits[0]
    pieces = [
        "NeoForge",
        str(top.get("category") or ""),
        str(top.get("capability") or ""),
        str(top.get("title") or ""),
        "repair citation",
    ]
    candidate = " ".join(piece for piece in pieces if piece).strip()
    return candidate if candidate and candidate.lower() != query.lower() else ""


def write_rag_decision_trace(agent_dir: Path, traces: list[dict[str, Any]]) -> Path:
    path = ensure_directory(agent_dir) / "rag-decision-trace.json"
    write_json(path, traces)
    return path


def mark_latest_trace_used_by_patch(traces: list[dict[str, Any]], citation_ids: list[str]) -> None:
    for item in reversed(traces):
        if item.get("citations"):
            item["used_by_patch"] = True
            if citation_ids:
                item["patch_citation_ids"] = list(citation_ids)
            return


def sensitive_patch_paths(changed_files: list[str]) -> list[str]:
    return [path for path in changed_files if _is_sensitive_path(path)]


def citation_coverage(trace: list[dict[str, Any]]) -> float:
    patch_entries = [entry for entry in trace if entry.get("action") == "apply_structured_patch"]
    if not patch_entries:
        return 1.0
    covered = 0
    for entry in patch_entries:
        observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
        if observation.get("citation_ids") or observation.get("citations"):
            covered += 1
    return covered / len(patch_entries)


def _is_sensitive_path(path: str) -> bool:
    normalized = str(path).replace("\\", "/").strip()
    if not normalized:
        return False
    for pattern in SENSITIVE_RAG_PATTERNS:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def _gate_failed(payload: dict[str, Any]) -> bool:
    return bool(payload.get("attempted") and payload.get("success") is False)


def _gate_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("summary", "error"):
        if payload.get(key):
            parts.append(str(payload.get(key)))
    for key in ("errors", "issues"):
        values = payload.get(key)
        if isinstance(values, list):
            for item in values[:8]:
                if isinstance(item, dict):
                    parts.append(str(item.get("message") or item.get("summary") or item))
                else:
                    parts.append(str(item))
    return " ".join(parts)


def _reviewer_requires_more_rag(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("requires_more_rag")
        or payload.get("evidence_sufficiency") == "insufficient"
        or payload.get("unsupported_citation_gaps")
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
