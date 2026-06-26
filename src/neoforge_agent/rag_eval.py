from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .knowledge_base import KnowledgeHit, NeoForgeKnowledgeBase, expand_knowledge_query
from .tools import ensure_directory, write_json, write_text


DEFAULT_RECALL_K = 3


@dataclass(slots=True)
class RAGEvalCase:
    identifier: str
    query: str
    expected_knowledge_ids: list[str] = field(default_factory=list)
    expected_categories: list[str] = field(default_factory=list)
    expected_capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "query": self.query,
            "expected_knowledge_ids": list(self.expected_knowledge_ids),
            "expected_categories": list(self.expected_categories),
            "expected_capabilities": list(self.expected_capabilities),
        }


@dataclass(slots=True)
class RAGEvalCaseResult:
    identifier: str
    query: str
    expected_knowledge_ids: list[str]
    expected_categories: list[str]
    expected_capabilities: list[str]
    query_expansions: list[str]
    raw_hits: list[dict[str, Any]]
    expanded_hits: list[dict[str, Any]]
    raw_best_rank: int | None
    expanded_best_rank: int | None
    raw_recall_at_1: bool
    raw_recall_at_k: bool
    expanded_recall_at_1: bool
    expanded_recall_at_k: bool
    raw_expected_category_hit: bool
    expanded_expected_category_hit: bool
    raw_expected_capability_hit: bool
    expanded_expected_capability_hit: bool
    query_rewrite_rank_delta: int | None
    query_rewrite_recall_at_k_delta: int
    success: bool
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "query": self.query,
            "expected_knowledge_ids": list(self.expected_knowledge_ids),
            "expected_categories": list(self.expected_categories),
            "expected_capabilities": list(self.expected_capabilities),
            "query_expansions": list(self.query_expansions),
            "raw_hits": list(self.raw_hits),
            "expanded_hits": list(self.expanded_hits),
            "raw_best_rank": self.raw_best_rank,
            "expanded_best_rank": self.expanded_best_rank,
            "raw_recall_at_1": self.raw_recall_at_1,
            "raw_recall_at_k": self.raw_recall_at_k,
            "expanded_recall_at_1": self.expanded_recall_at_1,
            "expanded_recall_at_k": self.expanded_recall_at_k,
            "raw_expected_category_hit": self.raw_expected_category_hit,
            "expanded_expected_category_hit": self.expanded_expected_category_hit,
            "raw_expected_capability_hit": self.raw_expected_capability_hit,
            "expanded_expected_capability_hit": self.expanded_expected_capability_hit,
            "query_rewrite_rank_delta": self.query_rewrite_rank_delta,
            "query_rewrite_recall_at_k_delta": self.query_rewrite_recall_at_k_delta,
            "success": self.success,
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class RAGEvalResult:
    success: bool
    run_id: str
    report_dir: Path
    cases_path: str | None
    limit: int
    recall_k: int
    metrics: dict[str, Any]
    cases: list[RAGEvalCaseResult]
    failed_cases: list[str]
    rag_eval_report_json_path: Path
    rag_eval_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "cases_path": self.cases_path,
            "limit": self.limit,
            "recall_k": self.recall_k,
            "metrics": dict(self.metrics),
            "cases": [case.to_dict() for case in self.cases],
            "cases_count": len(self.cases),
            "failed_cases": list(self.failed_cases),
            "failed_cases_count": len(self.failed_cases),
            "rag_eval_report_json_path": str(self.rag_eval_report_json_path),
            "rag_eval_report_md_path": str(self.rag_eval_report_md_path),
        }


