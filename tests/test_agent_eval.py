from __future__ import annotations

import os
import json
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

from neoforge_agent import AgentOrchestrator, AppConfig, BenchmarkEvaluator, BuildResult, EvalCase


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root, project_root=workspace_root)


class AgentEvalTests(unittest.TestCase):
    def test_development_e2e_cases_file_is_well_formed(self) -> None:
        cases_path = PROJECT_ROOT / "examples" / "agent_development_e2e.json"
        payload = json.loads(cases_path.read_text(encoding="utf-8"))
        cases = payload["cases"]
        identifiers = [case["id"] for case in cases]

        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertIn("generate", {case["mode"] for case in cases})
        self.assertIn("modify", {case["mode"] for case in cases})
        self.assertTrue(all(case["expected_features"] for case in cases))
        self.assertTrue(all(case["expected_categories"] for case in cases))

    def test_development_e2e_suite_reports_expected_coverage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = replace(test_config(Path(tmp)), project_root=PROJECT_ROOT)

            result = BenchmarkEvaluator(config).run(
                cases_path=PROJECT_ROOT / "examples" / "agent_development_e2e.json",
                planner_mode="llm",
                llm_provider="mock",
                run_build=False,
                run_audit=True,
                run_name="unit-development-e2e",
            )

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["total_cases"], 2)
            self.assertEqual(result.metrics["expected_feature_match_rate"], 1.0)
            self.assertEqual(result.metrics["expected_category_match_rate"], 1.0)
            self.assertEqual(result.metrics["audit_success_rate"], 1.0)
            self.assertEqual(result.metrics["build_attempted_count"], 0)
            self.assertEqual(result.metrics["repeat_modify_cases"], 1)
            self.assertEqual(result.metrics["repeat_modify_success_rate"], 1.0)

            progression = next(case for case in result.cases if case.identifier == "develop_progression_loop")
            self.assertIn("ruby_pickaxe", progression.matched_expected_features)
            self.assertIn("progression_report", progression.matched_expected_categories)

            repeat = next(case for case in result.cases if case.identifier == "modify_add_worldgen_repeat")
            self.assertTrue(repeat.repeat_modify_success)
            self.assertIn("ruby_ore", repeat.repeat_modify_skipped)

    def test_agent_repair_executes_safe_loop_after_audit_failure(self) -> None:
        class BreakBeforeAuditOrchestrator(AgentOrchestrator):
            def __init__(self, config: AppConfig) -> None:
                super().__init__(config)
                self.broken_once = False

            def _run_audit_step(self, workspace: Path, run_audit: bool, steps: list, decisions: list) -> dict:
                model_path = (
                    workspace
                    / "src"
                    / "main"
                    / "resources"
                    / "assets"
                    / "ruby_mod"
                    / "models"
                    / "item"
                    / "ruby.json"
                )
                if run_audit and not self.broken_once and model_path.exists():
                    model_path.unlink()
                    self.broken_once = True
                return super()._run_audit_step(workspace, run_audit, steps, decisions)

        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = BreakBeforeAuditOrchestrator(config)

            result = orchestrator.run_generate(
                "Create a ruby mod with ruby.",
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="agent-repair-audit",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
            )

            self.assertTrue(result.success)
            self.assertIsNotNone(result.workspace)
            repair_payload = result.payload["repair"]
            self.assertTrue(repair_payload["repair_needed"])
            self.assertTrue(repair_payload["repair_executed"])
            self.assertTrue(repair_payload["repair_success"])
            self.assertTrue(repair_payload["repair_rag"]["attempted"])
            self.assertGreater(repair_payload["repair_rag"]["hits_count"], 0)
            repair_decisions = [decision for decision in result.decisions if decision.role == "repair_agent"]
            self.assertTrue(repair_decisions)
            self.assertTrue(repair_decisions[-1].knowledge_refs)
            self.assertTrue(repair_decisions[-1].to_dict()["knowledge_ids"])
            self.assertTrue((result.workspace / ".agent" / "repair-loop-report.json").exists())
            self.assertTrue((result.workspace / ".agent" / "agent-repair-plan.json").exists())
            self.assertTrue((result.workspace / ".agent" / "repair-rag-context.json").exists())
            self.assertTrue((result.workspace / ".agent" / "repair-rag-context.md").exists())
            self.assertTrue(
                (
                    result.workspace
                    / "src"
                    / "main"
                    / "resources"
                    / "assets"
                    / "ruby_mod"
                    / "models"
                    / "item"
                    / "ruby.json"
                ).exists()
            )

    def test_agent_generate_with_mock_llm_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)

            result = orchestrator.run_generate(
                "Create a ruby mod with a ruby charm item.",
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="agent-ruby-charm",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
            )

            self.assertTrue(result.success)
            self.assertIsNotNone(result.workspace)
            self.assertEqual(result.payload["runtime"]["domain"], "neoforge")
            self.assertEqual(result.payload["runtime"]["stages"], ["planner", "reviewer", "executor", "auditor", "repair"])
            self.assertTrue((result.workspace / ".agent" / "agent-run.json").exists())
            self.assertTrue((result.workspace / ".agent" / "agent-decisions.md").exists())
            self.assertTrue((result.workspace / ".agent" / "prompt-trace.json").exists())
            self.assertTrue((result.workspace / ".agent" / "agent-trace-summary.json").exists())
            self.assertTrue((result.workspace / ".agent" / "agent-trace-summary.md").exists())
            self.assertTrue((result.workspace / ".agent" / "tool-call-trace.json").exists())
            self.assertTrue((result.workspace / ".agent" / "reviewer-report.json").exists())
            self.assertTrue((result.workspace / ".agent" / "reviewer-report.md").exists())
            self.assertGreaterEqual(len(result.decisions), 4)
            self.assertEqual(len(result.prompt_traces), 1)
            self.assertIn("normalized_json", result.prompt_traces[0].to_dict())
            roles = [step.role for step in result.steps]
            self.assertIn("planner_agent", roles)
            self.assertIn("reviewer_agent", roles)
            self.assertIn("executor_agent", roles)
            self.assertIn("auditor_agent", roles)
            review_steps = [step for step in result.steps if step.role == "reviewer_agent"]
            self.assertTrue(review_steps)
            self.assertIn("review_checks", review_steps[0].details)
            self.assertTrue(result.prompt_traces[0].used_knowledge)
            self.assertIn("behavior", result.prompt_traces[0].rag_categories)
            planner_decisions = [decision for decision in result.decisions if decision.role == "planner_agent"]
            self.assertTrue(planner_decisions)
            self.assertTrue(planner_decisions[0].knowledge_refs)
            self.assertTrue(planner_decisions[0].to_dict()["knowledge_ids"])
            decisions_md = (result.workspace / ".agent" / "agent-decisions.md").read_text(encoding="utf-8")
            self.assertIn("knowledge ids", decisions_md)

    def test_agent_develop_records_coding_agent_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)

            result = orchestrator.run_develop(
                "Create a ruby tech mod with ruby ore and recipes.",
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="agent-develop-ruby-tech",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
                max_iterations=5,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.mode, "develop")
            self.assertIsNotNone(result.workspace)
            agent_run = json.loads((result.workspace / ".agent" / "agent-run.json").read_text(encoding="utf-8"))
            self.assertEqual(agent_run["mode"], "develop")
            self.assertEqual(agent_run["payload"]["runtime"]["stages"], ["planner", "reviewer", "executor", "auditor", "repair"])
            self.assertEqual(agent_run["payload"]["repair"]["loop_purpose"], "develop_refine")
            self.assertTrue(agent_run["payload"]["repair"]["tool_call_trace"])
            self.assertEqual(agent_run["payload"]["repair"]["iterations"], 5)
            self.assertEqual(agent_run["payload"]["repair"]["success"], True)
            self.assertEqual(agent_run["payload"]["repair"]["final_audit"]["success"], True)
            self.assertGreaterEqual(len(agent_run["prompt_traces"]), 6)
            self.assertIn("planner_agent", {trace["role"] for trace in agent_run["prompt_traces"]})
            self.assertIn("repair_agent", {trace["role"] for trace in agent_run["prompt_traces"]})
            self.assertIn("reviewer_agent", {trace["role"] for trace in agent_run["prompt_traces"]})
            tool_trace = json.loads((result.workspace / ".agent" / "tool-call-trace.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [entry["action"] for entry in tool_trace],
                ["retrieve_rag", "read_file", "apply_structured_patch", "run_audit", "finish"],
            )
            self.assertTrue(all(entry.get("source") == "llm" for entry in tool_trace))
            self.assertNotIn("agent_step", {entry.get("source") for entry in tool_trace})
            self.assertIn("(develop refined)", (result.workspace / "src" / "main" / "resources" / "pack.mcmeta").read_text(encoding="utf-8"))
            self.assertTrue((result.workspace / ".agent" / "structured-patch-report.json").exists())
            self.assertTrue((result.workspace / ".agent" / "structured-patch-rollback-report.json").exists())
            snapshots = list((result.workspace / ".agent" / "structured-patch-snapshots").rglob("pack.mcmeta"))
            self.assertTrue(snapshots)
            reviewer = json.loads((result.workspace / ".agent" / "reviewer-report.json").read_text(encoding="utf-8"))
            self.assertEqual(reviewer["source"], "llm_reviewer")
            self.assertEqual(reviewer["decision"], "approve")
            self.assertEqual(reviewer["coverage_status"], "pass")
            self.assertEqual(reviewer["status"], "pass")
            self.assertTrue(reviewer["checks"])
            self.assertEqual(agent_run["payload"]["repair"]["reviewer"]["source"], "llm_reviewer")
            self.assertEqual(agent_run["payload"]["evidence"]["reviewer_source"], "llm_reviewer")
            self.assertEqual(agent_run["payload"]["evidence"]["reviewer_decision"], "approve")
            self.assertEqual(agent_run["payload"]["evidence"]["reviewer_coverage_status"], "pass")
            self.assertTrue(agent_run["payload"]["evidence"]["reviewer_report_json_path"].endswith("reviewer-report.json"))
            reviewer_traces = [trace for trace in agent_run["prompt_traces"] if trace["role"] == "reviewer_agent"]
            self.assertTrue(any(trace["prompt_kind"].startswith("reviewer_") for trace in reviewer_traces))

    def test_agent_develop_reviewer_needs_repair_feeds_followup_loop(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)

            result = orchestrator.run_develop(
                "Create a ruby tech mod with ruby ore and recipes; reviewer needs repair.",
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="agent-develop-reviewer-repair",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
                max_iterations=6,
            )

            self.assertTrue(result.success)
            self.assertIsNotNone(result.workspace)
            agent_run = json.loads((result.workspace / ".agent" / "agent-run.json").read_text(encoding="utf-8"))
            repair_payload = agent_run["payload"]["repair"]
            self.assertIn("reviewer_requested_repair", repair_payload)
            self.assertEqual(repair_payload["reviewer"]["source"], "llm_reviewer")
            self.assertEqual(repair_payload["reviewer"]["decision"], "needs_repair")
            self.assertEqual(repair_payload["reviewer"]["coverage_status"], "partial")
            self.assertEqual(repair_payload["tool_calls_count"], len(repair_payload["tool_call_trace"]))
            self.assertGreater(repair_payload["tool_calls_count"], 5)
            self.assertEqual(
                [entry["action"] for entry in repair_payload["tool_call_trace"][:5]],
                ["retrieve_rag", "read_file", "apply_structured_patch", "run_audit", "finish"],
            )
            self.assertTrue(
                any(
                    trace["role"] == "repair_agent"
                    and "reviewer_observation" in trace["input_text"]
                    and "Reviewer requested one additional constrained refinement pass" in trace["input_text"]
                    for trace in agent_run["prompt_traces"]
                )
            )
            reviewer_traces = [trace for trace in agent_run["prompt_traces"] if trace["role"] == "reviewer_agent"]
            self.assertTrue(any(trace["normalized_json"]["decision"] == "needs_repair" for trace in reviewer_traces))

    def test_agent_repair_existing_workspace_uses_safe_loop(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)
            setup = orchestrator.run_generate(
                "Create a ruby mod with ruby.",
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="agent-repair-existing",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
            )
            self.assertTrue(setup.success)
            self.assertIsNotNone(setup.workspace)

            model_path = (
                setup.workspace
                / "src"
                / "main"
                / "resources"
                / "assets"
                / "ruby_mod"
                / "models"
                / "item"
                / "ruby.json"
            )
            model_path.unlink()

            result = orchestrator.run_repair(
                setup.workspace,
                goal="Fix audit failures without changing user-owned files.",
                planner_mode="llm",
                llm_provider="mock",
                max_iterations=2,
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.mode, "repair")
            self.assertTrue(model_path.exists())
            self.assertTrue((setup.workspace / ".agent" / "agent-run.json").exists())
            self.assertTrue((setup.workspace / ".agent" / "repair-loop-report.json").exists())
            self.assertTrue((setup.workspace / ".agent" / "tool-call-trace.json").exists())

    def test_agent_generate_modspec_lane_does_not_write_direct_code_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)

            result = orchestrator.run_generate(
                "Create a ruby mod with ruby.",
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="agent-modspec-lane",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
                code_lane="modspec",
            )

            self.assertTrue(result.success)
            self.assertIsNotNone(result.workspace)
            self.assertFalse((result.workspace / ".agent" / "direct-code-plan.json").exists())
            roles = [step.role for step in result.steps]
            self.assertNotIn("direct_code_agent", roles)
            self.assertNotIn("direct_code_reviewer", roles)

    def test_agent_generate_hybrid_direct_code_lane_records_artifacts_and_roles(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)
            mock_build = BuildResult(attempted=True, success=True, summary="mock direct-code build")

            with patch.object(orchestrator.planner.builder, "build", return_value=mock_build):
                result = orchestrator.run_generate(
                    "Create a custom java direct code feature.",
                    planner_mode="llm",
                    llm_provider="mock",
                    workspace_name="agent-direct-code",
                    overwrite=True,
                    run_build=False,
                    run_audit=True,
                    repair=False,
                    code_lane="hybrid",
                )

            self.assertTrue(result.success)
            self.assertIsNotNone(result.workspace)
            roles = [step.role for step in result.steps]
            self.assertIn("direct_code_reviewer", roles)
            self.assertIn("direct_code_agent", roles)
            for name in (
                "direct-code-plan.json",
                "direct-code-plan.md",
                "direct-code-review.json",
                "direct-code-diff.md",
                "direct-code-report.json",
                "direct-code-rollback-report.json",
            ):
                self.assertTrue((result.workspace / ".agent" / name).exists(), name)
            self.assertTrue(
                (
                    result.workspace
                    / "src"
                    / "main"
                    / "java"
                    / "com"
                    / "generated"
                    / "direct_code_mod"
                    / "directcode"
                    / "DirectCodeMockFeature.java"
                ).exists()
            )
            direct_code = result.payload["generation"]["direct_code"]
            self.assertTrue(direct_code["success"])
            self.assertTrue(direct_code["build"]["attempted"])
            planner_step = [step for step in result.steps if step.role == "planner_agent"][0]
            self.assertTrue(planner_step.details["intent_contract"]["requires_direct_code"])

    def test_agent_generate_direct_code_build_failure_recommends_rollback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)
            mock_build = BuildResult(attempted=True, success=False, summary="mock compile error")

            with patch.object(orchestrator.planner.builder, "build", return_value=mock_build):
                result = orchestrator.run_generate(
                    "Create a custom java direct code feature.",
                    planner_mode="llm",
                    llm_provider="mock",
                    workspace_name="agent-direct-code-fail",
                    overwrite=True,
                    run_build=False,
                    run_audit=True,
                    repair=False,
                    code_lane="direct",
                )

            self.assertFalse(result.success)
            self.assertIsNotNone(result.workspace)
            rollback = json.loads((result.workspace / ".agent" / "direct-code-rollback-report.json").read_text(encoding="utf-8"))
            self.assertEqual(rollback["status"], "recommended")
            self.assertEqual(rollback["trigger"], "build_fail")
            report = json.loads((result.workspace / ".agent" / "direct-code-report.json").read_text(encoding="utf-8"))
            self.assertFalse(report["success"])

    def test_agent_modify_direct_code_lane_preserves_patch_and_direct_code_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)
            setup = orchestrator.run_generate(
                "Create a ruby mod with ruby.",
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="agent-modify-direct-base",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
                code_lane="modspec",
            )
            self.assertTrue(setup.success)
            self.assertIsNotNone(setup.workspace)

            mock_build = BuildResult(attempted=True, success=True, summary="mock direct-code modify build")
            with patch.object(orchestrator.planner.builder, "build", return_value=mock_build):
                result = orchestrator.run_modify(
                    setup.workspace,
                    "Add a custom java direct code source patch.",
                    planner_mode="llm",
                    llm_provider="mock",
                    run_build=False,
                    run_audit=True,
                    repair=False,
                    code_lane="direct",
                )

            self.assertTrue(result.success)
            roles = [step.role for step in result.steps]
            self.assertIn("direct_code_reviewer", roles)
            self.assertIn("direct_code_agent", roles)
            self.assertTrue((setup.workspace / ".agent" / "modspec.before.json").exists())
            self.assertTrue((setup.workspace / ".agent" / "modspec.after.json").exists())
            self.assertTrue((setup.workspace / ".agent" / "patch-agent-report.json").exists())
            self.assertTrue((setup.workspace / ".agent" / "direct-code-plan.json").exists())
            self.assertTrue(
                (
                    setup.workspace
                    / "src"
                    / "main"
                    / "java"
                    / "com"
                    / "generated"
                    / "ruby_mod"
                    / "directcode"
                    / "DirectCodeModifyMockFeature.java"
                ).exists()
            )

    def test_agent_real_llm_health_failure_falls_back_to_rules(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)

            with patch.dict(os.environ, {"NEOFORGE_AGENT_ROOT": tmp}, clear=True):
                result = orchestrator.run_generate(
                    "做一个红宝石模组，添加红宝石。",
                    planner_mode="llm",
                    llm_provider="openai-compatible",
                    workspace_name="agent-real-llm-fallback",
                    overwrite=True,
                    run_build=False,
                    run_audit=True,
                    repair=True,
                )

            self.assertTrue(result.success)
            self.assertEqual(result.planner_mode, "llm->rules")
            planner_step = [step for step in result.steps if step.role == "planner_agent"][0]
            self.assertTrue(any("fallback" in warning.lower() or "fell back" in warning.lower() for warning in planner_step.warnings))

    def test_agent_require_llm_fails_instead_of_falling_back_to_rules(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)

            with patch.dict(os.environ, {"NEOFORGE_AGENT_ROOT": tmp}, clear=True):
                result = orchestrator.run_generate(
                    "做一个红宝石模组，添加红宝石。",
                    planner_mode="llm",
                    llm_provider="openai-compatible",
                    workspace_name="agent-real-llm-required",
                    overwrite=True,
                    run_build=False,
                    run_audit=True,
                    repair=True,
                    require_llm=True,
                )

            self.assertFalse(result.success)
            self.assertEqual(result.planner_mode, "llm")
            planner_step = [step for step in result.steps if step.role == "planner_agent"][0]
            self.assertEqual(planner_step.status, "fail")
            self.assertTrue(any("LLM planner is required" in error for error in planner_step.errors))

    def test_eval_default_subset_reports_feature_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = BenchmarkEvaluator(config).run(
                planner_mode="llm",
                llm_provider="mock",
                run_build=False,
                run_audit=True,
                run_name="unit-eval",
                limit=2,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["total_cases"], 2)
            self.assertEqual(result.metrics["expected_feature_match_rate"], 1.0)
            self.assertEqual(result.metrics["expected_category_match_rate"], 1.0)
            self.assertEqual(result.metrics["agent_artifacts_complete_count"], 2)
            self.assertTrue(all(case.agent_trace_present for case in result.cases))
            self.assertTrue(all(case.agent_decisions_present for case in result.cases))
            self.assertTrue(all(case.prompt_trace_present for case in result.cases))
            self.assertTrue(all(case.agent_trace_summary_present for case in result.cases))
            self.assertEqual(result.metrics["rag_hit_rate"], 1.0)
            self.assertGreater(result.metrics["rag_hits_total"], 0)
            self.assertIn("rag_capabilities_covered", result.metrics)
            self.assertTrue(result.eval_report_json_path.exists())
            self.assertTrue(result.eval_report_md_path.exists())

    def test_agent_modify_mock_llm_uses_change_request_trace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)

            setup = orchestrator.run_generate(
                "Create a ruby mod with a ruby charm item.",
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="agent-modify-base",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
            )
            self.assertTrue(setup.success)
            self.assertIsNotNone(setup.workspace)

            result = orchestrator.run_modify(
                setup.workspace,
                "Add ruby ore that generates underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk.",
                planner_mode="llm",
                llm_provider="mock",
                run_build=False,
                run_audit=True,
                repair=True,
            )

            self.assertTrue(result.success)
            modify_payload = result.payload["modify"]
            self.assertIn("ruby", modify_payload["added"])
            self.assertIn("ruby_ore", modify_payload["added"])
            self.assertIn("patch_agent", modify_payload)
            self.assertTrue((setup.workspace / ".agent" / "patch-agent-plan.json").exists())
            self.assertTrue((setup.workspace / ".agent" / "patch-agent-plan.md").exists())
            self.assertTrue((setup.workspace / ".agent" / "patch-agent-report.json").exists())
            self.assertTrue((setup.workspace / ".agent" / "patch-agent-rollback-report.json").exists())
            self.assertIn("plan_json_path", modify_payload["patch_agent"])
            self.assertIn("report_json_path", modify_payload["patch_agent"])
            self.assertTrue((setup.workspace / ".agent" / "agent-decisions.md").exists())
            self.assertTrue((setup.workspace / ".agent" / "prompt-trace.json").exists())
            normalized = result.prompt_traces[0].normalized_json or {}
            feature_ids = [feature["id"] for feature in normalized.get("features", [])]
            self.assertIn("ruby_ore", feature_ids)

    def test_eval_fails_when_expected_feature_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            case = EvalCase(
                identifier="missing_feature",
                mode="generate",
                request="Create a ruby mod with ruby.",
                expected_features=["not_generated"],
            )

            result = BenchmarkEvaluator(config).run(
                cases=[case],
                planner_mode="llm",
                llm_provider="mock",
                run_build=False,
                run_audit=True,
                run_name="unit-negative-eval",
            )

            self.assertFalse(result.success)
            self.assertEqual(result.metrics["expected_features_matched"], 0)
            self.assertEqual(result.cases[0].missing_expected_features, ["not_generated"])

    def test_eval_repeat_modify_reports_idempotency(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            case = EvalCase(
                identifier="repeat_modify_charm",
                mode="modify",
                setup_request="Create a ruby mod with ruby.",
                request="Add a ruby charm item that heals 4 health on right click with 20 seconds cooldown.",
                expected_features=["ruby_charm"],
                expected_categories=["item", "behavior", "right_click_heal", "modify"],
                repeat_request=True,
            )

            result = BenchmarkEvaluator(config).run(
                cases=[case],
                planner_mode="llm",
                llm_provider="mock",
                run_build=False,
                run_audit=True,
                run_name="unit-repeat-eval",
            )

            self.assertTrue(result.success)
            self.assertTrue(result.cases[0].repeat_modify_success)
            self.assertIn("ruby_charm", result.cases[0].repeat_modify_skipped)
            self.assertEqual(result.metrics["repeat_modify_cases"], 1)
            self.assertEqual(result.metrics["repeat_modify_success_rate"], 1.0)
            self.assertEqual(result.metrics["expected_category_match_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
