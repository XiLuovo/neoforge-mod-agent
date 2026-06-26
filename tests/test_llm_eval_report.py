from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neoforge_agent import AppConfig, RealLLMEvalReportRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root, project_root=workspace_root)


class LLMEvalReportTests(unittest.TestCase):
    def test_llm_eval_report_runs_offline_mock_comparison(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = RealLLMEvalReportRunner(config).run(
                run_name="unit-llm-eval-mock",
                candidate_provider="mock",
                limit=1,
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.baseline_status, "pass")
            self.assertEqual(result.candidate_status, "pass")
            self.assertEqual(result.comparison_status, "pass")
            self.assertTrue(result.llm_eval_report_json_path.exists())
            self.assertTrue(result.llm_eval_report_md_path.exists())
            self.assertIsNotNone(result.baseline_eval_report_path)
            self.assertIsNotNone(result.candidate_eval_report_path)
            self.assertIsNotNone(result.eval_compare_report_path)
            self.assertEqual(result.provider_config["provider"], "mock")
            self.assertEqual(result.metrics_summary["success_rate_delta"], 0.0)

    def test_llm_eval_report_skips_missing_real_provider_without_network(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            with patch.dict(os.environ, {"NEOFORGE_AGENT_ROOT": tmp}, clear=True):
                result = RealLLMEvalReportRunner(config).run(
                    run_name="unit-llm-eval-skip-real",
                    candidate_provider="openai-compatible",
                    limit=1,
                    run_build=False,
                    run_audit=True,
                )

            self.assertTrue(result.success)
            self.assertEqual(result.baseline_status, "pass")
            self.assertEqual(result.candidate_status, "skip")
            self.assertEqual(result.comparison_status, "skip")
            self.assertFalse(result.provider_config["valid"])
            self.assertGreater(len(result.warnings), 0)
            self.assertEqual(result.errors, [])
            self.assertIsNone(result.candidate_eval_report_path)

    def test_llm_eval_report_require_real_fails_when_provider_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            with patch.dict(os.environ, {"NEOFORGE_AGENT_ROOT": tmp}, clear=True):
                result = RealLLMEvalReportRunner(config).run(
                    run_name="unit-llm-eval-require-real",
                    candidate_provider="openai-compatible",
                    require_real=True,
                    limit=1,
                    run_build=False,
                    run_audit=True,
                )

            self.assertFalse(result.success)
            self.assertEqual(result.candidate_status, "skip")
            self.assertGreater(len(result.errors), 0)
            self.assertTrue(result.llm_eval_report_json_path.exists())


if __name__ == "__main__":
    unittest.main()
