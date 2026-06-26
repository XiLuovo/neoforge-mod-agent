from __future__ import annotations

from typing import Any


def normalize_code_lane(value: str) -> str:
    normalized = str(value or "hybrid").strip().lower()
    if normalized not in {"hybrid", "modspec", "direct"}:
        raise ValueError(f"Unsupported code lane: {value}")
    return normalized


def normalize_rag_mode(value: str) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized not in {"auto", "on", "off"}:
        raise ValueError(f"Unsupported RAG mode: {value}")
    return normalized


def reviewer_requires_more_rag(payload: dict[str, Any]) -> bool:
    return bool(
        isinstance(payload, dict)
        and (
            payload.get("requires_more_rag")
            or payload.get("evidence_sufficiency") == "insufficient"
            or payload.get("unsupported_citation_gaps")
        )
    )


def merge_generated_files(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            value = str(item).replace("\\", "/")
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(value)
    return merged
