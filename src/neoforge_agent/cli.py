from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .agent_orchestrator import AgentOrchestrator
from .auditor import WorkspaceAuditor
from .benchmark_report import AgentBenchmarkRunner, BenchmarkReportRunner
from .builder import GradleBuilder
from .capabilities import CapabilityCatalog
from .config import AppConfig
from .dashboard import WebDashboardRunner
from .doctor import EnvironmentDoctor
from .domain_spec import DomainSpecRegistry
from .evidence_chain_report import EvidenceChainReportRunner
from .eval_compare import EvalComparisonRunner
from .evaluator import BenchmarkEvaluator
from .failure_lab import FailureLabRunner
from .free_code_lab import FreeCodeLabRunner, HarvestReportRunner
from .golden_tests import GoldenTestRunner
from .knowledge_base import KnowledgeQueryRunner
from .llm_client import check_llm_provider_health, create_llm_client
from .llm_engineering_report import LLMEngineeringReportRunner
from .llm_eval_report import RealLLMEvalReportRunner
from .llm_planner import LLMPlanningError, PlannerArtifacts, plan_with_llm, write_planner_artifacts
from .modifier import WorkspaceModifier
from .models import ModSpec, RequestOverrides
from .planner import ModProjectPlanner
from .portfolio_demo import PortfolioDemoRunner
from .quality_gate import QualityGateRunner
from .rag_eval import RAGEvalRunner
from .real_llm_stability import RealLLMStabilityRunner
from .repair import RepairArtifactGenerator
from .repair_eval import RepairEvalRunner
from .repair_loop import AutoRepairRunner
from .replay import AgentRunReplayer
from .schema import get_modspec_schema
from .showcase import ShowcaseRunner
from .tools import slugify_mod_id, write_generation_summary
from .tool_manifest import ToolManifestRunner
from .web_demo import WebDemoRunner, WebDemoServer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neoforge-agent",
        description="Generate, modify, audit, build, and repair NeoForge 26.1 mod workspaces.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    command_help = {
        "plan": "Parse a natural language request into a ModSpec plan without generating files.",
        "validate": "Parse and validate a natural language request without generating files.",
        "generate": "Generate a new workspace from a natural language request.",
    }
    for command_name in ("plan", "validate", "generate"):
        subparser = subparsers.add_parser(command_name, help=command_help[command_name])
        subparser.add_argument("request", help="Natural language mod request.")
        _add_common_generation_arguments(subparser)

    generate_spec_parser = subparsers.add_parser(
        "generate-from-spec",
        help="Generate a workspace from an existing ModSpec JSON file.",
    )
    generate_spec_parser.add_argument("spec_path", help="Path to a JSON spec file.")
    _add_generation_execution_arguments(generate_spec_parser)
    generate_spec_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    modify_parser = subparsers.add_parser(
        "modify",
        help="Modify an existing generated workspace by merging a new natural language request.",
    )
    modify_parser.add_argument("workspace", help="Path or workspace name of an existing generated mod project.")
    modify_parser.add_argument("change_request", help="Natural language change request to merge into the existing ModSpec.")
    modify_parser.add_argument("--planner", choices=["rules", "llm", "auto"], default="rules", help="Planner mode to use for the change request patch.")
    modify_parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="openai-compatible", help="LLM provider used when modify planner=llm or auto falls back to LLM.")
    _add_generation_execution_arguments(modify_parser)
    modify_parser.add_argument("--repair", action="store_true", help="Generate repair artifacts if the build fails.")
    modify_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    build_cmd_parser = subparsers.add_parser(
        "build",
        help="Run the Gradle build for an existing generated workspace.",
    )
    build_cmd_parser.add_argument("project", help="Path or workspace name of a generated mod project.")
    build_cmd_parser.add_argument("--repair", action="store_true", help="Generate repair artifacts if the build fails.")
    build_cmd_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    repair_parser = subparsers.add_parser(
        "repair",
        help="Create repair artifacts from the latest failed build logs.",
    )
    repair_parser.add_argument("project", help="Path or workspace name of a generated mod project.")
    repair_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    repair_loop_parser = subparsers.add_parser(
        "repair-loop",
        help="Run a safe automatic repair loop for an existing generated workspace.",
    )
    repair_loop_parser.add_argument("project", help="Path or workspace name of a generated mod project.")
    repair_loop_parser.add_argument("--max-attempts", type=int, default=1, help="Maximum managed-file regeneration attempts.")
    repair_loop_audit_group = repair_loop_parser.add_mutually_exclusive_group()
    repair_loop_audit_group.add_argument("--audit", dest="audit", action="store_true", help="Run workspace audit in each repair-loop check.")
    repair_loop_audit_group.add_argument("--no-audit", dest="audit", action="store_false", help="Skip workspace audit in repair-loop checks.")
    repair_loop_parser.set_defaults(audit=True)
    repair_loop_build_group = repair_loop_parser.add_mutually_exclusive_group()
    repair_loop_build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build in each repair-loop check.")
    repair_loop_build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build in repair-loop checks.")
    repair_loop_parser.set_defaults(build=False)
    repair_loop_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    audit_parser = subparsers.add_parser(
        "audit",
        help="Audit a generated workspace against .agent/modspec.json and generation-summary.json.",
    )
    audit_parser.add_argument("project", help="Path or workspace name of a generated mod project.")
    audit_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    replay_parser = subparsers.add_parser(
        "replay",
        help="Replay a saved .agent/agent-run.json as a deterministic historical timeline report.",
    )
    replay_parser.add_argument("target", help="Workspace path/name, .agent directory, or agent-run.json path to replay.")
    replay_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    eval_parser = subparsers.add_parser(
        "eval",
        help="Run benchmark prompts through the agent workflow and write evaluation reports.",
    )
    eval_parser.add_argument("--cases", help="Optional JSON file containing eval cases.")
    eval_parser.add_argument("--planner", choices=["rules", "llm", "auto"], default="llm", help="Planner mode used by benchmark cases.")
    eval_parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="mock", help="LLM provider used when planner mode needs an LLM.")
    eval_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/eval-runs/.")
    eval_parser.add_argument("--limit", type=int, help="Only run the first N eval cases.")
    eval_build_group = eval_parser.add_mutually_exclusive_group()
    eval_build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build for each eval case.")
    eval_build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build for eval cases.")
    eval_parser.set_defaults(build=False)
    eval_audit_group = eval_parser.add_mutually_exclusive_group()
    eval_audit_group.add_argument("--audit", dest="audit", action="store_true", help="Run workspace audit for each eval case.")
    eval_audit_group.add_argument("--no-audit", dest="audit", action="store_false", help="Skip workspace audit for eval cases.")
    eval_parser.set_defaults(audit=True)
    eval_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    eval_compare_parser = subparsers.add_parser(
        "eval-compare",
        help="Compare two eval reports and fail when benchmark metrics or cases regress.",
    )
    eval_compare_parser.add_argument("baseline", help="Baseline eval report path, eval run directory, or eval run name.")
    eval_compare_parser.add_argument("candidate", help="Candidate eval report path, eval run directory, or eval run name.")
    eval_compare_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/eval-comparisons/.")
    eval_compare_parser.add_argument("--tolerance", type=float, default=0.0, help="Allowed rate delta before reporting a regression.")
    eval_compare_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    llm_eval_report_parser = subparsers.add_parser(
        "llm-eval-report",
        help="Run a mock baseline eval, optional real LLM candidate eval, and a comparison report.",
    )
    llm_eval_report_parser.add_argument("--cases", help="Optional JSON file containing eval cases.")
    llm_eval_report_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/llm-eval-runs/.")
    llm_eval_report_parser.add_argument("--limit", type=int, help="Only run the first N eval cases.")
    llm_eval_report_parser.add_argument("--baseline-provider", choices=["mock", "openai-compatible"], default="mock", help="Provider for the baseline eval run.")
    llm_eval_report_parser.add_argument("--candidate-provider", choices=["mock", "openai-compatible"], default="openai-compatible", help="Provider for the candidate eval run.")
    llm_eval_report_parser.add_argument("--tolerance", type=float, default=0.0, help="Allowed rate delta before reporting a comparison regression.")
    llm_eval_report_parser.add_argument("--require-real", action="store_true", help="Fail if the real candidate provider is not configured.")
    llm_eval_build_group = llm_eval_report_parser.add_mutually_exclusive_group()
    llm_eval_build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build for each eval case.")
    llm_eval_build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build for eval cases.")
    llm_eval_report_parser.set_defaults(build=False)
    llm_eval_audit_group = llm_eval_report_parser.add_mutually_exclusive_group()
    llm_eval_audit_group.add_argument("--audit", dest="audit", action="store_true", help="Run workspace audit for each eval case.")
    llm_eval_audit_group.add_argument("--no-audit", dest="audit", action="store_false", help="Skip workspace audit for eval cases.")
    llm_eval_report_parser.set_defaults(audit=True)
    llm_eval_report_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    llm_engineering_report_parser = subparsers.add_parser(
        "llm-engineering-report",
        help="Aggregate prompt/provider engineering evidence from .agent prompt traces and LLM stability artifacts.",
    )
    llm_engineering_report_parser.add_argument(
        "target",
        help="Workspace path/name, .agent directory, prompt-trace.json, agent-run.json, or llm-stability.json path.",
    )
    llm_engineering_report_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/llm-engineering-runs/.")
    llm_engineering_report_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    real_llm_stability_parser = subparsers.add_parser(
        "real-llm-stability",
        help="Run strict real-provider cases and classify provider/schema/audit/build/runtime/fallback outcomes.",
    )
    real_llm_stability_parser.add_argument("--cases", help="Optional JSON file containing eval cases; only generate cases are used.")
    real_llm_stability_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/real-llm-stability-runs/.")
    real_llm_stability_parser.add_argument("--limit", type=int, default=10, help="Only run the first N generate cases.")
    real_llm_stability_parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="openai-compatible", help="Provider to test in strict mode.")
    real_llm_stability_parser.add_argument("--require-real", action="store_true", help="Fail the report unless every case succeeds through the real provider without fallback.")
    real_llm_stability_parser.add_argument("--fallback-probe", dest="fallback_probe", action="store_true", help="After strict real-provider failure, run a non-strict fallback probe and count it separately.")
    real_llm_stability_parser.add_argument("--no-fallback-probe", dest="fallback_probe", action="store_false", help="Do not run fallback probes after strict real-provider failures.")
    real_llm_stability_parser.set_defaults(fallback_probe=True)
    real_llm_stability_build_group = real_llm_stability_parser.add_mutually_exclusive_group()
    real_llm_stability_build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build for each strict/fallback case.")
    real_llm_stability_build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build for faster stability sampling.")
    real_llm_stability_parser.set_defaults(build=False)
    real_llm_stability_audit_group = real_llm_stability_parser.add_mutually_exclusive_group()
    real_llm_stability_audit_group.add_argument("--audit", dest="audit", action="store_true", help="Run workspace audit for each strict/fallback case.")
    real_llm_stability_audit_group.add_argument("--no-audit", dest="audit", action="store_false", help="Skip workspace audit for stability sampling.")
    real_llm_stability_parser.set_defaults(audit=True)
    real_llm_stability_parser.add_argument("--runtime-evidence", help="Optional JSON or Markdown file with documented Minecraft runtime validation evidence.")
    real_llm_stability_parser.add_argument("--require-runtime", action="store_true", help="Fail unless every strict case has passing runtime evidence.")
    real_llm_stability_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    benchmark_report_parser = subparsers.add_parser(
        "benchmark-report",
        help="Run/aggregate model A/B, mock/real, failure repair, build, and runtime benchmark evidence into one page.",
    )
    benchmark_report_parser.add_argument("--cases", help="Optional JSON file containing eval cases.")
    benchmark_report_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/benchmark-runs/.")
    benchmark_report_parser.add_argument("--eval-limit", type=int, default=3, help="Number of eval cases per model run.")
    benchmark_report_parser.add_argument("--repair-limit", type=int, default=3, help="Number of injected failure repair cases.")
    benchmark_report_parser.add_argument("--baseline-provider", choices=["mock", "openai-compatible"], default="mock", help="Provider for model A.")
    benchmark_report_parser.add_argument("--candidate-provider", choices=["mock", "openai-compatible"], default="openai-compatible", help="Provider for model B.")
    benchmark_report_parser.add_argument("--runtime-evidence", help="Markdown file with documented runtime validation evidence.")
    benchmark_report_parser.add_argument("--run-real", action="store_true", help="Actually run model B when it uses a real provider. Without this, real providers are preflighted and skipped.")
    benchmark_report_parser.add_argument("--require-real", action="store_true", help="Fail if model B is a real provider and is not configured.")
    benchmark_report_build_group = benchmark_report_parser.add_mutually_exclusive_group()
    benchmark_report_build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build for benchmark eval/repair cases.")
    benchmark_report_build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build for the fast benchmark page.")
    benchmark_report_parser.set_defaults(build=False)
    benchmark_report_audit_group = benchmark_report_parser.add_mutually_exclusive_group()
    benchmark_report_audit_group.add_argument("--audit", dest="audit", action="store_true", help="Run workspace audit for benchmark eval cases.")
    benchmark_report_audit_group.add_argument("--no-audit", dest="audit", action="store_false", help="Skip workspace audit for benchmark eval cases.")
    benchmark_report_parser.set_defaults(audit=True)
    benchmark_report_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    evidence_chain_parser = subparsers.add_parser(
        "evidence-chain-report",
        help="Aggregate Stable ModSpec, Behavior DSL, and controlled patch-agent evidence into one proof chain.",
    )
    evidence_chain_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/evidence-chain-runs/.")
    evidence_chain_parser.add_argument("--eval-limit", type=int, default=2, help="Number of stable-layer eval cases per model run.")
    evidence_chain_parser.add_argument("--repair-limit", type=int, default=2, help="Number of stable-layer injected failure repair cases.")
    evidence_chain_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    golden_parser = subparsers.add_parser(
        "golden-test",
        help="Run deterministic golden snapshot checks for generated feature coverage.",
    )
    golden_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/golden-runs/.")
    golden_parser.add_argument("--limit", type=int, help="Only run the first N golden cases.")
    golden_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    failure_lab_parser = subparsers.add_parser(
        "failure-lab",
        help="Inject common generated-workspace failures, then verify audit, repair-loop, and repair RAG diagnostics.",
    )
    failure_lab_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/failure-lab-runs/.")
    failure_lab_parser.add_argument("--case", action="append", dest="cases", help="Run only a named failure case. Repeat to run multiple cases.")
    failure_lab_parser.add_argument("--limit", type=int, help="Only run the first N failure cases.")
    failure_lab_parser.add_argument("--build", action="store_true", help="Also run Gradle build checks inside each repair-loop attempt.")
    failure_lab_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    repair_eval_parser = subparsers.add_parser(
        "repair-eval",
        help="Quantify self-healing across injected failure samples and write repair eval reports.",
    )
    repair_eval_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/repair-eval-runs/.")
    repair_eval_parser.add_argument("--case", action="append", dest="cases", help="Evaluate only a named failure case. Repeat to run multiple cases.")
    repair_eval_parser.add_argument("--limit", type=int, help="Only evaluate the first N failure cases.")
    repair_eval_parser.add_argument("--build", action="store_true", help="Also run Gradle build checks inside repair-loop attempts.")
    repair_eval_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    quality_gate_parser = subparsers.add_parser(
        "quality-gate",
        help="Run the reliability gate: compile, tests, schema, examples, eval smoke, golden tests, and failure lab.",
    )
    quality_gate_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/quality-gate-runs/.")
    quality_gate_parser.add_argument("--eval-limit", type=int, default=10, help="Number of default eval cases to run in eval smoke.")
    quality_gate_parser.add_argument("--timeout-seconds", type=int, default=900, help="Timeout per quality-gate check.")
    quality_gate_parser.add_argument("--no-doctor", dest="doctor", action="store_false", help="Skip environment doctor preflight.")
    quality_gate_parser.set_defaults(doctor=True)
    quality_gate_parser.add_argument("--doctor-java", action="store_true", help="Include java -version diagnostics in the quality-gate doctor check.")
    quality_gate_parser.add_argument("--doctor-strict", action="store_true", help="Treat doctor warnings as a failed quality-gate doctor check.")
    quality_gate_parser.add_argument("--no-compile", dest="compile", action="store_false", help="Skip Python compileall check.")
    quality_gate_parser.set_defaults(compile=True)
    quality_gate_parser.add_argument("--no-unittest", dest="unittest", action="store_false", help="Skip unittest regression suite.")
    quality_gate_parser.set_defaults(unittest=True)
    quality_gate_parser.add_argument("--no-schema", dest="schema", action="store_false", help="Skip print-schema check.")
    quality_gate_parser.set_defaults(schema=True)
    quality_gate_parser.add_argument("--no-examples", dest="examples", action="store_false", help="Skip example spec regression.")
    quality_gate_parser.set_defaults(examples=True)
    quality_gate_parser.add_argument("--no-eval", dest="eval", action="store_false", help="Skip eval smoke benchmark.")
    quality_gate_parser.set_defaults(eval=True)
    quality_gate_parser.add_argument("--no-golden", dest="golden", action="store_false", help="Skip deterministic golden snapshot tests.")
    quality_gate_parser.set_defaults(golden=True)
    quality_gate_parser.add_argument("--no-failure-lab", dest="failure_lab", action="store_false", help="Skip failure injection lab checks.")
    quality_gate_parser.set_defaults(failure_lab=True)
    quality_gate_parser.add_argument("--no-repair-eval", dest="repair_eval", action="store_false", help="Skip repair evaluation metrics.")
    quality_gate_parser.set_defaults(repair_eval=True)
    quality_gate_parser.add_argument("--build-smoke", action="store_true", help="Also run a slow Gradle build smoke generation.")
    quality_gate_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Run local environment diagnostics for Python, Java, templates, workspace, docs, and CI files.",
    )
    doctor_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/doctor-runs/.")
    doctor_parser.add_argument("--no-java", dest="java", action="store_false", help="Skip java -version diagnostics.")
    doctor_parser.set_defaults(java=True)
    doctor_parser.add_argument("--strict", action="store_true", help="Treat warnings as a failed doctor run.")
    doctor_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    showcase_parser = subparsers.add_parser(
        "showcase",
        help="Run a portfolio-friendly offline showcase flow and write a consolidated report.",
    )
    showcase_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/showcase-runs/.")
    showcase_parser.add_argument("--planner", choices=["rules", "llm", "auto"], default="llm", help="Planner mode used by showcase agent runs.")
    showcase_parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="mock", help="LLM provider used by showcase agent runs.")
    showcase_parser.add_argument("--eval-limit", type=int, default=2, help="Number of default eval cases to run in showcase eval smoke.")
    showcase_build_group = showcase_parser.add_mutually_exclusive_group()
    showcase_build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build for showcase agent generate/modify cases.")
    showcase_build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build for showcase agent generate/modify cases.")
    showcase_parser.set_defaults(build=False)
    showcase_parser.add_argument("--quality-gate", action="store_true", help="Also run the default fast quality gate inside the showcase run.")
    showcase_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    portfolio_parser = subparsers.add_parser(
        "portfolio-demo",
        help="Run a portfolio-grade one-command offline demo flow and write a Chinese consolidated report.",
    )
    portfolio_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/portfolio-runs/.")
    portfolio_parser.add_argument("--planner", choices=["rules", "llm", "auto"], default="llm", help="Planner mode used by portfolio demo agent runs.")
    portfolio_parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="mock", help="LLM provider used by portfolio demo agent runs.")
    portfolio_parser.add_argument("--candidate-provider", choices=["mock", "openai-compatible"], default="mock", help="Candidate provider used by the LLM eval report step.")
    portfolio_parser.add_argument("--eval-limit", type=int, default=2, help="Number of default eval cases to run in showcase and LLM eval steps.")
    portfolio_build_group = portfolio_parser.add_mutually_exclusive_group()
    portfolio_build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build in portfolio demo generate/modify/eval steps.")
    portfolio_build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build for the fast offline portfolio demo.")
    portfolio_parser.set_defaults(build=False)
    portfolio_parser.add_argument("--quality-gate", action="store_true", help="Include the default fast quality gate inside the showcase step.")
    portfolio_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Generate a local static Web demo dashboard from showcase, capability, and RAG reports.",
    )
    dashboard_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/dashboard-runs/.")
    dashboard_parser.add_argument("--planner", choices=["rules", "llm", "auto"], default="llm", help="Planner mode used by the dashboard showcase run.")
    dashboard_parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="mock", help="LLM provider used by the dashboard showcase run.")
    dashboard_parser.add_argument("--eval-limit", type=int, default=2, help="Number of default eval cases to run in the dashboard showcase.")
    dashboard_parser.add_argument("--quality-gate", action="store_true", help="Include the default fast quality gate inside the showcase run.")
    dashboard_parser.add_argument("--no-showcase", dest="showcase", action="store_false", help="Skip the showcase run and render capabilities/RAG only.")
    dashboard_parser.set_defaults(showcase=True)
    dashboard_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    web_demo_parser = subparsers.add_parser(
        "web-demo",
        help="Start the interactive local Web Demo Dashboard server.",
    )
    web_demo_parser.add_argument("--host", default="127.0.0.1", help="Host interface for the local demo server.")
    web_demo_parser.add_argument("--port", type=int, default=8765, help="Port for the local demo server.")
    web_demo_parser.add_argument(
        "--planner",
        choices=["rules", "mock-llm", "real-llm", "auto-mock", "auto-real"],
        default="mock-llm",
        help="Default planner selection used by --smoke and shown in the Web Demo.",
    )
    web_demo_parser.add_argument("--open-browser", action="store_true", help="Open the demo URL in the default browser after startup.")
    web_demo_parser.add_argument("--smoke", action="store_true", help="Run a fast Web Demo backend smoke test instead of starting the blocking server.")
    web_demo_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    capabilities_parser = subparsers.add_parser(
        "capabilities",
        help="Export the supported capability matrix as JSON and Markdown reports.",
    )
    capabilities_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/capability-runs/.")
    capabilities_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    tools_manifest_parser = subparsers.add_parser(
        "tools-manifest",
        help="Export internal CLI capabilities as tool schemas for Function Calling or future MCP wrapping.",
    )
    tools_manifest_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/tool-manifest-runs/.")
    tools_manifest_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    harvest_report_parser = subparsers.add_parser(
        "harvest-report",
        help="Aggregate Free-Code Lab harvest candidates into a capability harvest report.",
    )
    harvest_report_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/harvest-runs/.")
    harvest_report_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    domains_parser = subparsers.add_parser(
        "domains",
        help="List registered DomainSpec plugins such as minecraft.neoforge, spring.api, and unity.component.",
    )
    domains_parser.add_argument("--status", choices=["all", "stable", "planned"], default="all", help="Filter DomainSpec plugins by implementation status.")
    domains_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    rag_eval_parser = subparsers.add_parser(
        "rag-eval",
        help="Run offline RAG retrieval quality cases and write Recall/MRR reports.",
    )
    rag_eval_parser.add_argument("--cases", help="Optional JSON file containing RAG eval cases.")
    rag_eval_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/rag-eval-runs/.")
    rag_eval_parser.add_argument("--limit", type=int, default=5, help="Maximum number of snippets to retrieve per query.")
    rag_eval_parser.add_argument("--recall-k", type=int, default=3, help="K used for Recall@K and category/capability hit checks.")
    rag_eval_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    knowledge_parser = subparsers.add_parser(
        "knowledge",
        help="Query the bundled NeoForge knowledge base and write RAG retrieval reports.",
    )
    knowledge_subparsers = knowledge_parser.add_subparsers(dest="knowledge_command", required=True)
    knowledge_query_parser = knowledge_subparsers.add_parser(
        "query",
        help="Retrieve NeoForge knowledge snippets for a natural language query.",
    )
    knowledge_query_parser.add_argument("query", help="Natural language query for the local NeoForge knowledge base.")
    knowledge_query_parser.add_argument("--limit", type=int, default=5, help="Maximum number of snippets to return.")
    knowledge_query_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/knowledge-runs/.")
    knowledge_query_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    test_examples_parser = subparsers.add_parser(
        "test-examples",
        help="Generate all example ModSpec files under the examples directory as regression smoke tests.",
    )
    test_examples_parser.add_argument("--examples-dir", default="examples", help="Directory containing example JSON specs.")
    build_group = test_examples_parser.add_mutually_exclusive_group()
    build_group.add_argument("--build", dest="build", action="store_true", help="Build each generated example project.")
    build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle builds for example projects.")
    test_examples_parser.set_defaults(build=False)
    test_examples_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    schema_parser = subparsers.add_parser(
        "print-schema",
        help="Print the supported ModSpec JSON schema.",
    )
    schema_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    agent_parser = subparsers.add_parser(
        "agent",
        help="Run the lightweight multi-agent orchestration workflow.",
    )
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command", required=True)

    agent_generate_parser = agent_subparsers.add_parser(
        "generate",
        help="Run planner/reviewer/executor/auditor/repair roles for a new workspace.",
    )
    agent_generate_parser.add_argument("request", help="Natural language mod request.")
    _add_agent_generation_arguments(agent_generate_parser)

    agent_develop_parser = agent_subparsers.add_parser(
        "develop",
        help="Run the full Minecraft mod coding-agent loop for a new workspace.",
    )
    agent_develop_parser.add_argument("request", help="Natural language mod development goal.")
    _add_agent_generation_arguments(agent_develop_parser, default_max_iterations=5)

    agent_modify_parser = agent_subparsers.add_parser(
        "modify",
        help="Run agent orchestration for modifying an existing workspace.",
    )
    agent_modify_parser.add_argument("workspace", help="Path or workspace name of an existing generated mod project.")
    agent_modify_parser.add_argument("change_request", help="Natural language change request.")
    _add_agent_common_arguments(agent_modify_parser)
    agent_modify_parser.add_argument("--build", dest="build", action="store_true", help="Run Gradle build after modifying the project.")
    agent_modify_parser.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build after modifying the project.")
    agent_modify_parser.set_defaults(build=False)
    agent_modify_parser.add_argument("--no-audit", dest="audit", action="store_false", help="Skip workspace audit after modification.")
    agent_modify_parser.set_defaults(audit=True)
    agent_modify_parser.add_argument("--no-repair", dest="repair", action="store_false", help="Skip repair-agent analysis when checks fail.")
    agent_modify_parser.set_defaults(repair=True)
    agent_modify_parser.add_argument("--max-iterations", type=int, default=1, help="Maximum repair iterations after failed checks.")
    agent_modify_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    agent_repair_parser = agent_subparsers.add_parser(
        "repair",
        help="Run the agent observe/retrieve/repair loop for an existing workspace.",
    )
    agent_repair_parser.add_argument("workspace", help="Path or workspace name of an existing generated mod project.")
    agent_repair_parser.add_argument(
        "--goal",
        default="Fix build and audit failures without changing user-owned files.",
        help="Natural language repair goal.",
    )
    agent_repair_parser.add_argument("--planner", choices=["rules", "llm", "auto"], default="llm", help="Planner label recorded in the repair trace.")
    agent_repair_parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="mock", help="LLM provider label recorded in the repair trace.")
    agent_repair_parser.add_argument("--max-iterations", type=int, default=5, help="Maximum repair-loop iterations.")
    repair_build_group = agent_repair_parser.add_mutually_exclusive_group()
    repair_build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build during repair checks.")
    repair_build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build during repair checks.")
    agent_repair_parser.set_defaults(build=True)
    repair_audit_group = agent_repair_parser.add_mutually_exclusive_group()
    repair_audit_group.add_argument("--audit", dest="audit", action="store_true", help="Run workspace audit during repair checks.")
    repair_audit_group.add_argument("--no-audit", dest="audit", action="store_false", help="Skip workspace audit during repair checks.")
    agent_repair_parser.set_defaults(audit=True)
    agent_repair_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    agent_bench_parser = agent_subparsers.add_parser(
        "bench",
        help="Run the agent benchmark suite and aggregate coding-agent metrics.",
    )
    agent_bench_parser.add_argument("--suite", help="Optional JSON file containing benchmark/eval cases.")
    agent_bench_parser.add_argument("--run-name", help="Optional stable run folder name under workspace/benchmark-runs/.")
    agent_bench_parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="mock", help="Primary provider to benchmark.")
    agent_bench_parser.add_argument("--baseline-provider", choices=["mock", "openai-compatible"], default="mock", help="Baseline provider for model A.")
    agent_bench_parser.add_argument("--eval-limit", type=int, default=3, help="Number of eval cases per model run.")
    agent_bench_parser.add_argument("--repair-limit", type=int, default=3, help="Number of injected failure repair cases.")
    agent_bench_parser.add_argument("--run-real", action="store_true", help="Actually run a real OpenAI-compatible provider instead of only preflighting it.")
    agent_bench_parser.add_argument("--require-real", action="store_true", help="Fail if the real provider is not configured.")
    bench_build_group = agent_bench_parser.add_mutually_exclusive_group()
    bench_build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build for benchmark cases.")
    bench_build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build for benchmark cases.")
    agent_bench_parser.set_defaults(build=False)
    bench_audit_group = agent_bench_parser.add_mutually_exclusive_group()
    bench_audit_group.add_argument("--audit", dest="audit", action="store_true", help="Run workspace audit for benchmark cases.")
    bench_audit_group.add_argument("--no-audit", dest="audit", action="store_false", help="Skip workspace audit for benchmark cases.")
    agent_bench_parser.set_defaults(audit=True)
    agent_bench_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    agent_lab_generate_parser = agent_subparsers.add_parser(
        "lab-generate",
        help="Run an isolated Free-Code Lab experiment from an existing generated workspace.",
    )
    agent_lab_generate_parser.add_argument("request", help="Natural language request that exceeds stable generate coverage.")
    agent_lab_generate_parser.add_argument("--from-workspace", required=True, help="Source generated workspace path or workspace name to copy into the lab run.")
    agent_lab_generate_parser.add_argument("--run-name", help="Stable run folder name under workspace/free-code-lab-runs/.")
    agent_lab_generate_parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="mock", help="LLM provider used to propose the experimental free-code plan.")
    lab_build_group = agent_lab_generate_parser.add_mutually_exclusive_group()
    lab_build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build inside the lab workspace.")
    lab_build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build inside the lab workspace.")
    agent_lab_generate_parser.set_defaults(build=False)
    agent_lab_generate_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    return parser


