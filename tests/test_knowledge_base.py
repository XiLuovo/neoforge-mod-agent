from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neoforge_agent import AppConfig, KnowledgeQueryRunner, MockLLMClient, NeoForgeKnowledgeBase, plan_with_llm


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class KnowledgeBaseTests(unittest.TestCase):
    def test_query_returns_worldgen_snippet_for_ore_generation(self) -> None:
        hits = NeoForgeKnowledgeBase().query("红宝石矿石自然生成在主世界地下", limit=3)

        self.assertTrue(hits)
        self.assertEqual(hits[0].entry.identifier, "worldgen.overworld_ore")

    def test_query_runner_writes_rag_reports(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = KnowledgeQueryRunner(config).query("right click heal ruby charm item cooldown", run_name="unit-rag")

            self.assertTrue(result.success)
            self.assertTrue(result.hits)
            self.assertIn("behavior", result.categories)
            self.assertIn("right_click_behavior", result.capabilities)
            self.assertIn("right_click_heal", result.query_expansions)
            self.assertTrue(result.report_json_path.exists())
            self.assertTrue(result.report_md_path.exists())

    def test_llm_planner_includes_rag_context_artifacts(self) -> None:
        client = MockLLMClient(PROJECT_ROOT)

        spec, artifacts = plan_with_llm(
            "Create a ruby mod with ruby ore worldgen in the overworld.",
            client,
            config=AppConfig.default(),
        )

        self.assertTrue(spec.ores)
        self.assertTrue(artifacts.rag_hits)
        self.assertTrue(artifacts.used_knowledge)
        self.assertIn("worldgen", artifacts.rag_categories)
        self.assertIn("overworld_ore", artifacts.rag_capabilities)
        self.assertIn("NeoForge RAG Context", artifacts.system_prompt)
        self.assertTrue(any(hit["id"] == "worldgen.overworld_ore" for hit in artifacts.rag_hits))


if __name__ == "__main__":
    unittest.main()
