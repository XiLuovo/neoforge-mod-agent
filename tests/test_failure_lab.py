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

from neoforge_agent import AppConfig, FailureLabRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class FailureLabTests(unittest.TestCase):
    def test_failure_lab_detects_explains_and_repairs_generated_artifact_failures(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = FailureLabRunner(config).run(run_name="unit-failure-lab", limit=2)

            self.assertTrue(result.success)
            self.assertEqual(len(result.cases), 2)
            self.assertTrue(result.failure_lab_report_json_path.exists())
            self.assertTrue(result.failure_lab_report_md_path.exists())
            for case in result.cases:
                self.assertTrue(case.generation_success)
                self.assertTrue(case.fault_injected)
                self.assertFalse(case.initial_audit_success)
                self.assertTrue(case.detected_expected_failure)
                self.assertTrue(case.repair_rag_attempted)
                self.assertGreater(case.repair_rag_hits_count, 0)
                self.assertTrue(case.repair_success)
                self.assertTrue(case.final_audit_success)

    def test_failure_lab_recipe_reference_case_uses_actual_recipe_json_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = FailureLabRunner(config).run(
                run_name="unit-failure-lab-recipe",
                case_ids=["break_recipe_reference"],
            )

            self.assertTrue(result.success)
            case = result.cases[0]
            self.assertIn("break_recipe_reference", case.identifier)
            self.assertTrue(any(issue_id.startswith("recipe:") and ":json_" in issue_id for issue_id in case.detected_issue_ids))
            self.assertTrue(case.repair_success)


if __name__ == "__main__":
    unittest.main()
