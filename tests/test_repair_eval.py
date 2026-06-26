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

from neoforge_agent import AppConfig, RepairEvalRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class RepairEvalTests(unittest.TestCase):
    def test_repair_eval_quantifies_self_healing_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = RepairEvalRunner(config).run(run_name="unit-repair-eval", limit=2)

            self.assertTrue(result.success)
            self.assertTrue(result.repair_eval_report_json_path.exists())
            self.assertTrue(result.repair_eval_report_md_path.exists())
            self.assertTrue(result.failure_lab_report_json_path)
            metrics = result.metrics
            self.assertEqual(metrics["total_cases"], 2)
            self.assertEqual(metrics["audit_detected_count"], 2)
            self.assertEqual(metrics["repair_rag_relevant_count"], 2)
            self.assertEqual(metrics["repair_loop_repaired_count"], 2)
            self.assertEqual(metrics["audit_recovered_count"], 2)
            self.assertEqual(metrics["full_success_count"], 2)
            self.assertGreater(metrics["repair_rag_hits_count"], 0)

    def test_repair_eval_recipe_case_requires_relevant_rag_hit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = RepairEvalRunner(config).run(
                run_name="unit-repair-eval-recipe",
                case_ids=["break_recipe_reference"],
            )

            self.assertTrue(result.success)
            case = result.cases[0]
            self.assertTrue(case.audit_detected)
            self.assertTrue(case.repair_rag_relevant)
            self.assertIn("recipes_loot_tags", case.repair_rag_capabilities)
            self.assertTrue(case.repair_loop_repaired)
            self.assertTrue(case.audit_recovered)


if __name__ == "__main__":
    unittest.main()
