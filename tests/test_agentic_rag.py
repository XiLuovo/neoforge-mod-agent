from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neoforge_agent import AgenticRAGPolicy, AgenticRAGRetriever
from neoforge_agent.agentic_rag import (
    mark_latest_trace_used_by_patch,
    rewrite_rag_query,
    sensitive_patch_paths,
    write_rag_decision_trace,
)


class AgenticRAGTests(unittest.TestCase):
    def test_policy_triggers_for_gate_sensitive_patch_reviewer_and_rag_off(self) -> None:
        policy = AgenticRAGPolicy()

        decision = policy.decide(
            reason="audit failed",
            query="pack.mcmeta audit failure",
            audit={"attempted": True, "success": False, "errors": [{"message": "pack_format is wrong"}]},
            changed_files=["src/main/resources/pack.mcmeta"],
            reviewer_observation={"requires_more_rag": True},
            rag_mode="off",
        )

        self.assertFalse(decision.rag_required)
        self.assertTrue(decision.skipped)
        self.assertTrue(decision.would_require_rag)
        self.assertIn("audit_failure", decision.triggers)
        self.assertIn("sensitive_patch", decision.triggers)
        self.assertIn("reviewer_evidence_insufficient", decision.triggers)
        self.assertIn("rag_disabled", decision.triggers)

    def test_query_rewrite_known_neoforge_failures(self) -> None:
        cases = [
            ("pack.mcmeta audit failure", "NeoForge resource pack metadata pack.mcmeta pack_format rules"),
            ("missing neoforge.mods.toml", "NeoForge mod metadata neoforge.mods.toml required fields"),
            ("DeferredRegister error", "NeoForge DeferredRegister registry object registration rules"),
            ("recipe json audit failure", "Minecraft NeoForge recipe JSON data pack schema"),
        ]
        for reason, expected in cases:
            with self.subTest(reason=reason):
                self.assertEqual(
                    rewrite_rag_query(query="", reason=reason, build={}, audit={}, changed_files=[]),
                    expected,
                )

    def test_multihop_retrieval_trace_and_patch_usage(self) -> None:
        policy = AgenticRAGPolicy()
        decision = policy.decide(
            reason="pack.mcmeta audit failure",
            query="broken pack format",
            audit={"attempted": True, "success": False, "errors": [{"message": "pack.mcmeta pack_format"}]},
            rag_mode="on",
        )
        trace = AgenticRAGRetriever().retrieve(decision=decision, limit=4, max_hops=2)

        self.assertGreaterEqual(len(trace.queries), 1)
        self.assertLessEqual(len(trace.queries), 2)
        self.assertEqual(len(trace.queries), len(set(trace.queries)))
        self.assertTrue(trace.citations)
        self.assertEqual(trace.sufficiency, "sufficient")

        with tempfile.TemporaryDirectory(prefix="agentic-rag-", dir=TMP_ROOT) as tmp:
            traces = [trace.to_dict()]
            mark_latest_trace_used_by_patch(traces, ["pack.mcmeta"])
            path = write_rag_decision_trace(Path(tmp), traces)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(saved[0]["used_by_patch"])
            self.assertEqual(saved[0]["patch_citation_ids"], ["pack.mcmeta"])

    def test_sensitive_patch_paths(self) -> None:
        self.assertEqual(
            sensitive_patch_paths(
                [
                    "src/main/resources/data/ruby_mod/recipe/ruby_sword.json",
                    "README.md",
                ]
            ),
            ["src/main/resources/data/ruby_mod/recipe/ruby_sword.json"],
        )


if __name__ == "__main__":
    unittest.main()