class RAGEvalRunner:
    def __init__(self, config: AppConfig | None = None, knowledge_base: NeoForgeKnowledgeBase | None = None) -> None:
        self.config = config or AppConfig.default()
        self.knowledge_base = knowledge_base or NeoForgeKnowledgeBase()

    def run(
        self,
        *,
        cases_path: Path | None = None,
        run_name: str | None = None,
        limit: int = 5,
        recall_k: int = DEFAULT_RECALL_K,
    ) -> RAGEvalResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        resolved_limit = max(1, min(limit, 12))
        resolved_recall_k = max(1, min(recall_k, resolved_limit))
        cases = self._load_cases(cases_path)
        results = [self._evaluate_case(case, limit=resolved_limit, recall_k=resolved_recall_k) for case in cases]
        metrics = _metrics(results)
        failed_cases = [case.identifier for case in results if not case.success]
        success = bool(results) and not failed_cases

        report_dir = ensure_directory(self.config.workspace_root / "rag-eval-runs" / run_id / ".agent")
        report_json = report_dir / "rag-eval-report.json"
        report_md = report_dir / "rag-eval-report.md"
        result = RAGEvalResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            cases_path=str(cases_path) if cases_path else None,
            limit=resolved_limit,
            recall_k=resolved_recall_k,
            metrics=metrics,
            cases=results,
            failed_cases=failed_cases,
            rag_eval_report_json_path=report_json,
            rag_eval_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_markdown(result))
        return result

    def _load_cases(self, cases_path: Path | None) -> list[RAGEvalCase]:
        path = cases_path
        if path is None:
            default_path = self.config.project_root / "examples" / "rag_eval_cases.json"
            path = default_path if default_path.exists() else None
        if path is None:
            return default_rag_eval_cases()
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("cases", [])
        if not isinstance(data, list):
            raise ValueError("RAG eval cases file must contain a list or an object with a 'cases' list.")
        return [_case_from_dict(item) for item in data if isinstance(item, dict)]

    def _evaluate_case(self, case: RAGEvalCase, *, limit: int, recall_k: int) -> RAGEvalCaseResult:
        raw_hits = self.knowledge_base.query(case.query, limit=limit, use_query_expansion=False)
        expanded_hits = self.knowledge_base.query(case.query, limit=limit, use_query_expansion=True)
        raw_best_rank = _best_rank(raw_hits, case.expected_knowledge_ids)
        expanded_best_rank = _best_rank(expanded_hits, case.expected_knowledge_ids)
        raw_recall_at_1 = _rank_within(raw_best_rank, 1)
        raw_recall_at_k = _rank_within(raw_best_rank, recall_k)
        expanded_recall_at_1 = _rank_within(expanded_best_rank, 1)
        expanded_recall_at_k = _rank_within(expanded_best_rank, recall_k)
        raw_expected_category_hit = _category_hit(raw_hits, case.expected_categories, recall_k=recall_k)
        expanded_expected_category_hit = _category_hit(expanded_hits, case.expected_categories, recall_k=recall_k)
        raw_expected_capability_hit = _capability_hit(raw_hits, case.expected_capabilities, recall_k=recall_k)
        expanded_expected_capability_hit = _capability_hit(expanded_hits, case.expected_capabilities, recall_k=recall_k)
        errors: list[str] = []
        if case.expected_knowledge_ids and not expanded_recall_at_k:
            errors.append(f"expected knowledge id not found in top {recall_k}: {', '.join(case.expected_knowledge_ids)}")
        if case.expected_categories and not expanded_expected_category_hit:
            errors.append(f"expected category not found in top {recall_k}: {', '.join(case.expected_categories)}")
        if case.expected_capabilities and not expanded_expected_capability_hit:
            errors.append(f"expected capability not found in top {recall_k}: {', '.join(case.expected_capabilities)}")
        success = not errors
        return RAGEvalCaseResult(
            identifier=case.identifier,
            query=case.query,
            expected_knowledge_ids=list(case.expected_knowledge_ids),
            expected_categories=list(case.expected_categories),
            expected_capabilities=list(case.expected_capabilities),
            query_expansions=expand_knowledge_query(case.query),
            raw_hits=[_hit_to_eval_dict(hit) for hit in raw_hits],
            expanded_hits=[_hit_to_eval_dict(hit) for hit in expanded_hits],
            raw_best_rank=raw_best_rank,
            expanded_best_rank=expanded_best_rank,
            raw_recall_at_1=raw_recall_at_1,
            raw_recall_at_k=raw_recall_at_k,
            expanded_recall_at_1=expanded_recall_at_1,
            expanded_recall_at_k=expanded_recall_at_k,
            raw_expected_category_hit=raw_expected_category_hit,
            expanded_expected_category_hit=expanded_expected_category_hit,
            raw_expected_capability_hit=raw_expected_capability_hit,
            expanded_expected_capability_hit=expanded_expected_capability_hit,
            query_rewrite_rank_delta=_rank_delta(raw_best_rank, expanded_best_rank),
            query_rewrite_recall_at_k_delta=int(expanded_recall_at_k) - int(raw_recall_at_k),
            success=success,
            errors=errors,
        )

    def _render_markdown(self, result: RAGEvalResult) -> str:
        metrics = result.metrics
        lines = [
            "# RAG Eval Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Run ID: `{result.run_id}`",
            f"Cases: `{metrics['total_cases']}`",
            f"Recall K: `{result.recall_k}`",
            "",
            "## Metrics",
            "",
            f"- expanded Recall@1: `{metrics['expanded_recall_at_1']:.2%}`",
            f"- expanded Recall@{result.recall_k}: `{metrics['expanded_recall_at_k']:.2%}`",
            f"- expanded MRR: `{metrics['expanded_mrr']:.4f}`",
            f"- expected category hit rate: `{metrics['expanded_expected_category_hit_rate']:.2%}`",
            f"- expected capability hit rate: `{metrics['expanded_expected_capability_hit_rate']:.2%}`",
            f"- raw Recall@1: `{metrics['raw_recall_at_1']:.2%}`",
            f"- raw Recall@{result.recall_k}: `{metrics['raw_recall_at_k']:.2%}`",
            f"- raw MRR: `{metrics['raw_mrr']:.4f}`",
            f"- query rewrite Recall@{result.recall_k} delta: `{metrics['query_rewrite_recall_at_k_delta']:.2%}`",
            f"- query rewrite MRR delta: `{metrics['query_rewrite_mrr_delta']:.4f}`",
            f"- improved cases: `{metrics['query_rewrite_improved_cases']}`",
            f"- regressed cases: `{metrics['query_rewrite_regressed_cases']}`",
            "",
            "## Cases",
            "",
        ]
        for case in result.cases:
            lines.extend(
                [
                    f"### {case.identifier}",
                    "",
                    f"- query: `{case.query}`",
                    f"- success: `{str(case.success).lower()}`",
                    f"- expected ids: `{', '.join(case.expected_knowledge_ids)}`",
                    f"- expected categories: `{', '.join(case.expected_categories)}`",
                    f"- expected capabilities: `{', '.join(case.expected_capabilities)}`",
                    f"- expansions: `{', '.join(case.query_expansions)}`",
                    f"- raw best rank: `{case.raw_best_rank or 'miss'}`",
                    f"- expanded best rank: `{case.expanded_best_rank or 'miss'}`",
                    f"- rank delta: `{case.query_rewrite_rank_delta if case.query_rewrite_rank_delta is not None else 'n/a'}`",
                    f"- raw top ids: `{', '.join(hit['id'] for hit in case.raw_hits)}`",
                    f"- expanded top ids: `{', '.join(hit['id'] for hit in case.expanded_hits)}`",
                    "",
                ]
            )
            if case.errors:
                lines.append("Errors:")
                lines.extend(f"- {error}" for error in case.errors)
                lines.append("")
        return "\n".join(lines)


