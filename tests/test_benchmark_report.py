from __future__ import annotations

import json
import os
import shutil
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

from neoforge_agent import AgentBenchmarkCaseResult, AgentBenchmarkRunner, AppConfig, BenchmarkReportRunner
from neoforge_agent import AgentBenchmarkCaseSpec, ModProjectPlanner, WorkspaceAuditor, generate_agent_benchmark_holdout_cases
from neoforge_agent.benchmark_report import _agent_benchmark_breakage_registry, _inject_agent_benchmark_breakage, agent_benchmark_metrics


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class BenchmarkReportTests(unittest.TestCase):
    def test_agent_benchmark_metrics_classify_provider_and_repair_failures(self) -> None:
        provider_case = AgentBenchmarkCaseResult(
            identifier="provider-failed",
            mode="repair",
            request="repair provider",
            success=False,
            workspace=None,
            failure_kind="provider_error",
            provider_status_code=524,
            provider_error_summary="LLM provider returned HTTP 524.",
            errors=["LLM provider returned HTTP 524."],
            rag_mode="on",
        )
        repair_case = AgentBenchmarkCaseResult(
            identifier="repair-failed",
            mode="repair",
            request="repair logic",
            success=False,
            workspace=None,
            failure_kind="repair_logic_failure",
            errors=["Configured feature target must be a rule-test object, not a bare string."],
            rag_mode="on",
        )

        metrics = agent_benchmark_metrics([provider_case, repair_case])

        self.assertEqual(metrics["provider_error_count"], 1)
        self.assertEqual(metrics["provider_error_cases_count"], 1)
        self.assertEqual(metrics["repair_logic_failure_count"], 1)
        self.assertEqual(metrics["rag_on_repair_logic_failure_count"], 1)
        failed_by_id = {case["id"]: case for case in metrics["failed_cases"]}
        self.assertEqual(failed_by_id["provider-failed"]["failure_kind"], "provider_error")
        self.assertEqual(failed_by_id["provider-failed"]["provider_status_code"], 524)

    def test_agent_benchmark_repair_18_suite_schema_and_registry(self) -> None:
        suite_path = PROJECT_ROOT / "examples" / "agent_benchmark_repair_18.json"
        payload = json.loads(suite_path.read_text(encoding="utf-8"))
        cases = [AgentBenchmarkCaseSpec.from_dict(item) for item in payload["cases"]]
        registry = _agent_benchmark_breakage_registry()

        self.assertEqual(len(cases), 18)
        self.assertEqual(len({case.identifier for case in cases}), 18)
        for case in cases:
            with self.subTest(case=case.identifier):
                self.assertEqual(case.mode, "repair")
                self.assertTrue(case.breakage)
                self.assertTrue(case.category)
                self.assertTrue(case.expected_issue_prefixes)
                self.assertIn(case.breakage, registry)

    def test_focused_repair_benchmark_suite_schema_and_registry(self) -> None:
        suite_path = PROJECT_ROOT / "examples" / "focused_repair_benchmark.json"
        payload = json.loads(suite_path.read_text(encoding="utf-8"))
        cases = [AgentBenchmarkCaseSpec.from_dict(item) for item in payload["cases"]]
        registry = _agent_benchmark_breakage_registry()

        self.assertGreaterEqual(len(cases), 6)
        self.assertEqual(len({case.identifier for case in cases}), len(cases))
        self.assertIn("structured_patch", {case.expected_repair_strategy for case in cases})
        self.assertIn("regenerate_managed_files", {case.expected_repair_strategy for case in cases})
        self.assertIn("metadata", {case.category for case in cases})
        self.assertIn("asset_resource", {case.category for case in cases})
        self.assertIn("data_worldgen", {case.category for case in cases})
        self.assertIn("generated_code", {case.category for case in cases})
        for case in cases:
            with self.subTest(case=case.identifier):
                self.assertEqual(case.mode, "repair")
                self.assertTrue(case.breakage)
                self.assertTrue(case.category)
                self.assertTrue(case.expected_issue_prefixes)
                self.assertIn(case.breakage, registry)

    def test_agent_benchmark_repair_18_breakages_are_audit_detectable(self) -> None:
        suite_path = PROJECT_ROOT / "examples" / "agent_benchmark_repair_18.json"
        payload = json.loads(suite_path.read_text(encoding="utf-8"))
        cases = [AgentBenchmarkCaseSpec.from_dict(item) for item in payload["cases"]]

        with tempfile.TemporaryDirectory(prefix="agent-bench-breakages-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            config = test_config(root)
            planner = ModProjectPlanner(config)
            auditor = WorkspaceAuditor(config)
            clean_workspaces: dict[str, Path] = {}

            for index, prompt in enumerate(sorted({case.setup_request for case in cases}), start=1):
                generation = planner.execute(prompt, workspace_name=f"base-{index}", overwrite=True, run_build=False)
                self.assertTrue(generation.succeeded, generation.warnings)
                clean_workspaces[prompt] = generation.workspace_dir

            for case in cases:
                with self.subTest(case=case.identifier):
                    workspace = root / f"case-{case.identifier}"
                    shutil.copytree(clean_workspaces[case.setup_request], workspace)

                    injection = _inject_agent_benchmark_breakage(workspace, case.breakage)
                    audit = auditor.audit_workspace(workspace)
                    issue_ids = [issue.id for issue in audit.errors]

                    self.assertTrue(injection.injected_paths)
                    self.assertFalse(audit.success)
                    self.assertTrue(
                        any(
                            issue_id.startswith(prefix)
                            for issue_id in issue_ids
                            for prefix in case.expected_issue_prefixes
                        ),
                        f"{case.identifier} issues {issue_ids} did not match {case.expected_issue_prefixes}",
                    )

    def test_agent_benchmark_repair_holdout_generation_is_seeded(self) -> None:
        first = generate_agent_benchmark_holdout_cases(seed="unit-alpha", limit=8)
        second = generate_agent_benchmark_holdout_cases(seed="unit-alpha", limit=8)
        different = generate_agent_benchmark_holdout_cases(seed="unit-beta", limit=8)
        registry = _agent_benchmark_breakage_registry()

        self.assertEqual([case.to_dict() for case in first], [case.to_dict() for case in second])
        self.assertNotEqual([case.setup_request for case in first], [case.setup_request for case in different])
        self.assertEqual(len(first), 8)
        self.assertEqual(len({case.identifier for case in first}), 8)
        for case in first:
            with self.subTest(case=case.identifier):
                self.assertEqual(case.mode, "repair")
                self.assertIn(case.breakage, registry)
                self.assertTrue(case.category)
                self.assertTrue(case.expected_issue_prefixes)
                self.assertIn("Holdout material:", case.setup_request)
                self.assertNotIn("ruby mod with ruby", case.setup_request.lower())

    def test_agent_benchmark_repair_holdout_runs_mock_ablation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agent-bench-holdout-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = AgentBenchmarkRunner(config).run(
                run_name="unit-agent-benchmark-holdout",
                eval_limit=0,
                repair_limit=0,
                llm_provider="mock",
                run_build=False,
                run_audit=True,
                rag_ablation=True,
                repair_holdout=True,
                holdout_seed="unit-holdout",
                holdout_limit=3,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["cases_total"], 6)
            self.assertTrue(result.metrics["repair_holdout"])
            self.assertEqual(result.metrics["holdout_seed"], "unit-holdout")
            self.assertEqual(result.metrics["holdout_limit"], 3)
            self.assertEqual(result.metrics["expected_failure_detection_rate"], 1.0)
            self.assertEqual(result.metrics["rag_on_expected_detection_rate"], 1.0)
            for case in result.cases:
                self.assertTrue(case.identifier.startswith("holdout_unit_holdout_"))
                self.assertTrue(case.injected_paths)
                self.assertTrue(case.initial_audit_issue_ids)
                self.assertTrue(case.detected_expected_failure)

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
            self.assertIn("workspace-level evidence", result.metrics["evidence_scope"])
            self.assertTrue(result.metrics["trace_paths"])
            self.assertFalse(result.metrics["failed_cases"])
            self.assertTrue(result.benchmark_report_json_path.exists())
            self.assertTrue(result.benchmark_report_md_path.exists())
            self.assertTrue(result.benchmark_report_html_path.exists())
            agent_md = result.benchmark_report_md_path.read_text(encoding="utf-8")
            agent_html = result.benchmark_report_html_path.read_text(encoding="utf-8")
            self.assertIn("Evidence Boundary", agent_md)
            self.assertIn("not Minecraft client/server runtime acceptance", agent_md)
            self.assertIn("workspace benchmark", agent_html)

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

    def test_agent_benchmark_reports_rag_ablation_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = AgentBenchmarkRunner(config).run(
                run_name="unit-agentic-rag-ablation",
                cases_path=PROJECT_ROOT / "examples" / "agentic_rag_ablation.json",
                eval_limit=0,
                repair_limit=3,
                llm_provider="mock",
                run_build=False,
                run_audit=True,
                rag_ablation=True,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["cases_total"], 6)
            self.assertEqual(result.metrics["rag_on_success_rate"], 1.0)
            self.assertLess(result.metrics["rag_off_success_rate"], 1.0)
            self.assertGreater(result.metrics["rag_success_delta"], 0)
            self.assertGreater(result.metrics["rag_citation_coverage_rate"], 0)
            self.assertTrue(any(case.rag_mode == "on" for case in result.cases))
            self.assertTrue(any(case.rag_mode == "off" for case in result.cases))
            self.assertTrue(
                any(
                    case.rag_mode == "on" and case.rag_decision_trace_json_path
                    for case in result.cases
                )
            )
            self.assertTrue(
                any(
                    "rag-decision-trace.json" in trace_path
                    for case in result.cases
                    for trace_path in case.trace_paths
                )
            )
            self.assertTrue(result.benchmark_report_json_path.exists())

    def test_agent_benchmark_repair_18_subset_reports_detection_fields(self) -> None:
        source_path = PROJECT_ROOT / "examples" / "agent_benchmark_repair_18.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))["cases"]
        selected_ids = {
            "repair_delete_item_model",
            "repair_corrupt_recipe_json",
            "repair_break_recipe_reference",
            "repair_delete_ore_configured_feature",
        }
        selected_cases = [case for case in source if case["id"] in selected_ids]

        with tempfile.TemporaryDirectory(prefix="agent-bench-18-subset-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            suite_path = root / "subset.json"
            suite_path.write_text(json.dumps({"cases": selected_cases}, indent=2), encoding="utf-8")
            config = test_config(root / "workspace")

            result = AgentBenchmarkRunner(config).run(
                run_name="unit-agent-benchmark-18-subset",
                cases_path=suite_path,
                eval_limit=0,
                repair_limit=0,
                llm_provider="mock",
                run_build=False,
                run_audit=True,
                rag_ablation=True,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["cases_total"], 8)
            self.assertEqual(result.metrics["expected_failure_detection_rate"], 1.0)
            self.assertEqual(result.metrics["rag_on_expected_detection_rate"], 1.0)
            self.assertIn("asset_resource", result.metrics["cases_by_category"])
            self.assertIn("data_worldgen", result.metrics["cases_by_category"])
            for case in result.cases:
                self.assertTrue(case.injected_paths)
                self.assertTrue(case.initial_audit_issue_ids)
                self.assertTrue(case.detected_expected_failure)

    def test_agent_benchmark_real_provider_preflight(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            with patch.dict(os.environ, {}, clear=True):
                with patch("neoforge_agent.llm_client._project_dotenv_values", return_value={}):
                    skipped = AgentBenchmarkRunner(config).run(
                        run_name="unit-agent-benchmark-skip-real",
                        eval_limit=0,
                        repair_limit=0,
                        llm_provider="openai-compatible",
                        run_build=False,
                        run_audit=True,
                        rag_ablation=True,
                        require_real=False,
                    )
                    required = AgentBenchmarkRunner(config).run(
                        run_name="unit-agent-benchmark-require-real",
                        eval_limit=0,
                        repair_limit=0,
                        llm_provider="openai-compatible",
                        run_build=False,
                        run_audit=True,
                        rag_ablation=True,
                        require_real=True,
                    )

            self.assertTrue(skipped.success)
            self.assertEqual(skipped.cases, [])
            self.assertTrue(skipped.warnings)
            self.assertFalse(required.success)
            self.assertEqual(required.cases, [])
            self.assertTrue(required.errors)

    def test_benchmark_report_aggregates_mock_models_failure_types_and_runtime_page(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            config = test_config(root)
            runtime_evidence_path = root / "runtime-evidence.json"
            runtime_evidence_path.write_text(
                json.dumps(
                    {
                        "schema_version": "manual-runtime-evidence/v1",
                        "evidence_kind": "manual_minecraft_runtime",
                        "runtime_evidence_cases": [
                            {
                                "id": "unit_runtime_basic",
                                "workspace": "unit-runtime-basic",
                                "status": "passed",
                                "notes": "Unit runtime fixture.",
                            },
                            {
                                "id": "unit_runtime_behavior",
                                "workspace": "unit-runtime-behavior",
                                "status": "passed",
                                "notes": "Unit runtime fixture.",
                            },
                            {
                                "id": "unit_runtime_worldgen",
                                "workspace": "unit-runtime-worldgen",
                                "status": "passed",
                                "notes": "Unit runtime fixture.",
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = BenchmarkReportRunner(config).run(
                run_name="unit-benchmark",
                eval_limit=1,
                repair_limit=1,
                baseline_provider="mock",
                candidate_provider="mock",
                run_build=False,
                run_audit=True,
                runtime_evidence_path=runtime_evidence_path,
            )

            self.assertTrue(result.success)
            self.assertEqual(len(result.model_runs), 2)
            self.assertTrue(all(run.status == "pass" for run in result.model_runs))
            self.assertEqual(result.metrics["model_runs_completed"], 2)
            self.assertEqual(result.metrics["mock_runs"], 2)
            self.assertEqual(result.metrics["failure_types_total"], 1)
            self.assertEqual(result.metrics["repair_rate"], 1.0)
            self.assertIn("workspace-level evidence", result.metrics["evidence_scope"])
            self.assertGreaterEqual(result.metrics["runtime_cases_total"], 3)
            self.assertEqual(result.metrics["runtime_pass_rate"], 1.0)
            self.assertEqual(result.metrics["manual_runtime_evidence_schema"], "manual-runtime-evidence/v1")
            self.assertEqual(result.metrics["manual_runtime_evidence_kind"], "manual_minecraft_runtime")
            self.assertTrue(result.runtime_cases)
            self.assertEqual(result.runtime_cases[0].schema_version, "manual-runtime-evidence/v1")
            self.assertEqual(result.runtime_cases[0].evidence_kind, "manual_minecraft_runtime")
            self.assertTrue(result.benchmark_report_json_path.exists())
            self.assertTrue(result.benchmark_report_md_path.exists())
            self.assertTrue(result.benchmark_report_html_path.exists())

            html = result.benchmark_report_html_path.read_text(encoding="utf-8")
            self.assertIn("Benchmark Report", html)
            self.assertIn("Model A/B", html)
            self.assertIn("Failure Types", html)
            self.assertIn("Evidence Boundary", html)
            self.assertIn("Manual Runtime Evidence", html)

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

