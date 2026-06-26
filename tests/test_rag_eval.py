from __future__ import annotations

import json
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

from neoforge_agent import AppConfig, RAGEvalRunner, default_rag_eval_cases


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class RAGEvalTests(unittest.TestCase):
    def test_default_rag_eval_writes_reports_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = RAGEvalRunner(config).run(run_name="unit-rag-eval", limit=5, recall_k=3)

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["total_cases"], len(default_rag_eval_cases()))
            self.assertEqual(result.metrics["expanded_recall_at_k"], 1.0)
            self.assertEqual(result.metrics["expanded_expected_category_hit_rate"], 1.0)
            self.assertTrue(result.rag_eval_report_json_path.exists())
            self.assertTrue(result.rag_eval_report_md_path.exists())

            payload = json.loads(result.rag_eval_report_json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["cases_count"], len(default_rag_eval_cases()))
            self.assertIn("expanded_mrr", payload["metrics"])

    def test_rag_eval_accepts_custom_cases_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            cases_path = root / "cases.json"
            cases_path.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "unit_worldgen",
                                "query": "overworld ore configured feature placed feature",
                                "expected_knowledge_ids": ["worldgen.overworld_ore"],
                                "expected_categories": ["worldgen"],
                                "expected_capabilities": ["overworld_ore"],
                            }
                        ]
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            config = test_config(root / "workspace")

            result = RAGEvalRunner(config).run(cases_path=cases_path, run_name="custom-rag-eval")

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["total_cases"], 1)
            self.assertEqual(result.cases[0].identifier, "unit_worldgen")
            self.assertTrue(result.cases[0].expanded_recall_at_k)


if __name__ == "__main__":
    unittest.main()