def default_rag_eval_cases() -> list[RAGEvalCase]:
    return [
        RAGEvalCase(
            identifier="worldgen_ore_overworld",
            query="ruby ore overworld underground y -64 to 32 vein size",
            expected_knowledge_ids=["worldgen.overworld_ore"],
            expected_categories=["worldgen"],
            expected_capabilities=["overworld_ore"],
        ),
        RAGEvalCase(
            identifier="right_click_heal_item",
            query="right click ruby charm heal player cooldown custom item",
            expected_knowledge_ids=["behavior.right_click_item"],
            expected_categories=["behavior"],
            expected_capabilities=["right_click_behavior"],
        ),
        RAGEvalCase(
            identifier="procedural_texture_asset",
            query="generated png texture manifest 16x16 rgba asset model",
            expected_knowledge_ids=["assets.procedural_textures"],
            expected_categories=["assets"],
            expected_capabilities=["procedural_textures"],
        ),
        RAGEvalCase(
            identifier="controlled_java_extension",
            query="safe controlled java extension sandbox allowed imports rollback audit build",
            expected_knowledge_ids=["java.controlled_extension"],
            expected_categories=["java"],
            expected_capabilities=["controlled_java_extension"],
        ),
        RAGEvalCase(
            identifier="tool_armor_equipment",
            query="ruby pickaxe helmet tool armor equipment set deterministic recipe",
            expected_knowledge_ids=["content.tools_armor"],
            expected_categories=["content"],
            expected_capabilities=["tools_armor"],
        ),
        RAGEvalCase(
            identifier="unsupported_boundaries",
            query="unsupported arbitrary gui handwritten java custom terrain network",
            expected_knowledge_ids=["unsupported.boundaries"],
            expected_categories=["limits"],
            expected_capabilities=["unsupported_boundaries"],
        ),
    ]


def _case_from_dict(data: dict[str, Any]) -> RAGEvalCase:
    return RAGEvalCase(
        identifier=str(data.get("id") or data.get("identifier") or "rag_eval_case"),
        query=str(data.get("query") or ""),
        expected_knowledge_ids=_string_list(data.get("expected_knowledge_ids")),
        expected_categories=_string_list(data.get("expected_categories")),
        expected_capabilities=_string_list(data.get("expected_capabilities")),
    )


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def _hit_to_eval_dict(hit: KnowledgeHit) -> dict[str, Any]:
    data = hit.to_dict()
    return {
        "id": data["id"],
        "title": data["title"],
        "category": data["category"],
        "capability": data["capability"],
        "score": data["score"],
        "matched_terms": data["matched_terms"],
    }


