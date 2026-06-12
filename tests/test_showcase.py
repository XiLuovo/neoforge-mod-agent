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

from neoforge_agent import AppConfig, ShowcaseRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class ShowcaseTests(unittest.TestCase):
    def test_showcase_writes_report_and_runs_core_steps(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = ShowcaseRunner(config).run(
                run_name="unit-showcase",
                planner_mode="llm",
                llm_provider="mock",
                run_build=False,
                run_quality_gate=False,
                eval_limit=1,
            )

            self.assertTrue(result.success)
            self.assertTrue(result.showcase_report_json_path.exists())
            self.assertTrue(result.showcase_report_md_path.exists())

            statuses = {step.name: step.status for step in result.steps}
            self.assertEqual(statuses["doctor"], "pass")
            self.assertEqual(statuses["agent_generate"], "pass")
            self.assertEqual(statuses["agent_modify"], "pass")
            self.assertEqual(statuses["eval_smoke"], "pass")
            self.assertEqual(statuses["development_e2e"], "pass")
            self.assertEqual(statuses["quality_gate"], "skip")

            payload = json.loads(result.showcase_report_json_path.read_text(encoding="utf-8"))
            development_step = next(step for step in payload["steps"] if step["name"] == "development_e2e")
            self.assertTrue(Path(development_step["artifacts"]["eval_report_json"]).exists())
            self.assertEqual(development_step["metrics"]["expected_feature_match_rate"], 1.0)
            self.assertEqual(development_step["metrics"]["expected_category_match_rate"], 1.0)
            self.assertTrue(development_step["metrics"]["audit_success"])
            self.assertFalse(development_step["metrics"]["build_attempted"])
            self.assertIsNone(development_step["metrics"]["build_success"])
            self.assertTrue(development_step["metrics"]["repeat_modify_success"])


if __name__ == "__main__":
    unittest.main()