def _add_common_generation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mod-id", dest="mod_id", help="Override the generated mod_id.")
    parser.add_argument("--name", dest="display_name", help="Override the generated display name.")
    parser.add_argument("--package", dest="package_name", help="Override the generated Java package name.")
    parser.add_argument("--version", help="Override the mod version written into the generated workspace.")
    parser.add_argument("--author", action="append", dest="authors", default=[], help="Append an author entry. Repeat to add multiple authors.")
    parser.add_argument("--license", dest="license_name", help="Override the license name written into the workspace.")
    parser.add_argument("--description", help="Override the mod description.")
    parser.add_argument("--planner", choices=["rules", "llm", "auto"], default="rules", help="Planner mode to use for natural language parsing.")
    parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="openai-compatible", help="LLM provider used when planner=llm or planner=auto falls back to LLM.")
    _add_generation_execution_arguments(parser)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")


def _add_generation_execution_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-name", help="Optional workspace folder name under workspace/.")
    parser.add_argument("--overwrite", action="store_true", help="Delete an existing target workspace before generation.")
    build_group = parser.add_mutually_exclusive_group()
    build_group.add_argument("--build", dest="build", action="store_true", help="Run Gradle build after generating the project.")
    build_group.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build after generating the project.")
    parser.add_argument("--audit", action="store_true", help="Run workspace audit after generation or modification completes.")
    parser.set_defaults(build=False)