def _best_rank(hits: list[KnowledgeHit], expected_ids: list[str]) -> int | None:
    expected = set(expected_ids)
    if not expected:
        return None
    for index, hit in enumerate(hits, start=1):
        if hit.entry.identifier in expected:
            return index
    return None


def _rank_within(rank: int | None, limit: int) -> bool:
    return rank is not None and rank <= limit


def _category_hit(hits: list[KnowledgeHit], expected_categories: list[str], *, recall_k: int) -> bool:
    if not expected_categories:
        return True
    expected = set(expected_categories)
    return any(hit.entry.category in expected for hit in hits[:recall_k])


def _capability_hit(hits: list[KnowledgeHit], expected_capabilities: list[str], *, recall_k: int) -> bool:
    if not expected_capabilities:
        return True
    expected = set(expected_capabilities)
    return any((hit.entry.capability or hit.entry.category) in expected for hit in hits[:recall_k])


def _rank_delta(raw_rank: int | None, expanded_rank: int | None) -> int | None:
    if raw_rank is None and expanded_rank is None:
        return None
    if raw_rank is None and expanded_rank is not None:
        return 99 - expanded_rank
    if raw_rank is not None and expanded_rank is None:
        return -99
    if raw_rank is None or expanded_rank is None:
        return None
    return raw_rank - expanded_rank


def _metrics(results: list[RAGEvalCaseResult]) -> dict[str, Any]:
    total = len(results)
    raw_recall_at_1_count = sum(1 for result in results if result.raw_recall_at_1)
    raw_recall_at_k_count = sum(1 for result in results if result.raw_recall_at_k)
    expanded_recall_at_1_count = sum(1 for result in results if result.expanded_recall_at_1)
    expanded_recall_at_k_count = sum(1 for result in results if result.expanded_recall_at_k)
    raw_category_count = sum(1 for result in results if result.raw_expected_category_hit)
    expanded_category_count = sum(1 for result in results if result.expanded_expected_category_hit)
    raw_capability_count = sum(1 for result in results if result.raw_expected_capability_hit)
    expanded_capability_count = sum(1 for result in results if result.expanded_expected_capability_hit)
    success_count = sum(1 for result in results if result.success)
    improved_count = sum(1 for result in results if (result.query_rewrite_rank_delta or 0) > 0 or result.query_rewrite_recall_at_k_delta > 0)
    regressed_count = sum(1 for result in results if (result.query_rewrite_rank_delta or 0) < 0 or result.query_rewrite_recall_at_k_delta < 0)
    raw_mrr = _mrr([result.raw_best_rank for result in results])
    expanded_mrr = _mrr([result.expanded_best_rank for result in results])
    return {
        "total_cases": total,
        "success_count": success_count,
        "success_rate": _rate(success_count, total),
        "raw_recall_at_1_count": raw_recall_at_1_count,
        "raw_recall_at_1": _rate(raw_recall_at_1_count, total),
        "raw_recall_at_k_count": raw_recall_at_k_count,
        "raw_recall_at_k": _rate(raw_recall_at_k_count, total),
        "raw_mrr": raw_mrr,
        "raw_expected_category_hit_count": raw_category_count,
        "raw_expected_category_hit_rate": _rate(raw_category_count, total),
        "raw_expected_capability_hit_count": raw_capability_count,
        "raw_expected_capability_hit_rate": _rate(raw_capability_count, total),
        "expanded_recall_at_1_count": expanded_recall_at_1_count,
        "expanded_recall_at_1": _rate(expanded_recall_at_1_count, total),
        "expanded_recall_at_k_count": expanded_recall_at_k_count,
        "expanded_recall_at_k": _rate(expanded_recall_at_k_count, total),
        "expanded_mrr": expanded_mrr,
        "expanded_expected_category_hit_count": expanded_category_count,
        "expanded_expected_category_hit_rate": _rate(expanded_category_count, total),
        "expanded_expected_capability_hit_count": expanded_capability_count,
        "expanded_expected_capability_hit_rate": _rate(expanded_capability_count, total),
        "query_rewrite_recall_at_1_delta": _rate(expanded_recall_at_1_count, total) - _rate(raw_recall_at_1_count, total),
        "query_rewrite_recall_at_k_delta": _rate(expanded_recall_at_k_count, total) - _rate(raw_recall_at_k_count, total),
        "query_rewrite_mrr_delta": round(expanded_mrr - raw_mrr, 4),
        "query_rewrite_improved_cases": improved_count,
        "query_rewrite_regressed_cases": regressed_count,
    }


def _mrr(ranks: list[int | None]) -> float:
    if not ranks:
        return 0.0
    return round(sum((1 / rank) if rank else 0.0 for rank in ranks) / len(ranks), 4)


def _rate(count: int, total: int) -> float:
    return float(count / total) if total else 0.0
