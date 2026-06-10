from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neoforge_agent.cli import _collect_agent_run_metrics, build_parser


class CliParserTests(unittest.TestCase):
    def test_top_level_help_mentions_eval_and_agent(self) -> None:
        help_text = build_parser().format_help()

        self.assertIn("eval", help_text)
        self.assertIn("agent", help_text)
        self.assertIn("quality-gate", help_text)
        self.assertIn("doctor", help_text)
        self.assertIn("showcase", help_text)
        self.assertIn("portfolio-demo", help_text)
        self.assertIn("replay", help_text)
        self.assertIn("dashboard", help_text)
        self.assertIn("web-demo", help_text)
        self.assertIn("capabilities", help_text)
        self.assertIn("repair-loop", help_text)
        self.assertIn("eval-compare", help_text)
        self.assertIn("golden-test", help_text)
        self.assertIn("failure-lab", help_text)
        self.assertIn("repair-eval", help_text)
        self.assertIn("benchmark-report", help_text)
        self.assertIn("evidence-chain-report", help_text)
        self.assertIn("knowledge", help_text)
        self.assertIn("domains", help_text)
        self.assertIn("rag-eval", help_text)
        self.assertIn("tools-manifest", help_text)
        self.assertIn("llm-engineering-report", help_text)
        self.assertIn("harvest-report", help_text)

    def test_agent_bench_metrics_use_real_tool_loop_iterations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool_trace_path = root / "tool-call-trace.json"
            agent_run_path = root / "agent-run.json"
            tool_trace_path.write_text(
                json.dumps(
                    [
                        {"action": "retrieve_rag", "source": "llm"},
                        {"action": "read_file", "source": "llm"},
                        {"action": "finish", "source": "llm"},
                    ]
                ),
                encoding="utf-8",
            )
            agent_run_path.write_text(
                json.dumps(
                    {
                        "tool_call_trace_json_path": str(tool_trace_path),
                        "payload": {
                            "repair": {
                                "iterations": 3,
                                "repair_loop": {"attempts_count": 1},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            tool_call_counts: list[int] = []
            repair_attempt_counts: list[int] = []
            _collect_agent_run_metrics(agent_run_path, tool_call_counts, repair_attempt_counts)

            self.assertEqual(tool_call_counts, [3])
            self.assertEqual(repair_attempt_counts, [3])

    def test_eval_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "eval",
                "--planner",
                "llm",
                "--llm-provider",
                "mock",
                "--no-build",
                "--limit",
                "2",
                "--run-name",
                "unit",
                "--json",
            ]
        )

        self.assertEqual(args.command, "eval")
        self.assertEqual(args.planner, "llm")
        self.assertEqual(args.llm_provider, "mock")
        self.assertFalse(args.build)
        self.assertTrue(args.audit)
        self.assertEqual(args.limit, 2)
        self.assertEqual(args.run_name, "unit")
        self.assertTrue(args.json)

    def test_eval_compare_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "eval-compare",
                "baseline-run",
                "candidate-run",
                "--run-name",
                "unit-compare",
                "--tolerance",
                "0.01",
                "--json",
            ]
        )

        self.assertEqual(args.command, "eval-compare")
        self.assertEqual(args.baseline, "baseline-run")
        self.assertEqual(args.candidate, "candidate-run")
        self.assertEqual(args.run_name, "unit-compare")
        self.assertEqual(args.tolerance, 0.01)
        self.assertTrue(args.json)

    def test_generate_audit_flag_parses(self) -> None:
        args = build_parser().parse_args(
            [
                "generate",
                "Create a ruby mod with ruby.",
                "--audit",
                "--no-build",
                "--workspace-name",
                "unit-ruby",
            ]
        )

        self.assertEqual(args.command, "generate")
        self.assertTrue(args.audit)
        self.assertFalse(args.build)
        self.assertEqual(args.workspace_name, "unit-ruby")

    def test_replay_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "replay",
                "workspace/unit/.agent/agent-run.json",
                "--json",
            ]
        )

        self.assertEqual(args.command, "replay")
        self.assertEqual(args.target, "workspace/unit/.agent/agent-run.json")
        self.assertTrue(args.json)

    def test_quality_gate_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "quality-gate",
                "--run-name",
                "unit-gate",
                "--eval-limit",
                "1",
                "--doctor-java",
                "--doctor-strict",
                "--no-unittest",
                "--no-golden",
                "--build-smoke",
                "--json",
            ]
        )

        self.assertEqual(args.command, "quality-gate")
        self.assertEqual(args.run_name, "unit-gate")
        self.assertEqual(args.eval_limit, 1)
        self.assertTrue(args.doctor)
        self.assertTrue(args.doctor_java)
        self.assertTrue(args.doctor_strict)
        self.assertFalse(args.unittest)
        self.assertFalse(args.golden)
        self.assertTrue(args.failure_lab)
        self.assertTrue(args.repair_eval)
        self.assertTrue(args.build_smoke)
        self.assertTrue(args.json)

    def test_golden_test_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "golden-test",
                "--run-name",
                "unit-golden",
                "--limit",
                "2",
                "--json",
            ]
        )

        self.assertEqual(args.command, "golden-test")
        self.assertEqual(args.run_name, "unit-golden")
        self.assertEqual(args.limit, 2)
        self.assertTrue(args.json)

    def test_failure_lab_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "failure-lab",
                "--run-name",
                "unit-failure-lab",
                "--case",
                "delete_texture",
                "--limit",
                "1",
                "--build",
                "--json",
            ]
        )

        self.assertEqual(args.command, "failure-lab")
        self.assertEqual(args.run_name, "unit-failure-lab")
        self.assertEqual(args.cases, ["delete_texture"])
        self.assertEqual(args.limit, 1)
        self.assertTrue(args.build)
        self.assertTrue(args.json)

    def test_repair_eval_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "repair-eval",
                "--run-name",
                "unit-repair-eval",
                "--case",
                "delete_texture",
                "--limit",
                "1",
                "--build",
                "--json",
            ]
        )

        self.assertEqual(args.command, "repair-eval")
        self.assertEqual(args.run_name, "unit-repair-eval")
        self.assertEqual(args.cases, ["delete_texture"])
        self.assertEqual(args.limit, 1)
        self.assertTrue(args.build)
        self.assertTrue(args.json)

    def test_benchmark_report_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "benchmark-report",
                "--run-name",
                "unit-benchmark",
                "--eval-limit",
                "1",
                "--repair-limit",
                "1",
                "--baseline-provider",
                "mock",
                "--candidate-provider",
                "mock",
                "--run-real",
                "--no-build",
                "--audit",
                "--json",
            ]
        )

        self.assertEqual(args.command, "benchmark-report")
        self.assertEqual(args.run_name, "unit-benchmark")
        self.assertEqual(args.eval_limit, 1)
        self.assertEqual(args.repair_limit, 1)
        self.assertEqual(args.baseline_provider, "mock")
        self.assertEqual(args.candidate_provider, "mock")
        self.assertTrue(args.run_real)
        self.assertFalse(args.build)
        self.assertTrue(args.audit)
        self.assertTrue(args.json)

    def test_evidence_chain_report_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "evidence-chain-report",
                "--run-name",
                "unit-evidence-chain",
                "--eval-limit",
                "1",
                "--repair-limit",
                "1",
                "--json",
            ]
        )

        self.assertEqual(args.command, "evidence-chain-report")
        self.assertEqual(args.run_name, "unit-evidence-chain")
        self.assertEqual(args.eval_limit, 1)
        self.assertEqual(args.repair_limit, 1)
        self.assertTrue(args.json)

    def test_quality_gate_can_skip_doctor(self) -> None:
        args = build_parser().parse_args(
            [
                "quality-gate",
                "--no-doctor",
            ]
        )

        self.assertEqual(args.command, "quality-gate")
        self.assertFalse(args.doctor)

    def test_quality_gate_can_skip_failure_lab(self) -> None:
        args = build_parser().parse_args(
            [
                "quality-gate",
                "--no-failure-lab",
            ]
        )

        self.assertEqual(args.command, "quality-gate")
        self.assertFalse(args.failure_lab)

    def test_quality_gate_can_skip_repair_eval(self) -> None:
        args = build_parser().parse_args(
            [
                "quality-gate",
                "--no-repair-eval",
            ]
        )

        self.assertEqual(args.command, "quality-gate")
        self.assertFalse(args.repair_eval)

    def test_doctor_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "doctor",
                "--run-name",
                "unit-doctor",
                "--no-java",
                "--strict",
                "--json",
            ]
        )

        self.assertEqual(args.command, "doctor")
        self.assertEqual(args.run_name, "unit-doctor")
        self.assertFalse(args.java)
        self.assertTrue(args.strict)
        self.assertTrue(args.json)

    def test_showcase_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "showcase",
                "--run-name",
                "unit-showcase",
                "--planner",
                "llm",
                "--llm-provider",
                "mock",
                "--eval-limit",
                "1",
                "--quality-gate",
                "--build",
                "--json",
            ]
        )

        self.assertEqual(args.command, "showcase")
        self.assertEqual(args.run_name, "unit-showcase")
        self.assertEqual(args.planner, "llm")
        self.assertEqual(args.llm_provider, "mock")
        self.assertEqual(args.eval_limit, 1)
        self.assertTrue(args.quality_gate)
        self.assertTrue(args.build)
        self.assertTrue(args.json)

    def test_dashboard_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "dashboard",
                "--run-name",
                "unit-dashboard",
                "--planner",
                "llm",
                "--llm-provider",
                "mock",
                "--eval-limit",
                "1",
                "--no-showcase",
                "--json",
            ]
        )

        self.assertEqual(args.command, "dashboard")
        self.assertEqual(args.run_name, "unit-dashboard")
        self.assertEqual(args.planner, "llm")
        self.assertEqual(args.llm_provider, "mock")
        self.assertEqual(args.eval_limit, 1)
        self.assertFalse(args.showcase)
        self.assertTrue(args.json)

    def test_portfolio_demo_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "portfolio-demo",
                "--run-name",
                "unit-portfolio",
                "--planner",
                "llm",
                "--llm-provider",
                "mock",
                "--candidate-provider",
                "mock",
                "--eval-limit",
                "1",
                "--quality-gate",
                "--no-build",
                "--json",
            ]
        )

        self.assertEqual(args.command, "portfolio-demo")
        self.assertEqual(args.run_name, "unit-portfolio")
        self.assertEqual(args.planner, "llm")
        self.assertEqual(args.llm_provider, "mock")
        self.assertEqual(args.candidate_provider, "mock")
        self.assertEqual(args.eval_limit, 1)
        self.assertTrue(args.quality_gate)
        self.assertFalse(args.build)
        self.assertTrue(args.json)

    def test_web_demo_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "web-demo",
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
                "--planner",
                "mock-llm",
                "--smoke",
                "--json",
            ]
        )

        self.assertEqual(args.command, "web-demo")
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8765)
        self.assertEqual(args.planner, "mock-llm")
        self.assertTrue(args.smoke)
        self.assertTrue(args.json)

    def test_capabilities_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "capabilities",
                "--run-name",
                "unit-capabilities",
                "--json",
            ]
        )

        self.assertEqual(args.command, "capabilities")
        self.assertEqual(args.run_name, "unit-capabilities")
        self.assertTrue(args.json)

    def test_tools_manifest_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "tools-manifest",
                "--run-name",
                "unit-tools-manifest",
                "--json",
            ]
        )

        self.assertEqual(args.command, "tools-manifest")
        self.assertEqual(args.run_name, "unit-tools-manifest")
        self.assertTrue(args.json)

    def test_harvest_report_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "harvest-report",
                "--run-name",
                "unit-harvest",
                "--json",
            ]
        )

        self.assertEqual(args.command, "harvest-report")
        self.assertEqual(args.run_name, "unit-harvest")
        self.assertTrue(args.json)

    def test_agent_generate_code_lane_parses(self) -> None:
        args = build_parser().parse_args(
            [
                "agent",
                "generate",
                "Create a custom java feature.",
                "--planner",
                "llm",
                "--llm-provider",
                "mock",
                "--workspace-name",
                "unit-direct-code",
                "--code-lane",
                "direct",
                "--no-build",
                "--json",
            ]
        )

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "generate")
        self.assertEqual(args.code_lane, "direct")
        self.assertFalse(args.build)
        self.assertTrue(args.json)

    def test_agent_develop_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "agent",
                "develop",
                "Create a ruby tech mod.",
                "--planner",
                "llm",
                "--llm-provider",
                "mock",
                "--workspace-name",
                "unit-develop",
                "--build",
                "--max-iterations",
                "5",
                "--json",
            ]
        )

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "develop")
        self.assertEqual(args.request, "Create a ruby tech mod.")
        self.assertEqual(args.max_iterations, 5)
        self.assertTrue(args.build)
        self.assertTrue(args.audit)
        self.assertTrue(args.repair)
        self.assertTrue(args.json)

    def test_agent_modify_code_lane_parses(self) -> None:
        args = build_parser().parse_args(
            [
                "agent",
                "modify",
                "workspace/unit",
                "Add a ModSpec-only change.",
                "--code-lane",
                "modspec",
                "--no-build",
                "--json",
            ]
        )

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "modify")
        self.assertEqual(args.code_lane, "modspec")
        self.assertFalse(args.build)
        self.assertTrue(args.json)

    def test_agent_repair_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "agent",
                "repair",
                "workspace/unit",
                "--goal",
                "Fix audit failures.",
                "--llm-provider",
                "mock",
                "--max-iterations",
                "4",
                "--rag-mode",
                "on",
                "--no-build",
                "--json",
            ]
        )

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "repair")
        self.assertEqual(args.workspace, "workspace/unit")
        self.assertEqual(args.goal, "Fix audit failures.")
        self.assertEqual(args.max_iterations, 4)
        self.assertEqual(args.rag_mode, "on")
        self.assertFalse(args.build)
        self.assertTrue(args.audit)
        self.assertTrue(args.json)

    def test_agent_bench_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "agent",
                "bench",
                "--suite",
                "examples/agent_bench.json",
                "--llm-provider",
                "mock",
                "--eval-limit",
                "1",
                "--repair-limit",
                "1",
                "--build",
                "--audit",
                "--json",
            ]
        )

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "bench")
        self.assertEqual(args.suite, "examples/agent_bench.json")
        self.assertEqual(args.llm_provider, "mock")
        self.assertEqual(args.eval_limit, 1)
        self.assertEqual(args.repair_limit, 1)
        self.assertTrue(args.build)
        self.assertTrue(args.audit)
        self.assertTrue(args.json)

    def test_agent_bench_rag_ablation_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "agent",
                "bench",
                "--suite",
                "examples/agentic_rag_ablation.json",
                "--llm-provider",
                "openai-compatible",
                "--run-real",
                "--require-real",
                "--rag-mode",
                "auto",
                "--rag-ablation",
                "--audit",
                "--json",
            ]
        )

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "bench")
        self.assertEqual(args.suite, "examples/agentic_rag_ablation.json")
        self.assertEqual(args.llm_provider, "openai-compatible")
        self.assertTrue(args.run_real)
        self.assertTrue(args.require_real)
        self.assertEqual(args.rag_mode, "auto")
        self.assertTrue(args.rag_ablation)
        self.assertTrue(args.audit)
        self.assertTrue(args.json)

    def test_agent_lab_generate_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "agent",
                "lab-generate",
                "Add an advanced machine GUI beyond stable generate.",
                "--from-workspace",
                "learning-ruby",
                "--run-name",
                "unit-free-code-lab",
                "--llm-provider",
                "mock",
                "--build",
                "--json",
            ]
        )

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "lab-generate")
        self.assertEqual(args.request, "Add an advanced machine GUI beyond stable generate.")
        self.assertEqual(args.from_workspace, "learning-ruby")
        self.assertEqual(args.run_name, "unit-free-code-lab")
        self.assertEqual(args.llm_provider, "mock")
        self.assertTrue(args.build)
        self.assertTrue(args.json)

    def test_llm_engineering_report_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "llm-engineering-report",
                "workspace/unit",
                "--run-name",
                "unit-llm-engineering",
                "--json",
            ]
        )

        self.assertEqual(args.command, "llm-engineering-report")
        self.assertEqual(args.target, "workspace/unit")
        self.assertEqual(args.run_name, "unit-llm-engineering")
        self.assertTrue(args.json)

    def test_domains_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "domains",
                "--status",
                "planned",
                "--json",
            ]
        )

        self.assertEqual(args.command, "domains")
        self.assertEqual(args.status, "planned")
        self.assertTrue(args.json)

    def test_rag_eval_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "rag-eval",
                "--cases",
                "examples/rag_eval_cases.json",
                "--run-name",
                "unit-rag-eval",
                "--limit",
                "5",
                "--recall-k",
                "3",
                "--json",
            ]
        )

        self.assertEqual(args.command, "rag-eval")
        self.assertEqual(args.cases, "examples/rag_eval_cases.json")
        self.assertEqual(args.run_name, "unit-rag-eval")
        self.assertEqual(args.limit, 5)
        self.assertEqual(args.recall_k, 3)
        self.assertTrue(args.json)

    def test_llm_eval_report_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "llm-eval-report",
                "--run-name",
                "unit-llm-eval",
                "--candidate-provider",
                "mock",
                "--limit",
                "1",
                "--tolerance",
                "0.05",
                "--no-build",
                "--audit",
                "--json",
            ]
        )

        self.assertEqual(args.command, "llm-eval-report")
        self.assertEqual(args.run_name, "unit-llm-eval")
        self.assertEqual(args.candidate_provider, "mock")
        self.assertEqual(args.limit, 1)
        self.assertEqual(args.tolerance, 0.05)
        self.assertFalse(args.build)
        self.assertTrue(args.audit)
        self.assertTrue(args.json)

    def test_real_llm_stability_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "real-llm-stability",
                "--run-name",
                "unit-real-llm-stability",
                "--llm-provider",
                "openai-compatible",
                "--limit",
                "10",
                "--require-real",
                "--no-fallback-probe",
                "--no-build",
                "--audit",
                "--runtime-evidence",
                "docs/runtime.md",
                "--require-runtime",
                "--json",
            ]
        )

        self.assertEqual(args.command, "real-llm-stability")
        self.assertEqual(args.run_name, "unit-real-llm-stability")
        self.assertEqual(args.llm_provider, "openai-compatible")
        self.assertEqual(args.limit, 10)
        self.assertTrue(args.require_real)
        self.assertFalse(args.fallback_probe)
        self.assertFalse(args.build)
        self.assertTrue(args.audit)
        self.assertEqual(args.runtime_evidence, "docs/runtime.md")
        self.assertTrue(args.require_runtime)
        self.assertTrue(args.json)

    def test_repair_loop_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "repair-loop",
                "workspace/unit",
                "--max-attempts",
                "2",
                "--build",
                "--json",
            ]
        )

        self.assertEqual(args.command, "repair-loop")
        self.assertEqual(args.project, "workspace/unit")
        self.assertEqual(args.max_attempts, 2)
        self.assertTrue(args.audit)
        self.assertTrue(args.build)
        self.assertTrue(args.json)

    def test_knowledge_query_arguments_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "knowledge",
                "query",
                "红宝石矿石自然生成",
                "--limit",
                "3",
                "--run-name",
                "unit-rag",
                "--json",
            ]
        )

        self.assertEqual(args.command, "knowledge")
        self.assertEqual(args.knowledge_command, "query")
        self.assertEqual(args.query, "红宝石矿石自然生成")
        self.assertEqual(args.limit, 3)
        self.assertEqual(args.run_name, "unit-rag")
        self.assertTrue(args.json)


if __name__ == "__main__":
    unittest.main()
