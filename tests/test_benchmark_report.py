from __future__ import annotations

import json
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

from neoforge_agent import AgentBenchmarkRunner, AppConfig, BenchmarkReportRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class BenchmarkReportTests(unittest.TestCase):
    def test_agent_benchmark_runs_real_tool_loop_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = AgentBenchmarkRunner(config).run(
                run_name="unit-agent-benchmark",
                eval_limit=1,
                repair_limit=1,
                llm_provider="mock",
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["cases_total"], 2)
            self.assertEqual(result.metrics["success_rate"], 1.0)
            self.assertEqual(result.metrics["audit_success_rate"], 1.0)
            self.assertGreaterEqual(result.metrics["avg_tool_calls"], 5)
            self.assertGreaterEqual(result.metrics["avg_iterations"], 5)
            self.assertGreater(result.metrics["rag_hit_rate"], 0)
            self.assertGreater(result.metrics["patch_accept_rate"], 0)
            self.assertGreaterEqual(result.metrics["rollback_count"], 1)
            self.assertTrue(result.metrics["trace_paths"])
            self.assertFalse(result.metrics["failed_cases"])
            self.assertTrue(result.benchmark_report_json_path.exists())
            self.assertTrue(result.benchmark_report_md_path.exists())
            self.assertTrue(result.benchmark_report_html_path.exists())

            repair_case = next(case for case in result.cases if case.identifier == "repair_mods_toml_structured_patch")
            self.assertFalse(repair_case.managed_regen_success)
            self.assertTrue(repair_case.success)
            self.assertGreaterEqual(repair_case.patch_accepted_count, 1)
            self.assertTrue(repair_case.rollback_evidence_paths)
            self.assertTrue(repair_case.agent_run_json_path)
            self.assertTrue(repair_case.tool_call_trace_json_path)
            self.assertTrue(repair_case.reviewer_report_json_path)

            tool_trace = json.loads(Path(repair_case.tool_call_trace_json_path).read_text(encoding="utf-8"))
            self.assertIn("regenerate_managed_files", [entry["action"] for entry in tool_trace])
            self.assertIn("apply_structured_patch", [entry["action"] for entry in tool_trace])
            self.assertTrue(all(entry.get("source") == "llm" for entry in tool_trace))
            reviewer = json.loads(Path(repair_case.reviewer_report_json_path).read_text(encoding="utf-8"))
            self.assertEqual(reviewer["source"], "llm_reviewer")

    def test_benchmark_report_aggregates_mock_models_failure_types_and_runtime_page(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = BenchmarkReportRunner(config).run(
                run_name="unit-benchmark",
                eval_limit=1,
                repair_limit=1,
                baseline_provider="mock",
                candidate_provider="mock",
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(result.success)
            self.assertEqual(len(result.model_runs), 2)
            self.assertTrue(all(run.status == "pass" for run in result.model_runs))
            self.assertEqual(result.metrics["model_runs_completed"], 2)
            self.assertEqual(result.metrics["mock_runs"], 2)
            self.assertEqual(result.metrics["failure_types_total"], 1)
            self.assertEqual(result.metrics["repair_rate"], 1.0)
            self.assertGreaterEqual(result.metrics["runtime_cases_total"], 3)
            self.assertEqual(result.metrics["runtime_pass_rate"], 1.0)
            self.assertTrue(result.benchmark_report_json_path.exists())
            self.assertTrue(result.benchmark_report_md_path.exists())
            self.assertTrue(result.benchmark_report_html_path.exists())

            html = result.benchmark_report_html_path.read_text(encoding="utf-8")
            self.assertIn("Benchmark Report", html)
            self.assertIn("Model A/B", html)
            self.assertIn("Failure Types", html)
            self.assertIn("Runtime Evidence", html)

    def test_benchmark_report_skips_unconfigured_real_provider_without_network(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            with patch.dict(os.environ, {}, clear=True):
                result = BenchmarkReportRunner(config).run(
                    run_name="unit-benchmark-skip-real",
                    eval_limit=1,
                    repair_limit=1,
                    baseline_provider="mock",
                    candidate_provider="openai-compatible",
                    run_build=False,
                    run_audit=True,
                )

            self.assertTrue(result.success)
            self.assertEqual(result.model_runs[0].status, "pass")
            self.assertEqual(result.model_runs[1].status, "skip")
            self.assertEqual(result.metrics["model_runs_skipped"], 1)
            self.assertEqual(result.metrics["real_runs"], 1)
            self.assertGreater(len(result.warnings), 0)


if __name__ == "__main__":
    unittest.main()