def _add_agent_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--planner", choices=["rules", "llm", "auto"], default="llm", help="Planner role implementation.")
    parser.add_argument("--llm-provider", choices=["mock", "openai-compatible"], default="mock", help="LLM provider for agent planning.")
    parser.add_argument("--require-llm", action="store_true", help="Fail instead of falling back to rules when planner=llm cannot produce a real LLM ModSpec.")
    parser.add_argument(
        "--code-lane",
        choices=["hybrid", "modspec", "direct"],
        default="hybrid",
        help="Code generation lane for agent runs: ModSpec-first hybrid, ModSpec only, or audited direct-code patch.",
    )


def _add_agent_generation_arguments(parser: argparse.ArgumentParser, *, default_max_iterations: int = 1) -> None:
    parser.add_argument("--mod-id", dest="mod_id", help="Override the generated mod_id.")
    parser.add_argument("--name", dest="display_name", help="Override the generated display name.")
    parser.add_argument("--package", dest="package_name", help="Override the generated Java package name.")
    parser.add_argument("--version", help="Override the mod version written into the generated workspace.")
    parser.add_argument("--author", action="append", dest="authors", default=[], help="Append an author entry. Repeat to add multiple authors.")
    parser.add_argument("--license", dest="license_name", help="Override the license name written into the workspace.")
    parser.add_argument("--description", help="Override the mod description.")
    _add_agent_common_arguments(parser)
    parser.add_argument("--workspace-name", help="Optional workspace folder name under workspace/.")
    parser.add_argument("--overwrite", action="store_true", help="Delete an existing target workspace before generation.")
    parser.add_argument("--build", dest="build", action="store_true", help="Run Gradle build after generating the project.")
    parser.add_argument("--no-build", dest="build", action="store_false", help="Skip Gradle build after generating the project.")
    parser.set_defaults(build=False)
    parser.add_argument("--no-audit", dest="audit", action="store_false", help="Skip workspace audit after generation.")
    parser.set_defaults(audit=True)
    parser.add_argument("--no-repair", dest="repair", action="store_false", help="Skip repair-agent analysis when checks fail.")
    parser.set_defaults(repair=True)
    parser.add_argument("--max-iterations", type=int, default=default_max_iterations, help="Maximum repair iterations after failed checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.default()

    if args.command == "build":
        return _run_build_command(args, config)
    if args.command == "repair":
        return _run_repair_command(args, config)
    if args.command == "repair-loop":
        return _run_repair_loop_command(args, config)
    if args.command == "audit":
        return _run_audit_command(args, config)
    if args.command == "replay":
        return _run_replay_command(args, config)
    if args.command == "eval":
        return _run_eval_command(args, config)
    if args.command == "eval-compare":
        return _run_eval_compare_command(args, config)
    if args.command == "llm-eval-report":
        return _run_llm_eval_report_command(args, config)
    if args.command == "llm-engineering-report":
        return _run_llm_engineering_report_command(args, config)
    if args.command == "real-llm-stability":
        return _run_real_llm_stability_command(args, config)
    if args.command == "benchmark-report":
        return _run_benchmark_report_command(args, config)
    if args.command == "evidence-chain-report":
        return _run_evidence_chain_report_command(args, config)
    if args.command == "golden-test":
        return _run_golden_test_command(args, config)
    if args.command == "failure-lab":
        return _run_failure_lab_command(args, config)
    if args.command == "repair-eval":
        return _run_repair_eval_command(args, config)
    if args.command == "quality-gate":
        return _run_quality_gate_command(args, config)
    if args.command == "doctor":
        return _run_doctor_command(args, config)
    if args.command == "showcase":
        return _run_showcase_command(args, config)
    if args.command == "portfolio-demo":
        return _run_portfolio_demo_command(args, config)
    if args.command == "web-demo":
        return _run_web_demo_command(args, config)
    if args.command == "dashboard":
        return _run_dashboard_command(args, config)
    if args.command == "capabilities":
        return _run_capabilities_command(args, config)
    if args.command == "tools-manifest":
        return _run_tools_manifest_command(args, config)
    if args.command == "harvest-report":
        return _run_harvest_report_command(args, config)
    if args.command == "domains":
        return _run_domains_command(args)
    if args.command == "rag-eval":
        return _run_rag_eval_command(args, config)
    if args.command == "knowledge":
        return _run_knowledge_command(args, config)
    if args.command == "print-schema":
        print(json.dumps(get_modspec_schema(), indent=2, ensure_ascii=False))
        return 0
    if args.command == "agent":
        return _run_agent_command(args, config)

    planner = ModProjectPlanner(config)

    if args.command == "generate-from-spec":
        spec = planner.spec_from_file(Path(args.spec_path))
        result = planner.execute_spec(
            spec,
            workspace_name=args.workspace_name,
            overwrite=args.overwrite,
            run_build=args.build,
        )
        payload = result.to_dict()
        payload = _append_audit_payload_if_requested(payload, workspace=result.workspace_dir, run_audit=args.audit, config=config)
        _print_payload(payload, as_json=args.json)
        return _payload_exit_code(payload, result.succeeded)

    if args.command == "modify":
        return _run_modify_command(args, config)

    if args.command == "test-examples":
        return _run_test_examples(args, planner)

    overrides = RequestOverrides(
        mod_id=getattr(args, "mod_id", None),
        display_name=getattr(args, "display_name", None),
        package_name=getattr(args, "package_name", None),
        version=getattr(args, "version", None),
        authors=getattr(args, "authors", []),
        license_name=getattr(args, "license_name", None),
        description=getattr(args, "description", None),
    )

    try:
        spec, planner_artifacts, planner_warnings, planner_mode_used = _resolve_spec_from_prompt(
            request=args.request,
            overrides=overrides,
            args=args,
            planner=planner,
            config=config,
        )
    except LLMPlanningError as exc:
        payload = {
            "error": str(exc),
            "planner_mode": getattr(args, "planner", "llm"),
            "llm_provider": getattr(args, "llm_provider", "openai-compatible"),
            "planner_warnings": exc.artifacts.warnings,
            "llm_raw_text": exc.artifacts.raw_text,
            "llm_parse_attempts": exc.artifacts.parse_attempts,
            "llm_retry_attempts": exc.artifacts.retry_attempts,
            "llm_json_repair_applied": exc.artifacts.json_repair_applied,
        }
        _print_payload(payload, as_json=args.json)
        return 1
    except ValueError as exc:
        payload = {
            "error": str(exc),
        }
        _print_payload(payload, as_json=args.json)
        return 1

    if args.command == "plan":
        payload = {
            "planner_mode": planner_mode_used,
            "planner_warnings": planner_warnings,
            "spec": spec.to_dict(),
            "steps": [step.to_dict() for step in planner.build_plan(run_build=args.build)],
        }
        _print_payload(payload, as_json=args.json)
        return 0

    if args.command == "validate":
        report = planner.validate(spec)
        payload = {
            "planner_mode": planner_mode_used,
            "planner_warnings": planner_warnings,
            "spec": spec.to_dict(),
            "validation": report.to_dict(),
        }
        _print_payload(payload, as_json=args.json)
        return 0 if report.is_valid else 1

    result = planner.execute_spec(
        spec,
        workspace_name=args.workspace_name,
        overwrite=args.overwrite,
        run_build=args.build,
        parsed_from_request=True,
    )
    if planner_artifacts is not None:
        planner_artifacts.planner_mode = planner_mode_used
        write_planner_artifacts(result.workspace_dir, config, planner_artifacts)

    if planner_warnings:
        result.warnings = [*planner_warnings, *result.warnings]
        write_generation_summary(result.workspace_dir, config, result.to_dict())

    payload = result.to_dict()
    payload["planner_mode"] = planner_mode_used
    payload = _append_audit_payload_if_requested(payload, workspace=result.workspace_dir, run_audit=args.audit, config=config)
    _print_payload(payload, as_json=args.json)
    return _payload_exit_code(payload, result.succeeded)


def _run_build_command(args: argparse.Namespace, config: AppConfig) -> int:
    project_dir = _resolve_project_dir(args.project, config)
    builder = GradleBuilder(config)
    result = builder.build(project_dir, repair=args.repair)
    payload = {
        "workspace_dir": str(project_dir),
        "build": result.to_dict(),
    }
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_repair_command(args: argparse.Namespace, config: AppConfig) -> int:
    project_dir = _resolve_project_dir(args.project, config)
    build_result_path = config.logs_dir_for(project_dir) / "gradle-build.json"
    log_path = config.logs_dir_for(project_dir) / "gradle-build.log"
    stdout_path = config.logs_dir_for(project_dir) / "gradle-build.stdout.log"
    stderr_path = config.logs_dir_for(project_dir) / "gradle-build.stderr.log"

    if not log_path.exists():
        payload = {
            "workspace_dir": str(project_dir),
            "error": f"Build log not found at {log_path}. Run build first.",
        }
        _print_payload(payload, as_json=args.json)
        return 1

    command: list[str] = []
    exit_code: int | None = None
    if build_result_path.exists():
        try:
            build_data = json.loads(build_result_path.read_text(encoding="utf-8"))
            command = [str(item) for item in build_data.get("command", [])]
            exit_code = build_data.get("exit_code", build_data.get("return_code"))
        except json.JSONDecodeError:
            command = []

    if not command:
        command = ["gradlew.bat", config.gradle_task, "--console=plain", "--no-configuration-cache"]

    repair_generator = RepairArtifactGenerator(config)
    artifacts = repair_generator.generate(
        project_dir=project_dir,
        command=command,
        exit_code=exit_code,
        log_path=log_path,
        stdout_path=stdout_path if stdout_path.exists() else None,
        stderr_path=stderr_path if stderr_path.exists() else None,
    )
    payload = {
        "workspace_dir": str(project_dir),
        "debug_context_path": str(artifacts.debug_context_path),
        "fix_request_path": str(artifacts.fix_request_path),
        "suspected_errors_path": str(artifacts.suspected_errors_path),
        "issues": [issue.to_dict() for issue in artifacts.issues],
    }
    _print_payload(payload, as_json=args.json)
    return 0


def _run_repair_loop_command(args: argparse.Namespace, config: AppConfig) -> int:
    workspace = _resolve_project_dir(args.project, config)
    result = AutoRepairRunner(config).run(
        workspace,
        max_attempts=args.max_attempts,
        run_build=args.build,
        run_audit=args.audit,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_audit_command(args: argparse.Namespace, config: AppConfig) -> int:
    workspace = _resolve_project_dir(args.project, config)
    try:
        result = WorkspaceAuditor(config).audit_workspace(workspace)
    except FileNotFoundError as exc:
        payload = {
            "success": False,
            "workspace": str(workspace),
            "error": str(exc),
        }
        _print_payload(payload, as_json=args.json)
        return 1
    payload = {
        "success": result.success,
        "workspace": result.workspace,
        "audit_report_path": result.audit_report_path,
        "errors_count": len(result.errors),
        "warnings_count": len(result.warnings),
        "checks_count": len(result.checks),
        "errors": [issue.to_dict() for issue in result.errors],
        "warnings": [issue.to_dict() for issue in result.warnings],
    }
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_replay_command(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        result = AgentRunReplayer(config).replay(args.target)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        payload = {
            "success": False,
            "target": args.target,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
        _print_payload(payload, as_json=args.json)
        return 1
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_eval_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = BenchmarkEvaluator(config).run(
        cases_path=Path(args.cases) if args.cases else None,
        planner_mode=args.planner,
        llm_provider=args.llm_provider,
        run_build=args.build,
        run_audit=args.audit,
        run_name=args.run_name,
        limit=args.limit,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_eval_compare_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = EvalComparisonRunner(config).compare(
        args.baseline,
        args.candidate,
        run_name=args.run_name,
        tolerance=args.tolerance,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_llm_eval_report_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = RealLLMEvalReportRunner(config).run(
        cases_path=Path(args.cases) if args.cases else None,
        run_name=args.run_name,
        limit=args.limit,
        baseline_provider=args.baseline_provider,
        candidate_provider=args.candidate_provider,
        run_build=args.build,
        run_audit=args.audit,
        tolerance=args.tolerance,
        require_real=args.require_real,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_llm_engineering_report_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = LLMEngineeringReportRunner(config).run(
        args.target,
        run_name=args.run_name,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_real_llm_stability_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = RealLLMStabilityRunner(config).run(
        cases_path=Path(args.cases) if args.cases else None,
        run_name=args.run_name,
        limit=args.limit,
        llm_provider=args.llm_provider,
        run_build=args.build,
        run_audit=args.audit,
        fallback_probe=args.fallback_probe,
        require_real=args.require_real,
        runtime_evidence_path=Path(args.runtime_evidence) if args.runtime_evidence else None,
        require_runtime=args.require_runtime,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_benchmark_report_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = BenchmarkReportRunner(config).run(
        cases_path=Path(args.cases) if args.cases else None,
        run_name=args.run_name,
        eval_limit=args.eval_limit,
        repair_limit=args.repair_limit,
        baseline_provider=args.baseline_provider,
        candidate_provider=args.candidate_provider,
        run_build=args.build,
        run_audit=args.audit,
        run_real=args.run_real,
        require_real=args.require_real,
        runtime_evidence_path=Path(args.runtime_evidence) if args.runtime_evidence else None,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_evidence_chain_report_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = EvidenceChainReportRunner(config).run(
        run_name=args.run_name,
        eval_limit=args.eval_limit,
        repair_limit=args.repair_limit,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_golden_test_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = GoldenTestRunner(config).run(
        run_name=args.run_name,
        limit=args.limit,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_failure_lab_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = FailureLabRunner(config).run(
        run_name=args.run_name,
        case_ids=args.cases,
        limit=args.limit,
        run_build=args.build,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_repair_eval_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = RepairEvalRunner(config).run(
        run_name=args.run_name,
        case_ids=args.cases,
        limit=args.limit,
        run_build=args.build,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_quality_gate_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = QualityGateRunner(config).run(
        run_name=args.run_name,
        eval_limit=args.eval_limit,
        run_doctor=args.doctor,
        run_doctor_java=args.doctor_java,
        doctor_strict=args.doctor_strict,
        run_compile=args.compile,
        run_unittest=args.unittest,
        run_schema=args.schema,
        run_examples=args.examples,
        run_eval=args.eval,
        run_golden=args.golden,
        run_failure_lab=args.failure_lab,
        run_repair_eval=args.repair_eval,
        run_build_smoke=args.build_smoke,
        timeout_seconds=args.timeout_seconds,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_doctor_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = EnvironmentDoctor(config).run(
        run_name=args.run_name,
        check_java=args.java,
        strict=args.strict,
    )
    payload = result.to_dict()
    payload["strict"] = args.strict
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_showcase_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = ShowcaseRunner(config).run(
        run_name=args.run_name,
        planner_mode=args.planner,
        llm_provider=args.llm_provider,
        run_build=args.build,
        run_quality_gate=args.quality_gate,
        eval_limit=args.eval_limit,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_portfolio_demo_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = PortfolioDemoRunner(config).run(
        run_name=args.run_name,
        planner_mode=args.planner,
        llm_provider=args.llm_provider,
        candidate_provider=args.candidate_provider,
        eval_limit=args.eval_limit,
        run_build=args.build,
        run_quality_gate=args.quality_gate,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_capabilities_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = CapabilityCatalog(config).build(run_name=args.run_name)
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_tools_manifest_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = ToolManifestRunner(config).build(run_name=args.run_name)
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_harvest_report_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = HarvestReportRunner(config).run(run_name=args.run_name)
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_domains_command(args: argparse.Namespace) -> int:
    registry = DomainSpecRegistry.default()
    status = None if args.status == "all" else args.status
    domains = [metadata.to_dict() for metadata in registry.list_metadata(status=status)]
    payload = {
        "success": True,
        "domains": domains,
        "domains_count": len(domains),
        "stable_count": sum(1 for domain in domains if domain["status"] == "stable"),
        "planned_count": sum(1 for domain in domains if domain["status"] == "planned"),
    }
    _print_payload(payload, as_json=args.json)
    return 0


def _run_web_demo_command(args: argparse.Namespace, config: AppConfig) -> int:
    if args.smoke:
        payload = WebDemoRunner(config).smoke(planner_selection=args.planner)
        _print_payload(payload, as_json=args.json)
        return 0 if payload.get("success") else 1

    result = WebDemoServer(config).serve(
        host=args.host,
        port=args.port,
        open_browser=args.open_browser,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_dashboard_command(args: argparse.Namespace, config: AppConfig) -> int:
    result = WebDashboardRunner(config).run(
        run_name=args.run_name,
        planner_mode=args.planner,
        llm_provider=args.llm_provider,
        eval_limit=args.eval_limit,
        run_showcase=args.showcase,
        run_quality_gate=args.quality_gate,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_rag_eval_command(args: argparse.Namespace, config: AppConfig) -> int:
    cases_path = Path(args.cases) if args.cases else None
    result = RAGEvalRunner(config).run(
        cases_path=cases_path,
        run_name=args.run_name,
        limit=args.limit,
        recall_k=args.recall_k,
    )
    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _run_knowledge_command(args: argparse.Namespace, config: AppConfig) -> int:
    if args.knowledge_command == "query":
        result = KnowledgeQueryRunner(config).query(
            args.query,
            limit=args.limit,
            run_name=args.run_name,
        )
        _print_payload(result.to_dict(), as_json=args.json)
        return 0 if result.success else 1
    payload = {"success": False, "error": f"Unsupported knowledge command: {args.knowledge_command}"}
    _print_payload(payload, as_json=args.json)
    return 1


def _run_test_examples(args: argparse.Namespace, planner: ModProjectPlanner) -> int:
    examples_dir = Path(args.examples_dir)
    spec_paths = sorted(path for path in examples_dir.glob("*.json") if not path.name.endswith("_expected.json"))
    payload = {"results": []}
    exit_code = 0

    for spec_path in spec_paths:
        spec = planner.spec_from_file(spec_path)
        workspace_name = spec_path.stem
        result = planner.execute_spec(
            spec,
            workspace_name=workspace_name,
            overwrite=True,
            run_build=args.build,
        )
        payload["results"].append(
            {
                "example": str(spec_path),
                "workspace_dir": str(result.workspace_dir),
                "succeeded": result.succeeded,
                "warnings": list(result.warnings),
                "build": result.build.to_dict(),
            }
        )
        if not result.succeeded:
            exit_code = 1

    _print_payload(payload, as_json=args.json)
    return exit_code


def _run_modify_command(args: argparse.Namespace, config: AppConfig) -> int:
    workspace = _resolve_project_dir(args.workspace, config)
    modifier = WorkspaceModifier(config)
    result = modifier.modify(
        workspace,
        args.change_request,
        planner_mode=args.planner,
        llm_provider=args.llm_provider,
        run_build=args.build,
        repair=args.repair,
    )
    payload = {
        "success": result.success,
        "workspace": str(result.workspace),
        "modspec_path": str(result.modspec_path),
        "modify_summary_path": str(result.modify_summary_path),
        "added": result.added,
        "updated": result.updated,
        "skipped": result.skipped,
        "warnings": result.warnings,
        "build": result.build.to_dict(),
    }
    payload = _append_audit_payload_if_requested(payload, workspace=result.workspace, run_audit=args.audit, config=config)
    _print_payload(payload, as_json=args.json)
    return _payload_exit_code(payload, result.success)


def _run_agent_command(args: argparse.Namespace, config: AppConfig) -> int:
    if args.agent_command == "lab-generate":
        result = FreeCodeLabRunner(config).run(
            args.request,
            from_workspace=_resolve_project_dir(args.from_workspace, config),
            run_name=args.run_name,
            llm_provider=args.llm_provider,
            run_build=args.build,
        )
        payload = result.to_dict()
        _print_payload(payload, as_json=args.json)
        return 0 if result.success else 1

    if args.agent_command == "bench":
        result = AgentBenchmarkRunner(config).run(
            cases_path=Path(args.suite) if args.suite else None,
            run_name=args.run_name,
            eval_limit=args.eval_limit,
            repair_limit=args.repair_limit,
            llm_provider=args.llm_provider,
            run_build=args.build,
            run_audit=args.audit,
        )
        payload = result.to_dict()
        _print_payload(payload, as_json=args.json)
        return 0 if result.success else 1

    orchestrator = AgentOrchestrator(config)
    if args.agent_command in {"generate", "develop"}:
        overrides = RequestOverrides(
            mod_id=getattr(args, "mod_id", None),
            display_name=getattr(args, "display_name", None),
            package_name=getattr(args, "package_name", None),
            version=getattr(args, "version", None),
            authors=getattr(args, "authors", []),
            license_name=getattr(args, "license_name", None),
            description=getattr(args, "description", None),
        )
        run_kwargs = {
            "overrides": overrides,
            "planner_mode": args.planner,
            "llm_provider": args.llm_provider,
            "workspace_name": args.workspace_name,
            "overwrite": args.overwrite,
            "run_build": args.build,
            "run_audit": args.audit,
            "repair": args.repair,
            "require_llm": args.require_llm,
            "code_lane": args.code_lane,
            "max_iterations": args.max_iterations,
        }
        if args.agent_command == "develop":
            result = orchestrator.run_develop(args.request, **run_kwargs)
        else:
            result = orchestrator.run_generate(args.request, **run_kwargs)
    elif args.agent_command == "repair":
        result = orchestrator.run_repair(
            _resolve_project_dir(args.workspace, config),
            goal=args.goal,
            planner_mode=args.planner,
            llm_provider=args.llm_provider,
            max_iterations=args.max_iterations,
            run_build=args.build,
            run_audit=args.audit,
        )
    else:
        result = orchestrator.run_modify(
            _resolve_project_dir(args.workspace, config),
            args.change_request,
            planner_mode=args.planner,
            llm_provider=args.llm_provider,
            run_build=args.build,
            run_audit=args.audit,
            repair=args.repair,
            code_lane=args.code_lane,
            max_iterations=args.max_iterations,
        )

    payload = result.to_dict()
    _print_payload(payload, as_json=args.json)
    return 0 if result.success else 1


def _agent_bench_payload(result) -> dict:
    payload = result.to_dict()
    model_runs = payload.get("model_runs") or []
    completed = [run for run in model_runs if run.get("status") in {"pass", "fail"}]
    audit_rates = [
        float((run.get("metrics") or {}).get("audit_success_rate", 0) or 0)
        for run in completed
    ]
    rag_rates = [
        float((run.get("metrics") or {}).get("rag_hit_rate", 0) or 0)
        for run in completed
    ]
    trace_paths: list[str] = []
    failed_cases: list[dict] = []
    tool_call_counts: list[int] = []
    repair_attempt_counts: list[int] = []
    for run in completed:
        eval_path = run.get("eval_report_path")
        if not eval_path:
            continue
        try:
            eval_report = json.loads(Path(eval_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for case in eval_report.get("cases", []):
            if not isinstance(case, dict):
                continue
            if case.get("agent_run_json_path"):
                trace_path = str(case["agent_run_json_path"])
                trace_paths.append(trace_path)
                _collect_agent_run_metrics(Path(trace_path), tool_call_counts, repair_attempt_counts)
            if not case.get("success"):
                failed_cases.append(
                    {
                        "id": case.get("id"),
                        "mode": case.get("mode"),
                        "workspace": case.get("workspace"),
                        "errors": case.get("errors", []),
                    }
                )
    for failure in payload.get("failure_types") or []:
        if isinstance(failure, dict) and not failure.get("success"):
            failed_cases.append(
                {
                    "id": failure.get("id"),
                    "mode": "repair",
                    "workspace": failure.get("workspace"),
                    "errors": [failure.get("title", "repair failure")],
                }
            )
    metrics = payload.get("metrics") or {}
    agent_metrics = {
        "success_rate": metrics.get("best_success_rate", 0),
        "build_success_rate": metrics.get("build_pass_rate"),
        "audit_success_rate": max(audit_rates, default=0),
        "repair_success_rate": metrics.get("repair_rate", 0),
        "avg_tool_calls": round(sum(tool_call_counts) / len(tool_call_counts), 2) if tool_call_counts else 0,
        "avg_iterations": round(sum(repair_attempt_counts) / len(repair_attempt_counts), 2) if repair_attempt_counts else 1,
        "rag_hit_rate": max(rag_rates, default=0),
        "failed_cases": failed_cases,
        "trace_paths": trace_paths,
    }
    payload["agent_bench_metrics"] = agent_metrics
    payload.update(agent_metrics)
    return payload


def _collect_agent_run_metrics(
    trace_path: Path,
    tool_call_counts: list[int],
    repair_attempt_counts: list[int],
) -> None:
    try:
        agent_run = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    tool_trace_path = agent_run.get("tool_call_trace_json_path")
    if tool_trace_path:
        try:
            tool_trace = json.loads(Path(tool_trace_path).read_text(encoding="utf-8"))
            if isinstance(tool_trace, list):
                tool_call_counts.append(len(tool_trace))
        except (OSError, json.JSONDecodeError):
            pass
    if not tool_trace_path:
        tool_call_counts.append(len(agent_run.get("steps", []) or []))
    repair_payload = ((agent_run.get("payload") or {}).get("repair") or {})
    iterations = repair_payload.get("iterations")
    if isinstance(iterations, int):
        repair_attempt_counts.append(iterations)
        return
    repair_loop = repair_payload.get("repair_loop") or {}
    attempts_count = repair_loop.get("attempts_count")
    if isinstance(attempts_count, int):
        repair_attempt_counts.append(attempts_count)
    else:
        repair_attempt_counts.append(1)


def _resolve_spec_from_prompt(
    *,
    request: str,
    overrides: RequestOverrides,
    args: argparse.Namespace,
    planner: ModProjectPlanner,
    config: AppConfig,
) -> tuple[ModSpec, PlannerArtifacts | None, list[str], str]:
    planner_mode = getattr(args, "planner", "rules")
    provider = getattr(args, "llm_provider", "openai-compatible")

    if planner_mode == "rules":
        return planner.parse_request(request, overrides=overrides), None, [], "rules"

    if planner_mode == "llm":
        health = check_llm_provider_health(provider)
        if provider == "openai-compatible" and not health.healthy:
            spec = planner.parse_request(request, overrides=overrides)
            warnings = [
                "LLM provider health check failed; generate planner fell back to rules.",
                *health.errors,
                *health.warnings,
            ]
            return spec, None, warnings, "llm->rules"
        try:
            client = create_llm_client(provider, config.project_root)
            spec, artifacts = plan_with_llm(request, client, config=config)
            _apply_overrides(spec, overrides)
            return spec, artifacts, list(artifacts.warnings), "llm"
        except (LLMPlanningError, ValueError, RuntimeError) as exc:
            spec = planner.parse_request(request, overrides=overrides)
            artifacts = exc.artifacts if isinstance(exc, LLMPlanningError) else None
            warnings = [f"LLM planner failed; fallback to rules: {exc}"]
            if artifacts is not None:
                warnings.extend(artifacts.warnings)
            return spec, artifacts, warnings, "llm->rules"

    rules_spec = planner.parse_request(request, overrides=overrides)
    if not _rules_planner_needs_llm(request, rules_spec):
        return rules_spec, None, [], "rules"

    health = check_llm_provider_health(provider)
    if provider == "openai-compatible" and not health.healthy:
        warnings = [
            "Auto planner fallback to rules because LLM provider health check failed.",
            *health.errors,
            *health.warnings,
        ]
        return rules_spec, None, warnings, "auto->rules"
    try:
        client = create_llm_client(provider, config.project_root)
        spec, artifacts = plan_with_llm(request, client, config=config)
        _apply_overrides(spec, overrides)
        warnings = [*artifacts.warnings, "Auto planner used LLM because rules parsing looked incomplete."]
        return spec, artifacts, warnings, "auto->llm"
    except (LLMPlanningError, ValueError, RuntimeError) as exc:
        artifacts = exc.artifacts if isinstance(exc, LLMPlanningError) else None
        warnings = [f"Auto planner fallback to rules: {exc}"]
        if artifacts is not None:
            warnings.extend(artifacts.warnings)
        return rules_spec, artifacts, warnings, "auto->rules"


def _apply_overrides(spec: ModSpec, overrides: RequestOverrides) -> None:
    if overrides.mod_id:
        spec.mod_id = slugify_mod_id(overrides.mod_id)
    if overrides.display_name:
        spec.display_name = overrides.display_name
    if overrides.package_name:
        spec.package_name = overrides.package_name
    if overrides.version:
        spec.version = overrides.version
    if overrides.authors:
        spec.authors = list(overrides.authors)
    if overrides.license_name:
        spec.license_name = overrides.license_name
    if overrides.description:
        spec.description = overrides.description


def _rules_planner_needs_llm(request: str, spec: ModSpec) -> bool:
    if spec.all_content() or spec.entities or spec.recipes:
        expected_checks = [
            ("方块", bool(spec.blocks)),
            ("矿石", bool(spec.ores)),
            ("苹果", bool(spec.foods)),
            ("剑", bool(spec.swords)),
            ("工具", bool(spec.tools)),
            ("护甲", bool(spec.armors)),
            ("实体", bool(spec.entities)),
            ("生物", bool(spec.entities)),
        ]
        for token, matched in expected_checks:
            if token in request and not matched:
                return True
        if "分解" in request and not any(recipe.recipe_type == "shapeless" for recipe in spec.recipes):
            return True
        return False
    return True


def _print_payload(payload: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if "dashboard_index_path" in payload:
        print(f"dashboard: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"index: {payload.get('dashboard_index_path')}")
        print(f"data: {payload.get('dashboard_data_path')}")
        print(f"report: {payload.get('dashboard_report_md_path')}")
        for step in payload.get("steps", []):
            print(f"- {step.get('name')}: {step.get('status')} - {step.get('summary')}")
        return

    if "web_demo_url" in payload or payload.get("web_demo_smoke"):
        if payload.get("web_demo_smoke"):
            print(f"web demo smoke: {'success' if payload.get('success') else 'failed'}")
            print(f"workspace: {payload.get('workspace')}")
            print(f"features: {payload.get('modspec_feature_count')}")
            print(f"generated files: {payload.get('generated_files_count')}")
            print(f"audit: {payload.get('audit_success')}")
            return
        print(f"web demo: {'success' if payload.get('success') else 'failed'}")
        print(f"url: {payload.get('web_demo_url')}")
        print(payload.get("message", ""))
        return

    if "rag_eval_report_json_path" in payload:
        metrics = payload.get("metrics", {})
        recall_k = payload.get("recall_k", 3)
        print(f"rag eval: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"cases: {metrics.get('success_count', 0)}/{metrics.get('total_cases', 0)} passed")
        print(f"expanded Recall@1: {metrics.get('expanded_recall_at_1')}")
        print(f"expanded Recall@{recall_k}: {metrics.get('expanded_recall_at_k')}")
        print(f"expanded MRR: {metrics.get('expanded_mrr')}")
        print(f"rewrite Recall@{recall_k} delta: {metrics.get('query_rewrite_recall_at_k_delta')}")
        print(f"rag eval json: {payload.get('rag_eval_report_json_path')}")
        print(f"rag eval report: {payload.get('rag_eval_report_md_path')}")
        failed = [case for case in payload.get("cases", []) if not case.get("success")]
        if failed:
            print("")
            print("failed rag-eval cases:")
            for case in failed:
                print(f"- {case.get('id')}: {', '.join(case.get('errors') or ['failed'])}")
        return

    if "hits_count" in payload and "context" in payload and "query" in payload:
        print(f"knowledge query: {payload.get('query')}")
        print(f"hits: {payload.get('hits_count')}")
        print(f"report json: {payload.get('report_json_path')}")
        print(f"report md: {payload.get('report_md_path')}")
        for hit in payload.get("hits", []):
            print(f"- {hit.get('id')} score={hit.get('score')}: {hit.get('title')}")
        return

    if "eval_compare_report_json_path" in payload:
        print(f"eval compare: {'success' if payload.get('success') else 'regression'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"regressions: {payload.get('regressions_count', 0)}")
        print(f"improvements: {payload.get('improvements_count', 0)}")
        print(f"warnings: {payload.get('warnings_count', 0)}")
        print(f"compare json: {payload.get('eval_compare_report_json_path')}")
        print(f"compare report: {payload.get('eval_compare_report_md_path')}")
        if payload.get("regressions"):
            print("")
            print("regressions:")
            for item in payload["regressions"]:
                print(f"- {item}")
        return

    if "real_llm_stability_json_path" in payload:
        metrics = payload.get("metrics", {})
        print(f"real LLM stability: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"provider: {payload.get('llm_provider')}")
        print(f"real LLM success: {metrics.get('real_llm_success_count', 0)}/{metrics.get('total_cases', 0)}")
        print(f"provider failures: {metrics.get('provider_failure_count', 0)}")
        print(f"schema failures: {metrics.get('schema_failure_count', 0)}")
        print(f"audit failures: {metrics.get('audit_failure_count', 0)}")
        print(f"build failures: {metrics.get('build_failure_count', 0)}")
        print(f"runtime failures: {metrics.get('runtime_failure_count', 0)}")
        print(f"runtime unverified: {metrics.get('runtime_unverified_count', 0)}")
        print(f"fallback success: {metrics.get('fallback_success_count', 0)}")
        print(f"tokens: {metrics.get('total_tokens', 0)}")
        print(f"estimated cost USD: {metrics.get('estimated_cost_usd')}")
        print(f"stability json: {payload.get('real_llm_stability_json_path')}")
        print(f"stability report: {payload.get('real_llm_stability_md_path')}")
        failed = [case for case in payload.get("cases", []) if not case.get("real_llm_success")]
        if failed:
            print("")
            print("non-real-success cases:")
            for case in failed:
                print(f"- {case.get('id')}: {case.get('outcome')} ({case.get('failure_type') or 'no failure type'})")
        return

    if "benchmark_report_json_path" in payload:
        metrics = payload.get("metrics", {})
        if payload.get("benchmark_kind") == "agent":
            print(f"agent benchmark: {'success' if payload.get('success') else 'failed'}")
            print(f"run id: {payload.get('run_id')}")
            print(f"success rate: {metrics.get('success_rate')}")
            print(f"audit success rate: {metrics.get('audit_success_rate')}")
            print(f"repair success rate: {metrics.get('repair_success_rate')}")
            print(f"avg tool calls: {metrics.get('avg_tool_calls')}")
            print(f"avg iterations: {metrics.get('avg_iterations')}")
            print(f"patch accept rate: {metrics.get('patch_accept_rate')}")
            print(f"rollback count: {metrics.get('rollback_count')}")
            print(f"benchmark json: {payload.get('benchmark_report_json_path')}")
            print(f"benchmark report: {payload.get('benchmark_report_md_path')}")
            print(f"benchmark page: {payload.get('benchmark_report_html_path')}")
            return
        print(f"benchmark report: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"models completed: {metrics.get('model_runs_completed')}/{metrics.get('model_runs_total')}")
        print(f"repair rate: {metrics.get('repair_rate')}")
        print(f"build pass rate: {metrics.get('build_pass_rate')}")
        print(f"runtime pass rate: {metrics.get('runtime_pass_rate')}")
        print(f"benchmark json: {payload.get('benchmark_report_json_path')}")
        print(f"benchmark report: {payload.get('benchmark_report_md_path')}")
        print(f"benchmark page: {payload.get('benchmark_report_html_path')}")
        return

    if "evidence_chain_report_json_path" in payload:
        metrics = payload.get("metrics", {})
        print(f"evidence chain: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"layers: {metrics.get('layers_passed')}/{metrics.get('layers_total')} passed")
        print(f"acceptance success rate: {metrics.get('acceptance_success_rate')}")
        print(f"recovery rate: {metrics.get('recovery_rate')}")
        print(f"generated files total: {metrics.get('generated_files_total')}")
        print(f"runtime pass rate: {metrics.get('runtime_validation_pass_rate')}")
        print(f"evidence chain json: {payload.get('evidence_chain_report_json_path')}")
        print(f"evidence chain report: {payload.get('evidence_chain_report_md_path')}")
        return

    if "golden_report_json_path" in payload:
        print(f"golden test: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"report dir: {payload.get('report_dir')}")
        print(
            "cases: "
            f"{payload.get('passed_count', 0)} passed, "
            f"{payload.get('failed_count', 0)} failed"
        )
        print(f"golden json: {payload.get('golden_report_json_path')}")
        print(f"golden report: {payload.get('golden_report_md_path')}")
        failed = [case for case in payload.get("cases", []) if not case.get("success")]
        if failed:
            print("")
            print("failed golden cases:")
            for case in failed:
                print(f"- {case.get('id')}: {', '.join(case.get('errors') or ['failed'])}")
        return

    if "eval_report_json_path" in payload:
        metrics = payload.get("metrics", {})
        print(f"eval run: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"eval dir: {payload.get('eval_dir')}")
        print(f"planner: {payload.get('planner_mode')}")
        print(f"llm provider: {payload.get('llm_provider')}")
        print(f"cases: {metrics.get('success_count', 0)}/{metrics.get('total_cases', 0)} passed")
        print(f"feature match: {metrics.get('expected_features_matched', 0)}/{metrics.get('expected_features_total', 0)}")
        if metrics.get("audit_attempted_count"):
            print(f"audit: {metrics.get('audit_success_count', 0)}/{metrics.get('audit_attempted_count', 0)} passed")
        if metrics.get("build_attempted_count"):
            print(f"build: {metrics.get('build_success_count', 0)}/{metrics.get('build_attempted_count', 0)} passed")
        print(f"eval report json: {payload.get('eval_report_json_path')}")
        print(f"eval report md: {payload.get('eval_report_md_path')}")
        failed = [case for case in payload.get("cases", []) if not case.get("success")]
        if failed:
            print("")
            print("failed cases:")
            for case in failed:
                print(f"- {case.get('id')}: {', '.join(case.get('errors') or ['failed'])}")
        return

    if "quality_gate_report_json_path" in payload:
        print(f"quality gate: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"report dir: {payload.get('report_dir')}")
        print(
            "checks: "
            f"{payload.get('passed_count', 0)} passed, "
            f"{payload.get('failed_count', 0)} failed, "
            f"{payload.get('skipped_count', 0)} skipped"
        )
        print(f"quality gate json: {payload.get('quality_gate_report_json_path')}")
        print(f"quality gate report: {payload.get('quality_gate_report_md_path')}")
        failed = [check for check in payload.get("checks", []) if check.get("status") == "fail"]
        if failed:
            print("")
            print("failed checks:")
            for check in failed:
                print(f"- {check.get('name')}: {check.get('summary')}")
                if check.get("stderr_path"):
                    print(f"  stderr: {check.get('stderr_path')}")
        return

    if "failure_lab_report_json_path" in payload and "repair_eval_report_json_path" not in payload:
        print(f"failure lab: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"report dir: {payload.get('report_dir')}")
        print(
            "cases: "
            f"{payload.get('passed_count', 0)} passed, "
            f"{payload.get('failed_count', 0)} failed"
        )
        print(f"repair RAG hits: {payload.get('repair_rag_hits_count', 0)}")
        print(f"failure lab json: {payload.get('failure_lab_report_json_path')}")
        print(f"failure lab report: {payload.get('failure_lab_report_md_path')}")
        failed = [case for case in payload.get("cases", []) if not case.get("success")]
        if failed:
            print("")
            print("failed failure-lab cases:")
            for case in failed:
                print(f"- {case.get('id')}: {', '.join(case.get('errors') or ['failed'])}")
        return

    if "repair_eval_report_json_path" in payload:
        metrics = payload.get("metrics", {})
        total = metrics.get("total_cases", payload.get("cases_count", 0))
        print(f"repair eval: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"report dir: {payload.get('report_dir')}")
        print(f"cases: {metrics.get('full_success_count', 0)}/{total} full success")
        print(f"audit detected: {metrics.get('audit_detected_count', 0)}/{total}")
        print(f"repair RAG relevant: {metrics.get('repair_rag_relevant_count', 0)}/{total}")
        print(f"repair-loop repaired: {metrics.get('repair_loop_repaired_count', 0)}/{total}")
        print(f"audit recovered: {metrics.get('audit_recovered_count', 0)}/{total}")
        print(f"repair eval json: {payload.get('repair_eval_report_json_path')}")
        print(f"repair eval report: {payload.get('repair_eval_report_md_path')}")
        failed = [case for case in payload.get("cases", []) if not case.get("success")]
        if failed:
            print("")
            print("failed repair-eval cases:")
            for case in failed:
                print(f"- {case.get('id')}: {', '.join(case.get('errors') or ['failed'])}")
        return

    if "doctor_report_json_path" in payload:
        print(f"doctor: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"report dir: {payload.get('report_dir')}")
        print(
            "checks: "
            f"{payload.get('passed_count', 0)} passed, "
            f"{payload.get('warnings_count', 0)} warnings, "
            f"{payload.get('failed_count', 0)} failed, "
            f"{payload.get('skipped_count', 0)} skipped"
        )
        print(f"doctor json: {payload.get('doctor_report_json_path')}")
        print(f"doctor report: {payload.get('doctor_report_md_path')}")
        notable = [check for check in payload.get("checks", []) if check.get("status") in {"warning", "fail"}]
        if notable:
            print("")
            print("doctor findings:")
            for check in notable:
                print(f"- {check.get('id')}: {check.get('status')} ({check.get('message')})")
        return

    if "repair_loop_report_json_path" in payload:
        print(f"repair loop: {'success' if payload.get('success') else 'failed'}")
        print(f"workspace: {payload.get('workspace')}")
        print(f"attempts: {payload.get('attempts_count')}")
        print(f"repaired: {payload.get('repaired')}")
        print(f"repair loop json: {payload.get('repair_loop_report_json_path')}")
        print(f"repair loop report: {payload.get('repair_loop_report_md_path')}")
        failed = [attempt for attempt in payload.get("attempts", []) if not attempt.get("success")]
        if failed:
            print("")
            print("failed attempts:")
            for attempt in failed:
                print(f"- {attempt.get('phase')}: {', '.join(attempt.get('errors') or ['failed'])}")
        return

    if "portfolio_report_json_path" in payload:
        print(f"portfolio demo: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"portfolio dir: {payload.get('portfolio_dir')}")
        print(
            "steps: "
            f"{payload.get('passed_count', 0)} passed, "
            f"{payload.get('failed_count', 0)} failed, "
            f"{payload.get('skipped_count', 0)} skipped"
        )
        print(f"portfolio json: {payload.get('portfolio_report_json_path')}")
        print(f"portfolio report: {payload.get('portfolio_report_md_path')}")
        failed = [step for step in payload.get("steps", []) if step.get("status") == "fail"]
        if failed:
            print("")
            print("failed portfolio steps:")
            for step in failed:
                print(f"- {step.get('name')}: {step.get('summary')}")
        return

    if "showcase_report_json_path" in payload:
        print(f"showcase: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"showcase dir: {payload.get('showcase_dir')}")
        print(
            "steps: "
            f"{payload.get('passed_count', 0)} passed, "
            f"{payload.get('failed_count', 0)} failed, "
            f"{payload.get('skipped_count', 0)} skipped"
        )
        print(f"showcase json: {payload.get('showcase_report_json_path')}")
        print(f"showcase report: {payload.get('showcase_report_md_path')}")
        failed = [step for step in payload.get("steps", []) if step.get("status") == "fail"]
        if failed:
            print("")
            print("failed showcase steps:")
            for step in failed:
                print(f"- {step.get('name')}: {step.get('summary')}")
        return

    if "capability_report_json_path" in payload:
        print(f"capabilities: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"version: {payload.get('version')}")
        print(f"sections: {payload.get('sections_count')}")
        print(f"capabilities: {payload.get('capabilities_count')}")
        print(f"capabilities json: {payload.get('capability_report_json_path')}")
        print(f"capabilities report: {payload.get('capability_report_md_path')}")
        return

    if "tools_manifest_json_path" in payload:
        print(f"tools manifest: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"version: {payload.get('version')}")
        print(f"tools: {payload.get('tools_count')}")
        print(f"tools manifest json: {payload.get('tools_manifest_json_path')}")
        print(f"tools manifest report: {payload.get('tools_manifest_md_path')}")
        return

    if "harvest_candidate" in payload and "lab_workspace" in payload:
        print(f"free-code lab: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"source workspace: {payload.get('source_workspace')}")
        print(f"lab workspace: {payload.get('lab_workspace')}")
        print(f"report dir: {payload.get('report_dir')}")
        print(f"changed files: {len(payload.get('changed_files') or [])}")
        candidate = payload.get("harvest_candidate") or {}
        print(f"harvest recommendation: {candidate.get('recommendation')}")
        artifacts = payload.get("artifacts") or {}
        if artifacts.get("report_json"):
            print(f"free-code report: {artifacts.get('report_json')}")
        if artifacts.get("harvest_candidate_json"):
            print(f"harvest candidate: {artifacts.get('harvest_candidate_json')}")
        return

    if "report_json_path" in payload and "candidates" in payload:
        print(f"harvest report: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"report dir: {payload.get('report_dir')}")
        print(f"candidates: {len(payload.get('candidates') or [])}")
        metrics = payload.get("metrics") or {}
        print(f"ready to harvest: {metrics.get('ready_to_harvest_count', 0)}")
        print(f"rejected: {metrics.get('reject_count', 0)}")
        print(f"harvest json: {payload.get('report_json_path')}")
        print(f"harvest report: {payload.get('report_md_path')}")
        return

    if "llm_engineering_report_json_path" in payload:
        print(f"llm engineering report: {'success' if payload.get('success') else 'failed'}")
        print(f"run id: {payload.get('run_id')}")
        print(f"target: {payload.get('target')}")
        metrics = payload.get("metrics", {})
        if isinstance(metrics, dict):
            providers = metrics.get("providers", [])
            print(f"prompt traces: {metrics.get('prompt_traces_count')}")
            print(f"providers: {', '.join(providers) if isinstance(providers, list) else ''}")
            print(f"retry attempts: {metrics.get('retry_attempts_total')}")
            print(f"fallback detected: {metrics.get('fallback_detected')}")
        print(f"llm engineering json: {payload.get('llm_engineering_report_json_path')}")
        print(f"llm engineering report: {payload.get('llm_engineering_report_md_path')}")
        return

    if "domains" in payload and "domains_count" in payload:
        print("domain specs:")
        for domain in payload.get("domains", []):
            print(f"- {domain.get('domain_id')} `{domain.get('status')}`: {domain.get('spec_type')} - {domain.get('summary')}")
        print(f"stable: {payload.get('stable_count')}, planned: {payload.get('planned_count')}")
        return

    if "results" in payload:
        print("example results:")
        for result in payload["results"]:
            print(f"- {result['example']}: {'ok' if result['succeeded'] else 'failed'}")
        return

    if "agent_run_json_path" in payload:
        print(f"agent run: {'success' if payload.get('success') else 'failed'}")
        if payload.get("workspace"):
            print(f"workspace: {payload['workspace']}")
        if payload.get("agent_run_json_path"):
            print(f"agent run json: {payload['agent_run_json_path']}")
        if payload.get("agent_run_md_path"):
            print(f"agent run report: {payload['agent_run_md_path']}")
        if payload.get("agent_decisions_md_path"):
            print(f"agent decisions: {payload['agent_decisions_md_path']}")
        if payload.get("prompt_trace_json_path"):
            print(f"prompt trace: {payload['prompt_trace_json_path']}")
        if payload.get("agent_trace_summary_json_path"):
            print(f"agent trace summary: {payload['agent_trace_summary_json_path']}")
        print("steps:")
        for step in payload.get("steps", []):
            print(f"- {step['role']}: {step['status']} ({step['summary']})")
        return

    if "audit_report_path" in payload:
        print(f"workspace: {payload['workspace']}")
        print(f"audit report: {payload['audit_report_path']}")
        print(f"errors: {payload['errors_count']}")
        print(f"warnings: {payload['warnings_count']}")
        print(f"checks: {payload['checks_count']}")
        return

    if "replay_report_json_path" in payload:
        print(f"agent replay: {'success' if payload.get('success') else 'failed'}")
        print(f"source: {payload.get('source_path')}")
        print(f"workspace: {payload.get('workspace')}")
        print(f"mode: {payload.get('mode')}")
        print(f"events: {payload.get('events_count')}")
        print(f"replay json: {payload.get('replay_report_json_path')}")
        print(f"replay report: {payload.get('replay_report_md_path')}")
        print(f"trace viewer: {payload.get('replay_report_html_path')}")
        return

    if "modify_summary_path" in payload and "modspec_path" in payload:
        print(f"workspace: {payload['workspace']}")
        print(f"modspec: {payload['modspec_path']}")
        print(f"modify summary: {payload['modify_summary_path']}")
        if payload.get("added"):
            print(f"added: {', '.join(payload['added'])}")
        if payload.get("updated"):
            print(f"updated: {', '.join(payload['updated'])}")
        if payload.get("skipped"):
            print(f"skipped: {', '.join(payload['skipped'])}")
        build = payload.get("build")
        if build and build.get("attempted"):
            print("")
            print(f"build: {'success' if build.get('success') else 'failed'}")
            print(f"build summary: {build.get('summary')}")
        if payload.get("audit_requested"):
            print("")
            print(f"audit: {'success' if payload.get('audit_success') else 'failed'}")
            print(f"audit report: {payload.get('audit_report_path')}")
        return

    if "fix_request_path" in payload and "debug_context_path" in payload:
        print(f"workspace: {payload['workspace_dir']}")
        print(f"debug context: {payload['debug_context_path']}")
        print(f"fix request: {payload['fix_request_path']}")
        print(f"suspected errors: {payload['suspected_errors_path']}")
        issues = payload.get("issues", [])
        if issues:
            print("")
            print("issues:")
            for issue in issues:
                location = ""
                if issue.get("file"):
                    location = f" ({issue['file']}:{issue.get('line') or 1})"
                print(f"- {issue['kind']}: {issue['message']}{location}")
        return

    if "error" in payload:
        print(payload["error"])
        return

    if "spec" in payload:
        spec = payload["spec"]
        print(f"mod_id: {spec['mod_id']}")
        print(f"display_name: {spec['display_name']}")
        print(f"package_name: {spec['package_name']}")
        print(f"version: {spec['version']}")
        if spec.get("requested_features"):
            print(f"features: {', '.join(spec['requested_features'])}")
        if payload.get("planner_mode"):
            print(f"planner: {payload['planner_mode']}")

    planner_warnings = payload.get("planner_warnings") or []
    if planner_warnings:
        print("")
        print("planner warnings:")
        for warning in planner_warnings:
            print(f"- {warning}")

    validation = payload.get("validation")
    if validation:
        issues = validation["issues"]
        if issues:
            print("")
            print("validation:")
            for issue in issues:
                print(f"- {issue['severity']}: {issue['message']}")
        else:
            print("")
            print("validation: no issues")

    steps = payload.get("steps")
    if steps:
        print("")
        print("steps:")
        for step in steps:
            suffix = f" ({step['detail']})" if step.get("detail") else ""
            print(f"- {step['status']}: {step['name']}{suffix}")

    workspace_dir = payload.get("workspace_dir")
    if workspace_dir:
        print("")
        print(f"workspace: {workspace_dir}")
        if payload.get("audit_requested"):
            print(f"audit: {'success' if payload.get('audit_success') else 'failed'}")
            if payload.get("audit_report_path"):
                print(f"audit report: {payload.get('audit_report_path')}")

    build = payload.get("build")
    if build and build.get("attempted"):
        print("")
        print(f"build: {'success' if build.get('success') else 'failed'}")
        print(f"build summary: {build.get('summary')}")
        if build.get("jar_path"):
            print(f"jar: {build['jar_path']}")
        if build.get("log_path"):
            print(f"build log: {build['log_path']}")
        if build.get("stdout_path"):
            print(f"stdout log: {build['stdout_path']}")
        if build.get("stderr_path"):
            print(f"stderr log: {build['stderr_path']}")
        if build.get("debug_context_path"):
            print(f"debug context: {build['debug_context_path']}")
        if build.get("fix_request_path"):
            print(f"fix request: {build['fix_request_path']}")
        if build.get("suspected_errors_path"):
            print(f"suspected errors: {build['suspected_errors_path']}")

    warnings = payload.get("warnings") or []
    if warnings:
        print("")
        print("warnings:")
        for warning in warnings:
            print(f"- {warning}")

    pending_actions = payload.get("pending_actions") or []
    if pending_actions:
        print("")
        print("pending actions:")
        for action in pending_actions:
            print(f"- {action}")


def _resolve_project_dir(value: str, config: AppConfig) -> Path:
    raw_path = Path(value)
    if raw_path.exists():
        return raw_path.resolve()

    workspace_path = config.workspace_root / value
    if workspace_path.exists():
        return workspace_path.resolve()

    return raw_path.resolve()


def _append_audit_payload_if_requested(payload: dict, *, workspace: Path, run_audit: bool, config: AppConfig) -> dict:
    payload["audit_requested"] = run_audit
    if not run_audit:
        return payload

    try:
        result = WorkspaceAuditor(config).audit_workspace(workspace)
    except FileNotFoundError as exc:
        payload["audit_success"] = False
        payload["audit_error"] = str(exc)
        return payload

    payload["audit_success"] = result.success
    payload["audit_report_path"] = result.audit_report_path
    payload["audit_errors_count"] = len(result.errors)
    payload["audit_warnings_count"] = len(result.warnings)
    payload["audit_checks_count"] = len(result.checks)
    payload["audit_errors"] = [issue.to_dict() for issue in result.errors]
    payload["audit_warnings"] = [issue.to_dict() for issue in result.warnings]
    if "success" in payload:
        payload["success"] = bool(payload["success"]) and result.success
    if "succeeded" in payload:
        payload["succeeded"] = bool(payload["succeeded"]) and result.success
    return payload


def _payload_exit_code(payload: dict, primary_success: bool) -> int:
    if not primary_success:
        return 1
    if payload.get("audit_requested") and payload.get("audit_success") is False:
        return 1
    return 0
