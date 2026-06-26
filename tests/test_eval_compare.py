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

from neoforge_agent import AppConfig, EvalComparisonRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


def write_eval_report(path: Path, *, success_rate: float, case_success: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "success": case_success,
        "run_id": path.parent.parent.name,
        "metrics": {
            "success_rate": success_rate,
            "feature_expectation_success_rate": success_rate,
            "expected_feature_match_rate": success_rate,
            "category_expectation_success_rate": success_rate,
            "expected_category_match_rate": success_rate,
            "planning_success_rate": success_rate,
            "audit_success_rate": success_rate,
            "build_success_rate": 0.0,
            "agent_artifacts_complete_rate": success_rate,
            "agent_trace_present_rate": success_rate,
            "agent_decisions_present_rate": success_rate,
            "prompt_trace_present_rate": success_rate,
            "repeat_modify_success_rate": success_rate,
        },
        "cases": [
            {
                "id": "basic_ruby",
                "success": case_success,
                "errors": [] if case_success else ["case failed"],
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


class EvalCompareTests(unittest.TestCase):
    def test_eval_compare_passes_when_candidate_matches_baseline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            baseline = write_eval_report(Path(tmp) / "baseline" / ".agent" / "eval-report.json", success_rate=1.0)
            candidate = write_eval_report(Path(tmp) / "candidate" / ".agent" / "eval-report.json", success_rate=1.0)

            result = EvalComparisonRunner(config).compare(
                baseline,
                candidate,
                run_name="unit-compare-pass",
            )

            self.assertTrue(result.success)
            self.assertEqual(result.regressions, [])
            self.assertTrue(result.eval_compare_report_json_path.exists())
            self.assertTrue(result.eval_compare_report_md_path.exists())

    def test_eval_compare_reports_metric_and_case_regression(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            baseline = write_eval_report(Path(tmp) / "baseline" / ".agent" / "eval-report.json", success_rate=1.0)
            candidate = write_eval_report(
                Path(tmp) / "candidate" / ".agent" / "eval-report.json",
                success_rate=0.5,
                case_success=False,
            )

            result = EvalComparisonRunner(config).compare(
                baseline,
                candidate,
                run_name="unit-compare-regression",
            )

            self.assertFalse(result.success)
            self.assertGreaterEqual(len(result.regressions), 2)
            self.assertTrue(any("metric:success_rate" in item for item in result.regressions))
            self.assertTrue(any("case:basic_ruby" in item for item in result.regressions))

    def test_eval_compare_resolves_eval_run_names(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            write_eval_report(Path(tmp) / "eval-runs" / "baseline-run" / ".agent" / "eval-report.json", success_rate=1.0)
            write_eval_report(Path(tmp) / "eval-runs" / "candidate-run" / ".agent" / "eval-report.json", success_rate=1.0)

            result = EvalComparisonRunner(config).compare(
                "baseline-run",
                "candidate-run",
                run_name="unit-compare-run-names",
            )

            self.assertTrue(result.success)
            self.assertIn("baseline-run", str(result.baseline_report_path))
            self.assertIn("candidate-run", str(result.candidate_report_path))


if __name__ == "__main__":
    unittest.main()
