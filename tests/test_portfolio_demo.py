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

from neoforge_agent import AppConfig, PortfolioDemoRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class PortfolioDemoTests(unittest.TestCase):
    def test_portfolio_demo_writes_report_and_runs_core_steps(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = PortfolioDemoRunner(config).run(
                run_name="unit-portfolio",
                planner_mode="llm",
                llm_provider="mock",
                candidate_provider="mock",
                eval_limit=1,
                run_build=False,
                run_quality_gate=False,
            )

            self.assertTrue(result.success)
            self.assertTrue(result.portfolio_report_json_path.exists())
            self.assertTrue(result.portfolio_report_md_path.exists())

            statuses = {step.name: step.status for step in result.steps}
            self.assertEqual(statuses["doctor"], "pass")
            self.assertEqual(statuses["showcase"], "pass")
            self.assertEqual(statuses["dashboard"], "pass")
            self.assertEqual(statuses["llm_eval_report"], "pass")
            self.assertEqual(statuses["evidence_chain_report"], "pass")
            self.assertEqual(statuses["web_demo_smoke"], "pass")
            self.assertEqual(statuses["capabilities"], "pass")

            dashboard = next(step for step in result.steps if step.name == "dashboard")
            self.assertTrue(Path(dashboard.artifacts["dashboard_index"]).exists())

            report = result.portfolio_report_md_path.read_text(encoding="utf-8")
            self.assertIn("V4.0 作品集级一键演示报告", report)
            self.assertIn("讲解重点", report)
            self.assertIn("evidence_chain_report", report)


if __name__ == "__main__":
    unittest.main()
