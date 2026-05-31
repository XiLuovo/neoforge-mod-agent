from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AppConfig
from .knowledge_base import NeoForgeKnowledgeBase, expand_knowledge_query, summarize_knowledge_hits
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class RepairRAGResult:
    success: bool
    attempted: bool
    query: str
    limit: int
    hits: list[dict[str, Any]]
    categories: dict[str, int]
    capabilities: dict[str, int]
    context: str
    query_expansions: list[str] = field(default_factory=list)
    reason: str = ""
    report_json_path: Path | None = None
    report_md_path: Path | None = None

    @property
    def hits_count(self) -> int:
        return len(self.hits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "attempted": self.attempted,
            "reason": self.reason,
            "query": self.query,
            "limit": self.limit,
            "hits": list(self.hits),
            "hits_count": self.hits_count,
            "query_expansions": list(self.query_expansions),
            "categories": dict(self.categories),
            "capabilities": dict(self.capabilities),
            "context": self.context,
            "report_json_path": str(self.report_json_path) if self.report_json_path else None,
            "report_md_path": str(self.report_md_path) if self.report_md_path else None,
        }


class RepairRAGAdvisor:
    def __init__(
        self,
        config: AppConfig | None = None,
        knowledge_base: NeoForgeKnowledgeBase | None = None,
    ) -> None:
        self.config = config or AppConfig.default()
        self.knowledge_base = knowledge_base or NeoForgeKnowledgeBase()

    @staticmethod
    def skipped(reason: str) -> RepairRAGResult:
        return RepairRAGResult(
            success=True,
            attempted=False,
            reason=reason,
            query="",
            limit=0,
            hits=[],
            categories={},
            capabilities={},
            context="",
            query_expansions=[],
        )

    def advise(
        self,
        workspace: Path,
        *,
        root_causes: list[str],
        repair_plan: list[dict[str, str]],
        build_payload: dict[str, Any],
        audit_payload: dict[str, Any],
        limit: int = 5,
    ) -> RepairRAGResult:
        workspace = workspace.resolve()
        limit = max(1, min(limit, 12))
        query = _build_query(
            root_causes=root_causes,
            repair_plan=repair_plan,
            build_payload=build_payload,
            audit_payload=audit_payload,
        )
        hits = self.knowledge_base.query(query, limit=limit)
        hit_dicts = [hit.to_dict() for hit in hits]
        hit_summary = summarize_knowledge_hits(hit_dicts)
        result = RepairRAGResult(
            success=True,
            attempted=True,
            query=query,
            limit=limit,
            hits=hit_dicts,
            categories=hit_summary["categories"],
            capabilities=hit_summary["capabilities"],
            context=self.knowledge_base.render_context(query, limit=limit),
            query_expansions=expand_knowledge_query(query),
        )

        agent_dir = ensure_directory(self.config.agent_dir_for(workspace))
        result.report_json_path = agent_dir / "repair-rag-context.json"
        result.report_md_path = agent_dir / "repair-rag-context.md"
        write_json(result.report_json_path, result.to_dict())
        write_text(result.report_md_path, self._render_markdown(result))
        return result

    def _render_markdown(self, result: RepairRAGResult) -> str:
        lines = [
            "# Repair RAG Context",
            "",
            f"Success: {str(result.success).lower()}",
            f"Attempted: {str(result.attempted).lower()}",
            f"Query: `{result.query}`",
            f"Hits: `{result.hits_count}`",
            f"JSON: `{result.report_json_path or ''}`",
            f"Report: `{result.report_md_path or ''}`",
            "",
            "## Retrieved Knowledge",
            "",
        ]
        if not result.hits:
            lines.append("- No matching bundled knowledge snippets were found.")
        for hit in result.hits:
            lines.extend(
                [
                    f"- `{hit.get('id')}` score={hit.get('score')}: {hit.get('title')}",
                    f"  - category: `{hit.get('category')}`",
                    f"  - capability: `{hit.get('capability')}`",
                    f"  - summary: {hit.get('summary')}",
                ]
            )
        if result.query_expansions:
            lines.extend(["", "## Automatic Query Expansions", ""])
            lines.extend(f"- `{item}`" for item in result.query_expansions)
        lines.extend(["", "## Context", "", "```text", result.context, "```", ""])
        return "\n".join(lines)


def _build_query(
    *,
    root_causes: list[str],
    repair_plan: list[dict[str, str]],
    build_payload: dict[str, Any],
    audit_payload: dict[str, Any],
) -> str:
    parts: list[str] = ["repair audit build failure"]
    parts.extend(root_causes)
    for action in repair_plan:
        parts.extend(_dict_values(action, keys=("id", "summary", "artifact")))
    parts.extend(_payload_issue_parts(build_payload, issue_key="issues"))
    parts.extend(_payload_issue_parts(audit_payload, issue_key="errors"))
    parts.extend(_dict_values(build_payload, keys=("summary", "debug_context_path", "fix_request_path", "suspected_errors_path", "stdout_path", "stderr_path")))
    parts.extend(_dict_values(audit_payload, keys=("error", "audit_report_path", "audit_report_md_path")))
    return _compact_query(parts)


def _payload_issue_parts(payload: dict[str, Any], *, issue_key: str) -> list[str]:
    parts: list[str] = []
    issues = payload.get(issue_key)
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict):
                parts.extend(_dict_values(issue, keys=("id", "severity", "kind", "message", "path", "file")))
            elif issue is not None:
                parts.append(str(issue))
    return parts


def _dict_values(mapping: dict[str, Any], *, keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            values.append(text)
    return values


def _compact_query(parts: list[str]) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = " ".join(str(part).split())
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text[:500])
    query = " | ".join(cleaned)
    return query[:8000] if query else "repair audit build failure"
