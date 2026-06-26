from __future__ import annotations

import json
import tempfile
import tomllib
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

from neoforge_agent import AppConfig, WebDashboardRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class DashboardTests(unittest.TestCase):
    def test_dashboard_writes_static_html_and_data(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = WebDashboardRunner(config).run(
                run_name="unit-dashboard",
                planner_mode="llm",
                llm_provider="mock",
                eval_limit=1,
                run_showcase=True,
                run_quality_gate=False,
            )

            self.assertTrue(result.success)
            self.assertTrue(result.index_path.exists())
            self.assertTrue(result.dashboard_data_path.exists())
            self.assertTrue(result.dashboard_report_md_path.exists())

            html = result.index_path.read_text(encoding="utf-8")
            self.assertIn("NeoForge Mod Agent", html)
            self.assertIn("Capability Matrix", html)
            self.assertIn("RAG Knowledge", html)
            self.assertIn("Multi-Agent Trace", html)
            self.assertIn("RAG Hit Summary", html)
            self.assertIn("Self-Healing Repair", html)
            self.assertIn("Repair RAG Advice", html)
            self.assertIn("RAG query", html)
            self.assertIn("RAG Citation Chain", html)
            self.assertIn("knowledge ids", html)
            self.assertIn("Resource Preview", html)
            self.assertIn("resource-quality-report.json", html)

            data = json.loads(result.dashboard_data_path.read_text(encoding="utf-8"))
            project_metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
            self.assertEqual(data["version"], project_metadata["project"]["version"])
            self.assertGreater(data["metrics"]["capabilities"], 0)
            self.assertGreater(data["metrics"]["knowledge_hits"], 0)
            self.assertGreater(data["metrics"]["content_capabilities_total"], 0)
            self.assertGreater(data["metrics"]["content_capabilities_covered"], 0)
            self.assertGreater(data["metrics"]["agent_runs"], 0)
            self.assertGreater(data["metrics"]["agent_roles"], 0)
            self.assertGreater(data["metrics"]["agent_decisions"], 0)
            self.assertGreater(data["metrics"]["prompt_traces"], 0)
            self.assertGreater(data["metrics"]["rag_categories"], 0)
            self.assertGreater(data["metrics"]["rag_capabilities"], 0)
            self.assertGreater(data["metrics"]["repair_runs"], 0)
            self.assertIn("repair_executed", data["metrics"])
            self.assertIn("repair_attempts", data["metrics"])
            self.assertIn("repair_rag_runs", data["metrics"])
            self.assertIn("repair_rag_hits", data["metrics"])
            self.assertIn("rag_reference_chains", data["metrics"])
            self.assertIn("decision_knowledge_refs", data["metrics"])
            self.assertIn("resource_textures", data["metrics"])
            self.assertIn("resource_model_variants", data["metrics"])
            self.assertIn("resource_structure_previews", data["metrics"])
            self.assertGreater(data["metrics"]["rag_reference_chains"], 0)
            self.assertGreater(data["metrics"]["decision_knowledge_refs"], 0)
            self.assertGreater(data["metrics"]["resource_textures"], 0)
            self.assertIn("content_coverage", data)
            self.assertIn("agent_traces", data)
            self.assertIn("rag_summary", data)
            self.assertIn("rag_reference_chains", data)
            self.assertTrue(data["rag_reference_chains"])
            self.assertIn("repair_summary", data)
            self.assertIn("resource_preview", data)
            self.assertTrue(data["resource_preview"]["available"])
            self.assertGreater(data["rag_summary"]["hits_count"], 0)
            self.assertIn("tool", data["content_coverage"]["covered_capabilities"])
            self.assertIn("block_variants", data["content_coverage"]["covered_capabilities"])
            self.assertIsNotNone(data["showcase"])


if __name__ == "__main__":
    unittest.main()
