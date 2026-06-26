from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from .agent_models import AgentRunResult
from .agentic_rag import citation_coverage
from .agent_orchestrator import AgentOrchestrator
from .config import AppConfig
from .evaluator import BenchmarkEvaluator, EvalRunResult
from .llm_client import get_llm_provider_metadata, inspect_llm_provider_config
from .manual_runtime_evidence import (
    ManualRuntimeEvidenceCase as BenchmarkRuntimeCase,
    summarize_manual_runtime_evidence,
    load_manual_runtime_evidence_cases,
)
from .models import ModSpec
from .repair_loop import AutoRepairRunner
from .repair_eval import RepairEvalResult, RepairEvalRunner
from .tools import ensure_directory, write_json, write_text


BENCHMARK_EVIDENCE_SCOPE = (
    "Benchmark success is workspace-level evidence from planner/generator traces, reviewer output, "
    "structured patch results, audit reports, and optional Gradle build results. It is not Minecraft "
    "client/server runtime acceptance unless explicit manual runtime evidence is listed."
)


@dataclass(slots=True)
class BenchmarkModelRun:
    label: str
    provider: str
    model: str
    status: str
    provider_kind: str
    eval_report_path: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    provider_config: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "provider_kind": self.provider_kind,
            "eval_report_path": self.eval_report_path,
            "metrics": dict(self.metrics),
            "provider_config": dict(self.provider_config),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class BenchmarkFailureType:
    identifier: str
    title: str
    success: bool
    audit_detected: bool
    repair_loop_repaired: bool
    audit_recovered: bool
    repair_rag_hits_count: int
    initial_audit_errors_count: int
    capabilities: list[str] = field(default_factory=list)
    workspace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "title": self.title,
            "success": self.success,
            "audit_detected": self.audit_detected,
            "repair_loop_repaired": self.repair_loop_repaired,
            "audit_recovered": self.audit_recovered,
            "repair_rag_hits_count": self.repair_rag_hits_count,
            "initial_audit_errors_count": self.initial_audit_errors_count,
            "capabilities": list(self.capabilities),
            "workspace": self.workspace,
        }


@dataclass(slots=True)
class BenchmarkPageResult:
    success: bool
    run_id: str
    report_dir: Path
    model_runs: list[BenchmarkModelRun]
    failure_types: list[BenchmarkFailureType]
    runtime_cases: list[BenchmarkRuntimeCase]
    repair_eval_report_path: str | None
    metrics: dict[str, Any]
    benchmark_report_json_path: Path
    benchmark_report_md_path: Path
    benchmark_report_html_path: Path
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "model_runs": [run.to_dict() for run in self.model_runs],
            "failure_types": [failure.to_dict() for failure in self.failure_types],
            "runtime_cases": [case.to_dict() for case in self.runtime_cases],
            "repair_eval_report_path": self.repair_eval_report_path,
            "metrics": dict(self.metrics),
            "benchmark_report_json_path": str(self.benchmark_report_json_path),
            "benchmark_report_md_path": str(self.benchmark_report_md_path),
            "benchmark_report_html_path": str(self.benchmark_report_html_path),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "warnings_count": len(self.warnings),
            "errors_count": len(self.errors),
        }


@dataclass(slots=True)
class AgentBenchmarkCaseSpec:
    identifier: str
    mode: str
    request: str
    setup_request: str = ""
    breakage: str = ""
    max_iterations: int = 5
    rag_mode: str | None = None
    category: str = ""
    expected_issue_prefixes: list[str] = field(default_factory=list)
    expected_repair_strategy: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentBenchmarkCaseSpec":
        return cls(
            identifier=str(payload.get("id") or payload.get("identifier") or "agent_case"),
            mode=str(payload.get("mode") or "develop"),
            request=str(payload.get("request") or payload.get("goal") or "Create a ruby mod with ruby."),
            setup_request=str(payload.get("setup_request") or ""),
            breakage=str(payload.get("breakage") or ""),
            max_iterations=max(1, int(payload.get("max_iterations") or 5)),
            rag_mode=str(payload.get("rag_mode")) if payload.get("rag_mode") is not None else None,
            category=str(payload.get("category") or ""),
            expected_issue_prefixes=_string_list(payload.get("expected_issue_prefixes")),
            expected_repair_strategy=str(payload.get("expected_repair_strategy") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "mode": self.mode,
            "request": self.request,
            "setup_request": self.setup_request,
            "breakage": self.breakage,
            "max_iterations": self.max_iterations,
            "rag_mode": self.rag_mode,
            "category": self.category,
            "expected_issue_prefixes": list(self.expected_issue_prefixes),
            "expected_repair_strategy": self.expected_repair_strategy,
        }


@dataclass(slots=True)
class AgentBenchmarkCaseResult:
    identifier: str
    mode: str
    request: str
    success: bool
    workspace: str | None
    breakage: str = ""
    category: str = ""
    injected_paths: list[str] = field(default_factory=list)
    initial_audit_issue_ids: list[str] = field(default_factory=list)
    detected_expected_failure: bool | None = None
    agent_run_json_path: str | None = None
    tool_call_trace_json_path: str | None = None
    reviewer_report_json_path: str | None = None
    prompt_trace_json_path: str | None = None
    managed_regen_success: bool | None = None
    managed_regen_report_json_path: str | None = None
    build_attempted: bool = False
    build_success: bool | None = None
    audit_attempted: bool = False
    audit_success: bool | None = None
    repair_success: bool | None = None
    tool_calls_count: int = 0
    iterations: int = 0
    rag_hits_count: int = 0
    patch_attempts_count: int = 0
    patch_accepted_count: int = 0
    rollback_count: int = 0
    rollback_evidence_paths: list[str] = field(default_factory=list)
    reviewer_decision: str = ""
    reviewer_coverage_status: str = ""
    rag_mode: str = "auto"
    rag_decision_trace_json_path: str | None = None
    rag_decisions_count: int = 0
    rag_citations_count: int = 0
    rag_citation_coverage: float = 0.0
    trace_paths: list[str] = field(default_factory=list)
    failure_kind: str = ""
    provider_status_code: int | None = None
    provider_error_summary: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "mode": self.mode,
            "request": self.request,
            "success": self.success,
            "workspace": self.workspace,
            "breakage": self.breakage,
            "category": self.category,
            "injected_paths": list(self.injected_paths),
            "initial_audit_issue_ids": list(self.initial_audit_issue_ids),
            "detected_expected_failure": self.detected_expected_failure,
            "agent_run_json_path": self.agent_run_json_path,
            "tool_call_trace_json_path": self.tool_call_trace_json_path,
            "reviewer_report_json_path": self.reviewer_report_json_path,
            "prompt_trace_json_path": self.prompt_trace_json_path,
            "managed_regen_success": self.managed_regen_success,
            "managed_regen_report_json_path": self.managed_regen_report_json_path,
            "build_attempted": self.build_attempted,
            "build_success": self.build_success,
            "audit_attempted": self.audit_attempted,
            "audit_success": self.audit_success,
            "repair_success": self.repair_success,
            "tool_calls_count": self.tool_calls_count,
            "iterations": self.iterations,
            "rag_hits_count": self.rag_hits_count,
            "patch_attempts_count": self.patch_attempts_count,
            "patch_accepted_count": self.patch_accepted_count,
            "rollback_count": self.rollback_count,
            "rollback_evidence_paths": list(self.rollback_evidence_paths),
            "reviewer_decision": self.reviewer_decision,
            "reviewer_coverage_status": self.reviewer_coverage_status,
            "rag_mode": self.rag_mode,
            "rag_decision_trace_json_path": self.rag_decision_trace_json_path,
            "rag_decisions_count": self.rag_decisions_count,
            "rag_citations_count": self.rag_citations_count,
            "rag_citation_coverage": self.rag_citation_coverage,
            "trace_paths": list(self.trace_paths),
            "failure_kind": self.failure_kind,
            "provider_status_code": self.provider_status_code,
            "provider_error_summary": self.provider_error_summary,
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class AgentBenchmarkResult:
    success: bool
    run_id: str
    report_dir: Path
    cases: list[AgentBenchmarkCaseResult]
    metrics: dict[str, Any]
    benchmark_report_json_path: Path
    benchmark_report_md_path: Path
    benchmark_report_html_path: Path
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "success": self.success,
            "benchmark_kind": "agent",
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "cases": [case.to_dict() for case in self.cases],
            "cases_count": len(self.cases),
            "metrics": dict(self.metrics),
            "benchmark_report_json_path": str(self.benchmark_report_json_path),
            "benchmark_report_md_path": str(self.benchmark_report_md_path),
            "benchmark_report_html_path": str(self.benchmark_report_html_path),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "warnings_count": len(self.warnings),
            "errors_count": len(self.errors),
        }
        payload.update(self.metrics)
        payload["agent_bench_metrics"] = dict(self.metrics)
        return payload


@dataclass(slots=True)
class AgentBenchmarkBreakageInjection:
    breakage: str
    injected_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "breakage": self.breakage,
            "injected_paths": list(self.injected_paths),
        }


@dataclass(frozen=True, slots=True)
class AgentBenchmarkHoldoutTemplate:
    identifier: str
    breakage: str
    category: str
    setup_kind: str
    expected_issue_prefixes: tuple[str, ...]
    expected_repair_strategy: str


_HOLDOUT_MATERIALS: tuple[tuple[str, str], ...] = (
    ("sapphire", "Sapphire"),
    ("cobalt", "Cobalt"),
    ("amber", "Amber"),
    ("topaz", "Topaz"),
    ("opal", "Opal"),
    ("garnet", "Garnet"),
    ("silver", "Silver"),
    ("mythril", "Mythril"),
    ("onyx", "Onyx"),
    ("jade", "Jade"),
    ("crystal", "Crystal"),
    ("moonstone", "Moonstone"),
)


def generate_agent_benchmark_holdout_cases(*, seed: str | int = "default", limit: int = 8) -> list[AgentBenchmarkCaseSpec]:
    """Generate deterministic randomized repair benchmark cases for holdout checks."""

    templates = list(_agent_benchmark_holdout_templates())
    count = max(0, min(int(limit), len(templates)))
    rng = random.Random(str(seed))
    rng.shuffle(templates)
    selected = templates[:count]
    materials = list(_HOLDOUT_MATERIALS)
    rng.shuffle(materials)
    seed_slug = _agent_benchmark_slug(str(seed), fallback="seed")
    cases: list[AgentBenchmarkCaseSpec] = []
    for index, template in enumerate(selected, start=1):
        material_id, material_name = materials[(index - 1) % len(materials)]
        cases.append(
            AgentBenchmarkCaseSpec(
                identifier=f"holdout_{seed_slug}_{index:02d}_{material_id}_{template.identifier}",
                mode="repair",
                request=(
                    f"Repair randomized holdout failure `{template.breakage}` in the generated "
                    f"{material_name} mod, then rerun audit."
                ),
                setup_request=_agent_benchmark_holdout_setup_request(
                    setup_kind=template.setup_kind,
                    material_id=material_id,
                    material_name=material_name,
                ),
                breakage=template.breakage,
                max_iterations=7,
                rag_mode="auto",
                category=template.category,
                expected_issue_prefixes=list(template.expected_issue_prefixes),
                expected_repair_strategy=template.expected_repair_strategy,
            )
        )
    return cases


def _agent_benchmark_holdout_templates() -> tuple[AgentBenchmarkHoldoutTemplate, ...]:
    return (
        AgentBenchmarkHoldoutTemplate("delete_mods_toml", "delete_mods_toml", "metadata", "item", ("project:mods_toml",), "structured_patch"),
        AgentBenchmarkHoldoutTemplate("break_pack_mcmeta_format", "break_pack_mcmeta_format", "metadata", "item", ("project:pack_mcmeta:pack_format",), "structured_patch"),
        AgentBenchmarkHoldoutTemplate("corrupt_pack_mcmeta_json", "corrupt_pack_mcmeta_json", "metadata", "item", ("project:pack_mcmeta:json",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("delete_item_definition", "delete_item_definition", "asset_resource", "item", ("item:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("delete_item_model", "delete_item_model", "asset_resource", "item", ("item:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("corrupt_item_texture_png", "corrupt_item_texture_png", "asset_resource", "item", ("item:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("delete_blockstate", "delete_blockstate", "asset_resource", "block", ("block:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("delete_block_loot_table", "delete_block_loot_table", "asset_resource", "block", ("block:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("remove_lang_entry", "remove_lang_entry", "asset_resource", "item", ("item:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("delete_recipe_file", "delete_recipe_file", "data_worldgen", "recipe", ("recipe:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("corrupt_recipe_json", "corrupt_recipe_json", "data_worldgen", "recipe", ("recipe:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("break_recipe_reference", "break_recipe_reference", "data_worldgen", "recipe", ("recipe:",), "structured_patch"),
        AgentBenchmarkHoldoutTemplate("delete_ore_configured_feature", "delete_ore_configured_feature", "data_worldgen", "ore", ("ore:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("break_ore_rule_test", "break_ore_rule_test", "data_worldgen", "ore", ("ore:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("delete_ore_biome_modifier", "delete_ore_biome_modifier", "data_worldgen", "ore", ("ore:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("delete_behavior_item_java", "delete_behavior_item_java", "generated_code", "behavior_item", ("item:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("delete_machine_block_entity_java", "delete_machine_block_entity_java", "generated_code", "machine", ("machine:",), "regenerate_managed_files"),
        AgentBenchmarkHoldoutTemplate("delete_entity_spawn_modifier", "delete_entity_spawn_modifier", "generated_code", "entity", ("entity:",), "regenerate_managed_files"),
    )


def _agent_benchmark_holdout_setup_request(*, setup_kind: str, material_id: str, material_name: str) -> str:
    mod_id = f"{material_id}_holdout"
    feature_notes = {
        "item": f"Include item {material_id}.",
        "block": f"Include item {material_id} and block {material_id}_block.",
        "recipe": f"Include item {material_id}, block {material_id}_block, sword {material_id}_sword, and recipes.",
        "ore": (
            f"Include item {material_id} and ore {material_id}_ore that drops {material_id} "
            "and generates in the overworld underground with Y -64 to 32, vein size 6, count 4."
        ),
        "behavior_item": f"Include behavior item {material_id}_charm with right click heal 4 health and cooldown 20 seconds.",
        "machine": f"Include item {material_id} and machine {material_id}_compressor with machine cost and energy cost.",
        "entity": f"Include item {material_id}_scale and entity {material_id}_sentinel with melee attack, drops, and overworld spawn.",
    }
    note = feature_notes.get(setup_kind, feature_notes["item"])
    return (
        f"Create a {material_name} randomized holdout NeoForge mod. "
        f"mod id: {mod_id}. package: com.generated.{mod_id}. "
        f"Holdout material: {material_id}. Holdout features: {setup_kind}. {note}"
    )


def _agent_benchmark_slug(value: str, *, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    return (slug or fallback)[:40]


class AgentBenchmarkRunner:
    """Run real agent develop/repair loops and aggregate trace-backed metrics."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        cases_path: Path | None = None,
        eval_limit: int | None = 3,
        repair_limit: int | None = 3,
        llm_provider: str = "mock",
        run_build: bool = False,
        run_audit: bool = True,
        rag_mode: str = "auto",
        rag_ablation: bool = False,
        run_real: bool = False,
        require_real: bool = False,
        repair_holdout: bool = False,
        holdout_seed: str | int = "default",
        holdout_limit: int = 8,
    ) -> AgentBenchmarkResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        root_dir = ensure_directory(self.config.workspace_root / "benchmark-runs" / run_id)
        report_dir = ensure_directory(root_dir / ".agent")
        warnings: list[str] = []
        errors: list[str] = []

        if llm_provider != "mock":
            provider_config = inspect_llm_provider_config(llm_provider).to_dict()
            if not provider_config.get("valid"):
                message = (
                    f"Agent benchmark provider `{llm_provider}` is not configured; "
                    "set NEOFORGE_AGENT_LLM_API_KEY/OPENAI_API_KEY and model before running real acceptance."
                )
                if require_real:
                    errors.append(message)
                else:
                    warnings.append(message)
                return self._write_agent_result(
                    success=not errors,
                    run_id=run_id,
                    report_dir=report_dir,
                    cases=[],
                    warnings=warnings,
                    errors=errors,
                )
            if not run_real and not require_real:
                warnings.append(
                    f"Agent benchmark provider `{llm_provider}` was preflighted but not executed; "
                    "pass --run-real or --require-real to run real provider cases."
                )
                return self._write_agent_result(
                    success=True,
                    run_id=run_id,
                    report_dir=report_dir,
                    cases=[],
                    warnings=warnings,
                    errors=[],
                )

        scoped_config = replace(self.config, workspace_root=ensure_directory(root_dir / "runs"))
        orchestrator = AgentOrchestrator(scoped_config)
        repair_runner = AutoRepairRunner(scoped_config)
        metrics_extra: dict[str, Any] = {}
        if repair_holdout:
            if cases_path is not None:
                errors.append("--repair-holdout cannot be combined with --suite.")
                return self._write_agent_result(
                    success=False,
                    run_id=run_id,
                    report_dir=report_dir,
                    cases=[],
                    warnings=warnings,
                    errors=errors,
                )
            cases = generate_agent_benchmark_holdout_cases(seed=holdout_seed, limit=holdout_limit)
            metrics_extra.update(
                {
                    "repair_holdout": True,
                    "holdout_seed": str(holdout_seed),
                    "holdout_limit": len(cases),
                }
            )
            warnings.append(f"Generated randomized repair holdout suite with seed `{holdout_seed}` and {len(cases)} case(s).")
        else:
            cases = self._load_cases(cases_path, eval_limit=eval_limit, repair_limit=repair_limit)
        if rag_ablation:
            cases = _paired_rag_ablation_cases(cases)

        results: list[AgentBenchmarkCaseResult] = []
        for index, case in enumerate(cases, start=1):
            workspace_name = f"{index:02d}-{case.identifier}"
            try:
                results.append(
                    self._run_case(
                        case,
                        workspace_name=workspace_name,
                        orchestrator=orchestrator,
                        repair_runner=repair_runner,
                        llm_provider=llm_provider,
                        run_build=run_build,
                        run_audit=run_audit,
                        rag_mode=case.rag_mode or rag_mode,
                    )
                )
            except Exception as exc:  # Keep benchmark evidence complete across failing cases.
                results.append(
                    AgentBenchmarkCaseResult(
                        identifier=case.identifier,
                        mode=case.mode,
                        request=case.request,
                        success=False,
                        workspace=None,
                        rag_mode=case.rag_mode or rag_mode,
                        errors=[f"{type(exc).__name__}: {exc}"],
                    )
                )

        if not cases:
            warnings.append("No agent benchmark cases were selected.")
        success = _agent_benchmark_success(results, rag_ablation=rag_ablation)
        return self._write_agent_result(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            cases=results,
            warnings=warnings,
            errors=errors,
            metrics_extra=metrics_extra,
        )

    def _write_agent_result(
        self,
        *,
        success: bool,
        run_id: str,
        report_dir: Path,
        cases: list[AgentBenchmarkCaseResult],
        warnings: list[str],
        errors: list[str],
        metrics_extra: dict[str, Any] | None = None,
    ) -> AgentBenchmarkResult:
        metrics = agent_benchmark_metrics(cases)
        if metrics_extra:
            metrics.update(metrics_extra)
        result = AgentBenchmarkResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            cases=cases,
            metrics=metrics,
            benchmark_report_json_path=report_dir / "agent-benchmark-report.json",
            benchmark_report_md_path=report_dir / "agent-benchmark-report.md",
            benchmark_report_html_path=report_dir / "agent-benchmark-report.html",
            warnings=warnings,
            errors=errors,
        )
        write_json(result.benchmark_report_json_path, result.to_dict())
        write_text(result.benchmark_report_md_path, self._render_markdown(result))
        write_text(result.benchmark_report_html_path, self._render_html(result))
        return result

    def _load_cases(
        self,
        cases_path: Path | None,
        *,
        eval_limit: int | None,
        repair_limit: int | None,
    ) -> list[AgentBenchmarkCaseSpec]:
        if cases_path is not None:
            data = json.loads(cases_path.read_text(encoding="utf-8"))
            raw_cases = data.get("cases", data) if isinstance(data, dict) else data
            if not isinstance(raw_cases, list):
                raise ValueError("Agent benchmark suite must be a JSON list or an object with a cases list.")
            return [AgentBenchmarkCaseSpec.from_dict(item) for item in raw_cases if isinstance(item, dict)]

        develop_cases = [
            AgentBenchmarkCaseSpec(
                identifier="develop_ruby_tech_refine",
                mode="develop",
                request="Create a ruby tech mod with ruby ore and recipes.",
                max_iterations=5,
            ),
            AgentBenchmarkCaseSpec(
                identifier="develop_reviewer_followup",
                mode="develop",
                request="Create a ruby tech mod with ruby ore and recipes; reviewer needs repair.",
                max_iterations=6,
            ),
        ]
        repair_cases = [
            AgentBenchmarkCaseSpec(
                identifier="repair_mods_toml_structured_patch",
                mode="repair",
                request="Fix audit failures without changing user-owned files.",
                setup_request="Create a ruby mod with ruby.",
                breakage="delete_mods_toml",
                max_iterations=6,
                rag_mode="auto",
                category="metadata",
                expected_issue_prefixes=["project:mods_toml", "summary:"],
                expected_repair_strategy="structured_patch",
            ),
            AgentBenchmarkCaseSpec(
                identifier="repair_pack_mcmeta_agentic_rag",
                mode="repair",
                request="Fix pack.mcmeta audit failures using cited NeoForge metadata rules.",
                setup_request="Create a ruby mod with ruby.",
                breakage="break_pack_mcmeta_format",
                max_iterations=6,
                rag_mode="auto",
                category="metadata",
                expected_issue_prefixes=["project:pack_mcmeta:pack_format"],
                expected_repair_strategy="structured_patch",
            ),
            AgentBenchmarkCaseSpec(
                identifier="repair_recipe_resource_path_agentic_rag",
                mode="repair",
                request="Fix recipe/resource path audit failures with RAG-backed evidence.",
                setup_request="Create a ruby mod with ruby sword recipes.",
                breakage="break_recipe_reference",
                max_iterations=6,
                rag_mode="auto",
                category="data_worldgen",
                expected_issue_prefixes=["recipe:"],
                expected_repair_strategy="structured_patch",
            )
        ]
        return [
            *_limit_cases(develop_cases, eval_limit),
            *_limit_cases(repair_cases, repair_limit),
        ]

    def _run_case(
        self,
        case: AgentBenchmarkCaseSpec,
        *,
        workspace_name: str,
        orchestrator: AgentOrchestrator,
        repair_runner: AutoRepairRunner,
        llm_provider: str,
        run_build: bool,
        run_audit: bool,
        rag_mode: str,
    ) -> AgentBenchmarkCaseResult:
        if case.mode == "develop":
            run = orchestrator.run_develop(
                case.request,
                planner_mode="llm",
                llm_provider=llm_provider,
                workspace_name=workspace_name,
                overwrite=True,
                run_build=run_build,
                run_audit=run_audit,
                repair=True,
                max_iterations=case.max_iterations,
                rag_mode=rag_mode,
            )
            return _agent_benchmark_case_from_run(case, run)

        if case.mode == "repair":
            setup = orchestrator.run_generate(
                case.setup_request or "Create a ruby mod with ruby.",
                planner_mode="llm",
                llm_provider=llm_provider,
                workspace_name=f"{workspace_name}-setup",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
            )
            if setup.workspace is None or not setup.success:
                return _failed_agent_benchmark_case(case, setup, "Repair benchmark setup generation failed.")
            injection = _inject_agent_benchmark_breakage(setup.workspace, case.breakage)
            initial_audit = repair_runner.auditor.audit_workspace(setup.workspace)
            initial_issue_ids = [issue.id for issue in initial_audit.errors]
            detected_expected = _matches_issue_prefixes(initial_issue_ids, case.expected_issue_prefixes)
            if initial_audit.success:
                return AgentBenchmarkCaseResult(
                    identifier=case.identifier,
                    mode=case.mode,
                    request=case.request,
                    success=False,
                    workspace=str(setup.workspace),
                    breakage=case.breakage,
                    category=case.category,
                    injected_paths=list(injection.injected_paths),
                    initial_audit_issue_ids=initial_issue_ids,
                    detected_expected_failure=detected_expected,
                    rag_mode=case.rag_mode or rag_mode,
                    errors=["Breakage injection did not produce an audit failure."],
                )
            regen_probe = repair_runner.run(setup.workspace, max_attempts=1, run_build=run_build, run_audit=run_audit)
            _inject_agent_benchmark_breakage(setup.workspace, case.breakage)
            run = orchestrator.run_repair(
                setup.workspace,
                goal=case.request,
                planner_mode="llm",
                llm_provider=llm_provider,
                max_iterations=case.max_iterations,
                run_build=run_build,
                run_audit=run_audit,
                rag_mode=rag_mode,
            )
            result = _agent_benchmark_case_from_run(
                case,
                run,
                managed_regen_probe=regen_probe.to_dict(),
                injected_paths=injection.injected_paths,
                initial_audit_issue_ids=initial_issue_ids,
                detected_expected_failure=detected_expected,
            )
            if case.expected_issue_prefixes and not detected_expected:
                result.success = False
                result.errors.append(
                    "Initial audit did not match expected issue prefixes: "
                    + ", ".join(case.expected_issue_prefixes)
                )
            return result

        raise ValueError(f"Unsupported agent benchmark mode: {case.mode}")

    def _render_markdown(self, result: AgentBenchmarkResult) -> str:
        lines = [
            "# Agent Benchmark Report",
            "",
            f"Success: `{str(result.success).lower()}`",
            f"Run ID: `{result.run_id}`",
            "",
            "## Evidence Boundary",
            "",
            BENCHMARK_EVIDENCE_SCOPE,
            "",
            "## Metrics",
            "",
        ]
        for key, value in result.metrics.items():
            lines.append(f"- `{key}`: {value}")
        lines.extend(["", "## Cases", ""])
        for case in result.cases:
            lines.extend(
                [
                    f"### {case.identifier}",
                    "",
                    f"- mode: `{case.mode}`",
                    f"- category: `{case.category}`",
                    f"- breakage: `{case.breakage}`",
                    f"- success: `{str(case.success).lower()}`",
                    f"- workspace: `{case.workspace or ''}`",
                    f"- injected paths: `{', '.join(case.injected_paths)}`",
                    f"- initial audit issue ids: `{', '.join(case.initial_audit_issue_ids)}`",
                    f"- detected expected failure: `{case.detected_expected_failure}`",
                    f"- agent run: `{case.agent_run_json_path or ''}`",
                    f"- tool trace: `{case.tool_call_trace_json_path or ''}`",
                    f"- reviewer: `{case.reviewer_report_json_path or ''}`",
                    f"- tool calls: `{case.tool_calls_count}`",
                    f"- iterations: `{case.iterations}`",
                    f"- RAG mode: `{case.rag_mode}`",
                    f"- RAG hits: `{case.rag_hits_count}`",
                    f"- RAG decisions: `{case.rag_decisions_count}`",
                    f"- RAG citations: `{case.rag_citations_count}`",
                    f"- RAG citation coverage: `{case.rag_citation_coverage}`",
                    f"- patch accepted: `{case.patch_accepted_count}/{case.patch_attempts_count}`",
                    f"- rollback evidence: `{case.rollback_count}`",
                    f"- managed regeneration probe: `{case.managed_regen_success}`",
                    "",
                ]
            )
            if case.errors:
                lines.append("Errors:")
                lines.extend(f"- {error}" for error in case.errors)
                lines.append("")
        if result.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in result.warnings)
        lines.append("")
        return "\n".join(lines)

    def _render_html(self, result: AgentBenchmarkResult) -> str:
        rows = []
        for case in result.cases:
            status = "pass" if case.success else "fail"
            rows.append(
                "<tr>"
                f"<td><code>{escape(case.identifier)}</code><br>{escape(case.mode)}<br>{escape(case.category)}<br><code>{escape(case.breakage)}</code></td>"
                f'<td><span class="badge {status}">{status}</span></td>'
                f"<td>{escape(str(case.detected_expected_failure))}<br><code>{escape(', '.join(case.initial_audit_issue_ids[:3]))}</code></td>"
                f"<td>{case.tool_calls_count}</td>"
                f"<td>{case.iterations}</td>"
                f"<td><code>{escape(case.rag_mode)}</code><br>{case.rag_hits_count} hits<br>{case.rag_citations_count} citations</td>"
                f"<td>{case.patch_accepted_count}/{case.patch_attempts_count}</td>"
                f"<td><code>{escape(case.agent_run_json_path or '')}</code></td>"
                "</tr>"
            )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Benchmark Report</title>
  <style>
    body {{ margin: 0; background: #f7f8fa; color: #172033; font: 14px/1.55 "Segoe UI", Arial, sans-serif; }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin-top: 24px; font-size: 18px; letter-spacing: 0; }}
    .metrics {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }}
    .metric, table {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; }}
    .metric {{ padding: 14px; }}
    .metric span {{ display: block; color: #667085; font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 18px; overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: separate; border-spacing: 0; overflow: hidden; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #d8dee8; text-align: left; vertical-align: top; }}
    th {{ color: #667085; background: #fbfcfe; font-size: 12px; text-transform: uppercase; }}
    tr:last-child td {{ border-bottom: 0; }}
    code {{ overflow-wrap: anywhere; }}
    .badge {{ display: inline-flex; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 650; }}
    .pass {{ color: #16803c; background: #ecfdf3; }}
    .fail {{ color: #c2410c; background: #fff1ec; }}
    @media (max-width: 900px) {{ .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
  </style>
</head>
<body>
  <main class="wrap">
    <h1>Agent Benchmark Report</h1>
    <p>Trace-backed workspace benchmark for develop/repair flow, reviewer, RAG, structured patch, audit, and optional build evidence.</p>
    <p>{escape(BENCHMARK_EVIDENCE_SCOPE)}</p>
    <section class="metrics">
      {self._agent_metric_cards(result.metrics)}
    </section>
    <h2>Cases</h2>
    <table>
      <tr><th>Case</th><th>Status</th><th>Initial Detection</th><th>Tool Calls</th><th>Iterations</th><th>RAG Hits</th><th>Patch</th><th>Trace</th></tr>
      {''.join(rows)}
    </table>
  </main>
</body>
</html>
"""

    def _agent_metric_cards(self, metrics: dict[str, Any]) -> str:
        keys = [
            "success_rate",
            "audit_success_rate",
            "repair_success_rate",
            "avg_tool_calls",
            "patch_accept_rate",
            "audit_detection_rate",
            "expected_failure_detection_rate",
            "rollback_count",
            "rag_hit_rate",
            "rag_citation_coverage_rate",
            "rag_success_delta",
            "rag_on_success_rate",
            "rag_off_success_rate",
            "rag_iteration_delta",
            "rag_tool_call_delta",
            "rag_on_expected_detection_rate",
            "failed_cases_count",
            "trace_paths_count",
        ]
        return "\n".join(
            f'<div class="metric"><span>{escape(key)}</span><strong>{escape(_format_value(metrics.get(key)))}</strong></div>'
            for key in keys
        )


class BenchmarkReportRunner:
    """Aggregate model, repair, build, and runtime evidence into one benchmark page."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        cases_path: Path | None = None,
        eval_limit: int | None = 3,
        repair_limit: int | None = 3,
        baseline_provider: str = "mock",
        candidate_provider: str = "openai-compatible",
        run_build: bool = False,
        run_audit: bool = True,
        run_real: bool = False,
        require_real: bool = False,
        runtime_evidence_path: Path | None = None,
    ) -> BenchmarkPageResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        root_dir = ensure_directory(self.config.workspace_root / "benchmark-runs" / run_id)
        report_dir = ensure_directory(root_dir / ".agent")
        scoped_config = replace(self.config, workspace_root=ensure_directory(root_dir / "runs"))

        warnings: list[str] = []
        errors: list[str] = []
        model_runs: list[BenchmarkModelRun] = []

        baseline = self._run_eval(
            "A",
            provider=baseline_provider,
            scoped_config=scoped_config,
            cases_path=cases_path,
            eval_limit=eval_limit,
            run_build=run_build,
            run_audit=run_audit,
            run_id=run_id,
        )
        model_runs.append(baseline)
        errors.extend(baseline.errors)

        candidate_config = inspect_llm_provider_config(candidate_provider).to_dict()
        should_run_candidate = candidate_provider == "mock" or run_real or require_real
        if should_run_candidate and self._can_run_provider(candidate_provider, candidate_config):
            candidate = self._run_eval(
                "B",
                provider=candidate_provider,
                scoped_config=scoped_config,
                cases_path=cases_path,
                eval_limit=eval_limit,
                run_build=run_build,
                run_audit=run_audit,
                run_id=run_id,
            )
            model_runs.append(candidate)
            errors.extend(candidate.errors)
        else:
            if should_run_candidate:
                message = (
                    f"Candidate provider `{candidate_provider}` is not configured; "
                    "benchmark page records it as skipped without calling the network."
                )
            else:
                message = (
                    f"Candidate provider `{candidate_provider}` was preflighted but not executed; "
                    "pass --run-real or --require-real to include real provider calls."
                )
            if require_real:
                errors.append(message)
            else:
                warnings.append(message)
            model_runs.append(
                BenchmarkModelRun(
                    label="B",
                    provider=candidate_provider,
                    model=str(candidate_config.get("model", "")),
                    status="skip",
                    provider_kind=_provider_kind(candidate_provider),
                    provider_config=candidate_config,
                    warnings=[message],
                )
            )

        repair_eval = RepairEvalRunner(scoped_config).run(
            run_name=f"{run_id}-repair",
            limit=repair_limit,
            run_build=run_build,
        )
        failure_types = [_failure_from_repair_case(case) for case in repair_eval.cases]
        if not repair_eval.success:
            warnings.append("Repair eval did not reach full success for every selected failure type.")

        runtime_cases = self._load_runtime_cases(runtime_evidence_path)
        metrics = self._metrics(model_runs, failure_types, runtime_cases)
        success = not errors and bool(model_runs) and baseline.status == "pass" and repair_eval.success

        result = BenchmarkPageResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            model_runs=model_runs,
            failure_types=failure_types,
            runtime_cases=runtime_cases,
            repair_eval_report_path=str(repair_eval.repair_eval_report_json_path),
            metrics=metrics,
            benchmark_report_json_path=report_dir / "benchmark-report.json",
            benchmark_report_md_path=report_dir / "benchmark-report.md",
            benchmark_report_html_path=report_dir / "benchmark-report.html",
            warnings=warnings,
            errors=errors,
        )
        write_json(result.benchmark_report_json_path, result.to_dict())
        write_text(result.benchmark_report_md_path, self._render_markdown(result))
        write_text(result.benchmark_report_html_path, self._render_html(result))
        return result

    def _run_eval(
        self,
        label: str,
        *,
        provider: str,
        scoped_config: AppConfig,
        cases_path: Path | None,
        eval_limit: int | None,
        run_build: bool,
        run_audit: bool,
        run_id: str,
    ) -> BenchmarkModelRun:
        provider_config = inspect_llm_provider_config(provider).to_dict()
        metadata = get_llm_provider_metadata(provider).to_dict()
        model = str(metadata.get("model") or provider_config.get("model") or provider)
        try:
            eval_result = BenchmarkEvaluator(scoped_config).run(
                cases_path=cases_path,
                planner_mode="llm",
                llm_provider=provider,
                run_build=run_build,
                run_audit=run_audit,
                run_name=f"{run_id}-model-{label.lower()}-{provider}",
                limit=eval_limit,
            )
        except Exception as exc:  # keep the aggregate report alive
            return BenchmarkModelRun(
                label=label,
                provider=provider,
                model=model,
                status="fail",
                provider_kind=_provider_kind(provider),
                provider_config=provider_config,
                errors=[f"{type(exc).__name__}: {exc}"],
            )
        return BenchmarkModelRun(
            label=label,
            provider=provider,
            model=model,
            status="pass" if eval_result.success else "fail",
            provider_kind=_provider_kind(provider),
            eval_report_path=str(eval_result.eval_report_json_path),
            metrics=dict(eval_result.metrics),
            provider_config=provider_config,
        )

    def _can_run_provider(self, provider: str, provider_config: dict[str, Any]) -> bool:
        if provider == "mock":
            return True
        return bool(provider_config.get("valid"))

    def _load_runtime_cases(self, runtime_evidence_path: Path | None) -> list[BenchmarkRuntimeCase]:
        if runtime_evidence_path is None:
            return []
        if not runtime_evidence_path.exists():
            return []
        return load_manual_runtime_evidence_cases(runtime_evidence_path)

    def _metrics(
        self,
        model_runs: list[BenchmarkModelRun],
        failure_types: list[BenchmarkFailureType],
        runtime_cases: list[BenchmarkRuntimeCase],
    ) -> dict[str, Any]:
        completed_model_runs = [run for run in model_runs if run.status in {"pass", "fail"}]
        build_attempted = sum(int(run.metrics.get("build_attempted_count", 0) or 0) for run in completed_model_runs)
        build_success = sum(int(run.metrics.get("build_success_count", 0) or 0) for run in completed_model_runs)
        repair_total = len(failure_types)
        repair_success = sum(1 for failure in failure_types if failure.success)
        runtime_summary = summarize_manual_runtime_evidence(runtime_cases).to_dict()
        return {
            "model_runs_total": len(model_runs),
            "model_runs_completed": len(completed_model_runs),
            "model_runs_skipped": sum(1 for run in model_runs if run.status == "skip"),
            "mock_runs": sum(1 for run in model_runs if run.provider_kind == "mock"),
            "real_runs": sum(1 for run in model_runs if run.provider_kind == "real"),
            "best_success_rate": max((float(run.metrics.get("success_rate", 0) or 0) for run in completed_model_runs), default=0.0),
            "build_attempted_count": build_attempted,
            "build_success_count": build_success,
            "build_pass_rate": _rate(build_success, build_attempted) if build_attempted else None,
            "failure_types_total": repair_total,
            "failure_types_repaired": repair_success,
            "repair_rate": _rate(repair_success, repair_total),
            "audit_detection_rate": _rate(sum(1 for failure in failure_types if failure.audit_detected), repair_total),
            "manual_runtime_evidence_schema": runtime_summary["schema_version"],
            "manual_runtime_evidence_kind": runtime_summary["evidence_kind"],
            "runtime_cases_total": runtime_summary["runtime_cases_total"],
            "runtime_passed_count": runtime_summary["runtime_passed_count"],
            "runtime_pass_rate": runtime_summary["runtime_pass_rate"],
            "evidence_scope": BENCHMARK_EVIDENCE_SCOPE,
        }

    def _render_markdown(self, result: BenchmarkPageResult) -> str:
        lines = [
            "# Benchmark Report",
            "",
            f"Success: `{str(result.success).lower()}`",
            f"Run ID: `{result.run_id}`",
            f"HTML: `{result.benchmark_report_html_path}`",
            "",
            "## Evidence Boundary",
            "",
            BENCHMARK_EVIDENCE_SCOPE,
            "",
            "## Metrics",
            "",
        ]
        for key, value in result.metrics.items():
            lines.append(f"- `{key}`: {value}")
        lines.extend(["", "## Model A/B", ""])
        for run in result.model_runs:
            lines.append(
                f"- `{run.label}` `{run.provider}` `{run.model}` `{run.status}`: "
                f"success_rate={run.metrics.get('success_rate')}, "
                f"audit={run.metrics.get('audit_success_rate')}, "
                f"build={run.metrics.get('build_success_rate')}"
            )
        lines.extend(["", "## Failure Types", ""])
        for failure in result.failure_types:
            lines.append(
                f"- `{failure.identifier}`: repair={str(failure.success).lower()}, "
                f"audit_detected={str(failure.audit_detected).lower()}, "
                f"recovered={str(failure.audit_recovered).lower()}"
            )
        lines.extend(["", "## Manual Runtime Evidence", ""])
        if not result.runtime_cases:
            lines.append("- No manual Minecraft runtime evidence was included in this report.")
        for case in result.runtime_cases:
            lines.append(f"- `{case.identifier}` `{case.status}`: `{case.workspace}`")
        if result.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in result.warnings)
        if result.errors:
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- {error}" for error in result.errors)
        lines.append("")
        return "\n".join(lines)

    def _render_html(self, result: BenchmarkPageResult) -> str:
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Benchmark Report</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #172033;
      --muted: #667085;
      --line: #d8dee8;
      --blue: #2563eb;
      --green: #16803c;
      --amber: #a16207;
      --red: #c2410c;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.55 "Segoe UI", "Microsoft YaHei", Arial, sans-serif; }}
    header {{ background: var(--panel); border-bottom: 1px solid var(--line); }}
    .wrap {{ max-width: 1220px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; letter-spacing: 0; }}
    p {{ margin: 0; color: var(--muted); }}
    .grid {{ display: grid; gap: 12px; }}
    .metrics {{ grid-template-columns: repeat(6, minmax(0, 1fr)); margin: 18px 0; }}
    .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .card, .metric, table {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
    .card, .metric {{ padding: 14px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 18px; overflow-wrap: anywhere; }}
    section {{ margin-top: 22px; }}
    table {{ width: 100%; border-collapse: separate; border-spacing: 0; overflow: hidden; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; background: #fbfcfe; }}
    tr:last-child td {{ border-bottom: 0; }}
    code {{ overflow-wrap: anywhere; }}
    .badge {{ display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 650; border: 1px solid var(--line); }}
    .pass {{ color: var(--green); background: #ecfdf3; border-color: #b7e4ca; }}
    .fail {{ color: var(--red); background: #fff1ec; border-color: #ffc6b5; }}
    .skip {{ color: var(--amber); background: #fffbeb; border-color: #fde68a; }}
    .note {{ color: var(--muted); }}
    .notice {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; margin-top: 12px; }}
    @media (max-width: 980px) {{ .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .cards {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 640px) {{ .wrap {{ padding: 14px; }} .metrics {{ grid-template-columns: 1fr; }} h1 {{ font-size: 24px; }} }}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <h1>Benchmark Report</h1>
      <p>模型 A/B、mock/real provider、失败类型、修复率、build/runtime 通过率的统一 benchmark 页面。默认不会因为 real provider 未配置而联网。</p>
    </div>
  </header>
  <main class="wrap">
    <section class="notice">
      <span class="badge skip">Evidence Boundary</span>
      <p>{escape(BENCHMARK_EVIDENCE_SCOPE)}</p>
    </section>
    <section>
      <h2>Summary</h2>
      <div class="grid metrics">
        {self._metric_cards(result.metrics)}
      </div>
    </section>
    <section class="grid cards">
      <div class="card">
        <h2>Model A/B</h2>
        {self._model_table(result.model_runs)}
      </div>
      <div class="card">
        <h2>Failure Types</h2>
        {self._failure_table(result.failure_types)}
      </div>
    </section>
    <section class="card">
      <h2>Manual Runtime Evidence</h2>
      {self._runtime_table(result.runtime_cases)}
      <p class="note">Runtime pass rate is only populated from documented manual Minecraft runtime evidence. Fast benchmark runs keep build and runtime execution optional.</p>
    </section>
    <section class="card">
      <h2>Artifacts</h2>
      <table>
        <tr><th>Name</th><th>Path</th></tr>
        <tr><td>Benchmark JSON</td><td><code>{escape(str(result.benchmark_report_json_path))}</code></td></tr>
        <tr><td>Benchmark Markdown</td><td><code>{escape(str(result.benchmark_report_md_path))}</code></td></tr>
        <tr><td>Repair Eval</td><td><code>{escape(result.repair_eval_report_path or "")}</code></td></tr>
      </table>
    </section>
    {self._notices("Warnings", result.warnings, "skip")}
    {self._notices("Errors", result.errors, "fail")}
  </main>
</body>
</html>
"""

    def _metric_cards(self, metrics: dict[str, Any]) -> str:
        keys = [
            "model_runs_completed",
            "model_runs_skipped",
            "best_success_rate",
            "build_pass_rate",
            "repair_rate",
            "runtime_pass_rate",
            "failure_types_total",
            "runtime_cases_total",
        ]
        return "\n".join(
            f'<div class="metric"><span>{escape(key)}</span><strong>{escape(_format_value(metrics.get(key)))}</strong></div>'
            for key in keys
        )

    def _model_table(self, model_runs: list[BenchmarkModelRun]) -> str:
        rows = [
            "<table><tr><th>Label</th><th>Provider</th><th>Model</th><th>Status</th><th>Success</th><th>Audit</th><th>Build</th></tr>"
        ]
        for run in model_runs:
            rows.append(
                "<tr>"
                f"<td>{escape(run.label)}</td>"
                f"<td>{escape(run.provider_kind)}<br><code>{escape(run.provider)}</code></td>"
                f"<td><code>{escape(run.model)}</code></td>"
                f'<td><span class="badge {escape(run.status)}">{escape(run.status)}</span></td>'
                f"<td>{escape(_format_value(run.metrics.get('success_rate')))}</td>"
                f"<td>{escape(_format_value(run.metrics.get('audit_success_rate')))}</td>"
                f"<td>{escape(_format_value(run.metrics.get('build_success_rate')))}</td>"
                "</tr>"
            )
        rows.append("</table>")
        return "\n".join(rows)

    def _failure_table(self, failures: list[BenchmarkFailureType]) -> str:
        rows = [
            "<table><tr><th>Failure</th><th>Status</th><th>Audit</th><th>Repair</th><th>Recovered</th><th>RAG Hits</th></tr>"
        ]
        for failure in failures:
            status = "pass" if failure.success else "fail"
            rows.append(
                "<tr>"
                f"<td><code>{escape(failure.identifier)}</code><br>{escape(failure.title)}</td>"
                f'<td><span class="badge {status}">{status}</span></td>'
                f"<td>{escape(str(failure.audit_detected).lower())}</td>"
                f"<td>{escape(str(failure.repair_loop_repaired).lower())}</td>"
                f"<td>{escape(str(failure.audit_recovered).lower())}</td>"
                f"<td>{failure.repair_rag_hits_count}</td>"
                "</tr>"
            )
        rows.append("</table>")
        return "\n".join(rows)

    def _runtime_table(self, cases: list[BenchmarkRuntimeCase]) -> str:
        if not cases:
            return '<p class="note">No runtime validation evidence was found.</p>'
        rows = [
            "<table><tr><th>Case</th><th>Status</th><th>Workspace</th><th>Evidence</th></tr>"
        ]
        for case in cases:
            status = "pass" if case.passed else "fail"
            rows.append(
                "<tr>"
                f"<td>{escape(case.identifier)}</td>"
                f'<td><span class="badge {status}">{escape(case.status)}</span></td>'
                f"<td><code>{escape(case.workspace)}</code></td>"
                f"<td>{escape(case.notes)}</td>"
                "</tr>"
            )
        rows.append("</table>")
        return "\n".join(rows)

    def _notices(self, title: str, items: list[str], status: str) -> str:
        if not items:
            return ""
        body = "".join(f"<li>{escape(item)}</li>" for item in items)
        return f'<section class="notice"><span class="badge {status}">{escape(title)}</span><ul>{body}</ul></section>'


def _failure_from_repair_case(case: Any) -> BenchmarkFailureType:
    return BenchmarkFailureType(
        identifier=str(case.identifier),
        title=str(case.title),
        success=bool(case.success),
        audit_detected=bool(case.audit_detected),
        repair_loop_repaired=bool(case.repair_loop_repaired),
        audit_recovered=bool(case.audit_recovered),
        repair_rag_hits_count=int(case.repair_rag_hits_count),
        initial_audit_errors_count=int(case.initial_audit_errors_count),
        capabilities=list(case.repair_rag_capabilities),
        workspace=case.workspace,
    )


def agent_benchmark_metrics(cases: list[AgentBenchmarkCaseResult]) -> dict[str, Any]:
    total = len(cases)
    successes = sum(1 for case in cases if case.success)
    build_cases = [case for case in cases if case.build_attempted]
    audit_cases = [case for case in cases if case.audit_attempted]
    repair_cases = [case for case in cases if case.repair_success is not None]
    tool_cases = [case for case in cases if case.tool_calls_count > 0]
    iteration_cases = [case for case in cases if case.iterations > 0]
    patch_attempts = sum(case.patch_attempts_count for case in cases)
    patch_accepted = sum(case.patch_accepted_count for case in cases)
    trace_paths = _unique_strings(path for case in cases for path in case.trace_paths)
    rag_on = [case for case in cases if case.rag_mode == "on"]
    rag_off = [case for case in cases if case.rag_mode == "off"]
    injection_cases = [case for case in cases if case.breakage]
    expected_detection_cases = [case for case in cases if case.detected_expected_failure is not None]
    rag_citation_coverages = [case.rag_citation_coverage for case in cases if case.patch_attempts_count > 0]
    failed_cases = [
        {
            "id": case.identifier,
            "mode": case.mode,
            "breakage": case.breakage,
            "category": case.category,
            "failure_kind": case.failure_kind,
            "provider_status_code": case.provider_status_code,
            "provider_error_summary": case.provider_error_summary,
            "workspace": case.workspace,
            "errors": list(case.errors) or ["agent benchmark case failed"],
            "agent_run_json_path": case.agent_run_json_path,
        }
        for case in cases
        if not case.success
    ]
    metrics = {
        "cases_total": total,
        "success_count": successes,
        "success_rate": _rate(successes, total),
        "build_success_rate": _rate(sum(1 for case in build_cases if case.build_success is True), len(build_cases)) if build_cases else None,
        "audit_success_rate": _rate(sum(1 for case in audit_cases if case.audit_success is True), len(audit_cases)) if audit_cases else None,
        "repair_success_rate": _rate(sum(1 for case in repair_cases if case.repair_success is True), len(repair_cases)) if repair_cases else None,
        "avg_tool_calls": round(sum(case.tool_calls_count for case in tool_cases) / len(tool_cases), 2) if tool_cases else 0,
        "avg_iterations": round(sum(case.iterations for case in iteration_cases) / len(iteration_cases), 2) if iteration_cases else 0,
        "rag_hit_rate": _rate(sum(1 for case in cases if case.rag_hits_count > 0), total),
        "rag_decisions_count": sum(case.rag_decisions_count for case in cases),
        "rag_citations_count": sum(case.rag_citations_count for case in cases),
        "rag_citation_coverage_rate": round(sum(rag_citation_coverages) / len(rag_citation_coverages), 4) if rag_citation_coverages else 0.0,
        "patch_accept_rate": _rate(patch_accepted, patch_attempts),
        "patch_attempts_count": patch_attempts,
        "patch_accepted_count": patch_accepted,
        "rollback_count": sum(case.rollback_count for case in cases),
        "audit_detection_rate": _rate(sum(1 for case in injection_cases if case.initial_audit_issue_ids), len(injection_cases)),
        "expected_failure_detection_rate": _rate(
            sum(1 for case in expected_detection_cases if case.detected_expected_failure is True),
            len(expected_detection_cases),
        ),
        "cases_by_category": _case_counts_by_category(cases),
        "failed_cases": failed_cases,
        "failed_cases_count": len(failed_cases),
        "provider_error_count": sum(1 for case in cases if case.provider_error_summary),
        "provider_error_cases_count": len([case for case in cases if case.provider_error_summary]),
        "repair_logic_failure_count": sum(1 for case in cases if case.failure_kind == "repair_logic_failure"),
        "rag_on_repair_logic_failure_count": sum(1 for case in cases if case.rag_mode == "on" and case.failure_kind == "repair_logic_failure"),
        "trace_paths": trace_paths,
        "trace_paths_count": len(trace_paths),
        "evidence_scope": BENCHMARK_EVIDENCE_SCOPE,
    }
    if rag_on or rag_off:
        rag_on_success = _rate(sum(1 for case in rag_on if case.success), len(rag_on))
        rag_off_success = _rate(sum(1 for case in rag_off if case.success), len(rag_off))
        rag_on_audit = _rate(sum(1 for case in rag_on if case.audit_success is True), len([case for case in rag_on if case.audit_attempted]))
        rag_off_audit = _rate(sum(1 for case in rag_off if case.audit_success is True), len([case for case in rag_off if case.audit_attempted]))
        rag_on_iterations = _avg([case.iterations for case in rag_on if case.iterations > 0])
        rag_off_iterations = _avg([case.iterations for case in rag_off if case.iterations > 0])
        rag_on_tools = _avg([case.tool_calls_count for case in rag_on if case.tool_calls_count > 0])
        rag_off_tools = _avg([case.tool_calls_count for case in rag_off if case.tool_calls_count > 0])
        rag_on_detection = [case for case in rag_on if case.detected_expected_failure is not None]
        metrics.update(
            {
                "rag_on_success_rate": rag_on_success,
                "rag_off_success_rate": rag_off_success,
                "rag_on_audit_success_rate": rag_on_audit,
                "rag_off_audit_success_rate": rag_off_audit,
                "rag_on_avg_iterations": rag_on_iterations,
                "rag_off_avg_iterations": rag_off_iterations,
                "rag_on_avg_tool_calls": rag_on_tools,
                "rag_off_avg_tool_calls": rag_off_tools,
                "rag_success_delta": round(rag_on_success - rag_off_success, 4),
                "rag_iteration_delta": round(rag_off_iterations - rag_on_iterations, 4),
                "rag_tool_call_delta": round(rag_off_tools - rag_on_tools, 4),
                "rag_on_expected_detection_rate": _rate(
                    sum(1 for case in rag_on_detection if case.detected_expected_failure is True),
                    len(rag_on_detection),
                ),
            }
        )
    return metrics


def _provider_error_from_agent_run(
    run: AgentRunResult,
    tool_trace: list[dict[str, Any]],
    repair_payload: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    for entry in tool_trace:
        if not isinstance(entry, dict):
            continue
        observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
        candidate = _provider_error_from_mapping(observation)
        if candidate:
            return candidate
        completion = entry.get("completion") if isinstance(entry.get("completion"), dict) else {}
        candidate = _provider_error_from_mapping(completion)
        if candidate:
            return candidate
    candidate = _provider_error_from_mapping(repair_payload)
    if candidate:
        return candidate
    for trace in run.prompt_traces:
        completion_usage = getattr(trace, "completion_usage", {})
        if isinstance(completion_usage, dict):
            candidate = _provider_error_from_mapping(completion_usage)
            if candidate:
                return candidate
        error_text = str(getattr(trace, "error", "") or "")
        candidate = _provider_error_from_text(error_text)
        if candidate:
            return candidate
    for text in errors:
        candidate = _provider_error_from_text(str(text))
        if candidate:
            return candidate
    return {}


def _provider_error_from_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    provider_error = payload.get("provider_error") if isinstance(payload.get("provider_error"), dict) else {}
    if provider_error:
        return {
            "summary": str(provider_error.get("message") or payload.get("summary") or "LLM provider request failed."),
            "status_code": _int_or_none(provider_error.get("status_code")),
        }
    summary = str(payload.get("summary") or payload.get("error") or "")
    if "LLM provider" in summary or "provider request failed" in summary:
        return {
            "summary": summary,
            "status_code": _int_or_none(payload.get("provider_status_code")) or _status_code_from_text(summary),
        }
    return {}


def _provider_error_from_text(text: str) -> dict[str, Any]:
    if not text or ("LLM provider" not in text and "provider request failed" not in text):
        return {}
    return {
        "summary": text,
        "status_code": _status_code_from_text(text),
    }


def _status_code_from_text(text: str) -> int | None:
    match = re.search(r"HTTP\s+(\d{3})", text)
    return int(match.group(1)) if match else None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _classify_agent_benchmark_failure(
    *,
    success: bool,
    repair_success: bool | None,
    build_payload: dict[str, Any],
    audit_payload: dict[str, Any],
    provider_error: dict[str, Any],
) -> str:
    if success:
        return ""
    if provider_error:
        return "provider_error"
    if repair_success is False:
        return "repair_logic_failure"
    if (build_payload.get("attempted") and build_payload.get("success") is False) or (
        audit_payload.get("attempted") and audit_payload.get("success") is False
    ):
        return "gate_failure"
    return "unknown"


def _agent_benchmark_case_from_run(
    case: AgentBenchmarkCaseSpec,
    run: AgentRunResult,
    *,
    managed_regen_probe: dict[str, Any] | None = None,
    injected_paths: list[str] | None = None,
    initial_audit_issue_ids: list[str] | None = None,
    detected_expected_failure: bool | None = None,
) -> AgentBenchmarkCaseResult:
    payload = run.payload or {}
    repair_payload = payload.get("repair") if isinstance(payload.get("repair"), dict) else {}
    generation_payload = payload.get("generation") if isinstance(payload.get("generation"), dict) else {}
    build_payload = _dict_or_empty(repair_payload.get("final_build") or payload.get("build") or generation_payload.get("build"))
    audit_payload = _dict_or_empty(repair_payload.get("final_audit") or payload.get("audit"))
    tool_trace = _load_json_list(run.tool_call_trace_json_path)
    if not tool_trace:
        tool_trace = [dict(item) for item in repair_payload.get("tool_call_trace", []) if isinstance(item, dict)]
    reviewer_report = _load_json_dict(run.reviewer_report_json_path)
    reviewer_payload = _dict_or_empty(payload.get("reviewer") or repair_payload.get("reviewer"))
    if not reviewer_report:
        reviewer_report = reviewer_payload

    patch_attempts = 0
    patch_accepted = 0
    rag_hits_from_trace = 0
    rag_decision_path = run.workspace / ".agent" / "rag-decision-trace.json" if run.workspace else None
    rag_decisions = _load_json_list(rag_decision_path)
    rag_citation_ids = _unique_strings(
        citation
        for decision in rag_decisions
        for citation in (decision.get("citations") or [])
    )
    for entry in tool_trace:
        if entry.get("action") == "apply_structured_patch":
            patch_attempts += 1
            observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
            if observation.get("success") is True:
                patch_accepted += 1
        if entry.get("action") == "retrieve_rag":
            observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
            rag_hits_from_trace += int(observation.get("hits_count") or 0)

    rollback_paths = _rollback_evidence_paths(run.workspace, repair_payload)
    trace_paths = _unique_strings(
        path
        for path in [
            str(run.agent_run_json_path) if run.agent_run_json_path else "",
            str(run.tool_call_trace_json_path) if run.tool_call_trace_json_path else "",
            str(run.reviewer_report_json_path) if run.reviewer_report_json_path else "",
            str(run.prompt_trace_json_path) if run.prompt_trace_json_path else "",
            str(rag_decision_path) if rag_decision_path and rag_decision_path.exists() else "",
        ]
        if path
    )
    regen_success = None
    regen_report = None
    if isinstance(managed_regen_probe, dict):
        regen_success = bool(managed_regen_probe.get("success"))
        regen_report = str(managed_regen_probe.get("repair_loop_report_json_path") or "")

    errors = [error for step in run.steps for error in step.errors]
    if not run.success and not errors:
        errors.append("Agent run failed deterministic audit/build or repair gate.")
    rag_payload = repair_payload.get("repair_rag") if isinstance(repair_payload.get("repair_rag"), dict) else {}
    rag_hits = max(int(rag_payload.get("hits_count") or 0), rag_hits_from_trace)
    tool_calls = len(tool_trace) if tool_trace else int(repair_payload.get("tool_calls_count") or 0)
    iterations = int(repair_payload.get("iterations") or tool_calls or 0)
    repair_success = None
    if repair_payload.get("attempted"):
        repair_success = bool(repair_payload.get("success"))
    provider_error = _provider_error_from_agent_run(run, tool_trace, repair_payload, errors)
    failure_kind = _classify_agent_benchmark_failure(
        success=bool(run.success),
        repair_success=repair_success,
        build_payload=build_payload,
        audit_payload=audit_payload,
        provider_error=provider_error,
    )

    return AgentBenchmarkCaseResult(
        identifier=case.identifier,
        mode=case.mode,
        request=case.request,
        success=bool(run.success),
        workspace=str(run.workspace) if run.workspace else None,
        breakage=case.breakage,
        category=case.category,
        injected_paths=list(injected_paths or []),
        initial_audit_issue_ids=list(initial_audit_issue_ids or []),
        detected_expected_failure=detected_expected_failure,
        agent_run_json_path=str(run.agent_run_json_path) if run.agent_run_json_path else None,
        tool_call_trace_json_path=str(run.tool_call_trace_json_path) if run.tool_call_trace_json_path else None,
        reviewer_report_json_path=str(run.reviewer_report_json_path) if run.reviewer_report_json_path else None,
        prompt_trace_json_path=str(run.prompt_trace_json_path) if run.prompt_trace_json_path else None,
        managed_regen_success=regen_success,
        managed_regen_report_json_path=regen_report,
        build_attempted=bool(build_payload.get("attempted")),
        build_success=build_payload.get("success") if build_payload.get("attempted") else None,
        audit_attempted=bool(audit_payload.get("attempted")),
        audit_success=audit_payload.get("success") if audit_payload.get("attempted") else None,
        repair_success=repair_success,
        tool_calls_count=tool_calls,
        iterations=iterations,
        rag_hits_count=rag_hits,
        patch_attempts_count=patch_attempts,
        patch_accepted_count=patch_accepted,
        rollback_count=len(rollback_paths),
        rollback_evidence_paths=rollback_paths,
        reviewer_decision=str(reviewer_report.get("decision") or reviewer_payload.get("decision") or ""),
        reviewer_coverage_status=str(reviewer_report.get("coverage_status") or reviewer_payload.get("coverage_status") or ""),
        rag_mode=case.rag_mode or "auto",
        rag_decision_trace_json_path=str(rag_decision_path) if rag_decision_path and rag_decision_path.exists() else None,
        rag_decisions_count=len(rag_decisions),
        rag_citations_count=len(rag_citation_ids),
        rag_citation_coverage=citation_coverage(tool_trace),
        trace_paths=trace_paths,
        failure_kind=failure_kind,
        provider_status_code=provider_error.get("status_code"),
        provider_error_summary=str(provider_error.get("summary") or ""),
        errors=errors,
    )


def _failed_agent_benchmark_case(
    case: AgentBenchmarkCaseSpec,
    run: AgentRunResult,
    message: str,
) -> AgentBenchmarkCaseResult:
    result = _agent_benchmark_case_from_run(case, run)
    result.success = False
    result.errors.append(message)
    provider_error = _provider_error_from_text(message)
    if provider_error:
        result.failure_kind = "provider_error"
        result.provider_status_code = provider_error.get("status_code")
        result.provider_error_summary = str(provider_error.get("summary") or "")
    elif not result.failure_kind:
        result.failure_kind = "gate_failure"
    return result


def _inject_agent_benchmark_breakage(workspace: Path, breakage: str) -> AgentBenchmarkBreakageInjection:
    normalized = _normalize_breakage(breakage)
    handlers = _agent_benchmark_breakage_registry()
    handler = handlers.get(normalized)
    if handler is None:
        raise ValueError(f"Unsupported agent benchmark breakage: {breakage}")
    workspace = workspace.resolve()
    spec = _load_agent_benchmark_modspec(workspace)
    paths = handler(workspace, spec)
    if not paths:
        raise ValueError(f"Agent benchmark breakage injected no files: {breakage}")
    return AgentBenchmarkBreakageInjection(
        breakage=normalized,
        injected_paths=[_workspace_relative_path(workspace, path) for path in paths],
    )


def _agent_benchmark_breakage_registry() -> dict[str, Any]:
    return {
        "delete_mods_toml": _break_delete_mods_toml,
        "break_pack_mcmeta_format": _break_pack_mcmeta_format,
        "corrupt_pack_mcmeta_json": _break_corrupt_pack_mcmeta_json,
        "delete_item_definition": _break_delete_item_definition,
        "delete_item_model": _break_delete_item_model,
        "corrupt_item_texture_png": _break_corrupt_item_texture_png,
        "delete_blockstate": _break_delete_blockstate,
        "delete_block_loot_table": _break_delete_block_loot_table,
        "remove_lang_entry": _break_remove_lang_entry,
        "delete_recipe_file": _break_delete_recipe_file,
        "corrupt_recipe_json": _break_corrupt_recipe_json,
        "break_recipe_reference": _break_recipe_reference,
        "delete_ore_configured_feature": _break_delete_ore_configured_feature,
        "break_ore_rule_test": _break_ore_rule_test,
        "delete_ore_biome_modifier": _break_delete_ore_biome_modifier,
        "delete_behavior_item_java": _break_delete_behavior_item_java,
        "delete_machine_block_entity_java": _break_delete_machine_block_entity_java,
        "delete_entity_spawn_modifier": _break_delete_entity_spawn_modifier,
    }


def _normalize_breakage(breakage: str) -> str:
    normalized = str(breakage or "delete_mods_toml").strip()
    aliases = {
        "": "delete_mods_toml",
        "break_pack_mcmeta": "break_pack_mcmeta_format",
        "break_recipe_json": "break_recipe_reference",
    }
    return aliases.get(normalized, normalized)


def _break_delete_mods_toml(workspace: Path, spec: ModSpec) -> list[Path]:
    return [_delete_or_mark(workspace, workspace / "src" / "main" / "templates" / "META-INF" / "neoforge.mods.toml")]


def _break_pack_mcmeta_format(workspace: Path, spec: ModSpec) -> list[Path]:
    target = _safe_workspace_path(workspace, workspace / "src" / "main" / "resources" / "pack.mcmeta")
    text = target.read_text(encoding="utf-8")
    if '"pack_format": 61' in text:
        text = text.replace('"pack_format": 61', '"pack_format": "BROKEN"', 1)
    else:
        text = text.replace('"pack_format":', '"pack_format_broken":', 1)
    target.write_text(text, encoding="utf-8")
    return [target]


def _break_corrupt_pack_mcmeta_json(workspace: Path, spec: ModSpec) -> list[Path]:
    target = _safe_workspace_path(workspace, workspace / "src" / "main" / "resources" / "pack.mcmeta")
    target.write_text('{"pack": {"description": "broken", "pack_format": 61,,}}\n', encoding="utf-8")
    return [target]


def _break_delete_item_definition(workspace: Path, spec: ModSpec) -> list[Path]:
    identifier = _first_item_like_id(spec)
    return [_delete_or_mark(workspace, workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "items" / f"{identifier}.json")]


def _break_delete_item_model(workspace: Path, spec: ModSpec) -> list[Path]:
    identifier = _first_item_like_id(spec)
    return [_delete_or_mark(workspace, workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "models" / "item" / f"{identifier}.json")]


def _break_corrupt_item_texture_png(workspace: Path, spec: ModSpec) -> list[Path]:
    identifier = _first_item_like_id(spec)
    target = _safe_workspace_path(workspace, workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "textures" / "item" / f"{identifier}.png")
    target.write_bytes(b"not-a-png\n")
    return [target]


def _break_delete_blockstate(workspace: Path, spec: ModSpec) -> list[Path]:
    identifier = _first_block_like_id(spec)
    return [_delete_or_mark(workspace, workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "blockstates" / f"{identifier}.json")]


def _break_delete_block_loot_table(workspace: Path, spec: ModSpec) -> list[Path]:
    identifier = _first_block_like_id(spec)
    return [_delete_or_mark(workspace, workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "loot_table" / "blocks" / f"{identifier}.json")]


def _break_remove_lang_entry(workspace: Path, spec: ModSpec) -> list[Path]:
    target = _safe_workspace_path(workspace, workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "lang" / "en_us.json")
    data = json.loads(target.read_text(encoding="utf-8"))
    key = f"item.{spec.mod_id}.{_first_item_like_id(spec)}"
    if key not in data:
        key = f"block.{spec.mod_id}.{_first_block_like_id(spec)}"
    data.pop(key, None)
    write_json(target, data)
    return [target]


def _break_delete_recipe_file(workspace: Path, spec: ModSpec) -> list[Path]:
    recipe = _first_recipe_id(spec)
    return [_delete_or_mark(workspace, workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "recipe" / f"{recipe}.json")]


def _break_corrupt_recipe_json(workspace: Path, spec: ModSpec) -> list[Path]:
    recipe = _first_recipe_id(spec)
    target = _safe_workspace_path(workspace, workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "recipe" / f"{recipe}.json")
    target.write_text('{"type": "minecraft:crafting_shaped", "key": }\n', encoding="utf-8")
    return [target]


def _break_recipe_reference(workspace: Path, spec: ModSpec) -> list[Path]:
    recipe = _first_recipe_id(spec)
    target = _safe_workspace_path(workspace, workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "recipe" / f"{recipe}.json")
    data = json.loads(target.read_text(encoding="utf-8"))
    bad_reference = f"{spec.mod_id}:missing_agentic_rag_material"
    if isinstance(data.get("key"), dict) and data["key"]:
        first_key = next(iter(data["key"]))
        data["key"][first_key] = bad_reference
    elif isinstance(data.get("ingredients"), list) and data["ingredients"]:
        data["ingredients"][0] = bad_reference
    else:
        data["result"] = {"id": bad_reference, "count": 1}
    write_json(target, data)
    return [target]


def _break_delete_ore_configured_feature(workspace: Path, spec: ModSpec) -> list[Path]:
    ore = _first_ore_id(spec)
    return [_delete_or_mark(workspace, workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "worldgen" / "configured_feature" / f"{ore}.json")]


def _break_ore_rule_test(workspace: Path, spec: ModSpec) -> list[Path]:
    ore = _first_ore_id(spec)
    target = _safe_workspace_path(workspace, workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "worldgen" / "configured_feature" / f"{ore}.json")
    data = json.loads(target.read_text(encoding="utf-8"))
    data["config"]["targets"][0]["target"] = "minecraft:stone_ore_replaceables"
    write_json(target, data)
    return [target]


def _break_delete_ore_biome_modifier(workspace: Path, spec: ModSpec) -> list[Path]:
    ore = _first_ore_id(spec)
    return [_delete_or_mark(workspace, workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "neoforge" / "biome_modifier" / f"add_{ore}.json")]


def _break_delete_behavior_item_java(workspace: Path, spec: ModSpec) -> list[Path]:
    item = next((item for item in spec.items if item.behavior is not None), None)
    if item is None:
        raise ValueError("No generated behavior item was available.")
    class_name = "".join(part.capitalize() for part in item.identifier.split("_")) + "Item"
    return [_delete_or_mark(workspace, workspace / "src" / "main" / "java" / Path(*spec.package_name.split(".")) / "item" / f"{class_name}.java")]


def _break_delete_machine_block_entity_java(workspace: Path, spec: ModSpec) -> list[Path]:
    if not spec.machines:
        raise ValueError("No generated machine was available.")
    base_name = "".join(part.capitalize() for part in spec.machines[0].identifier.split("_"))
    return [
        _delete_or_mark(
            workspace,
            workspace
            / "src"
            / "main"
            / "java"
            / Path(*spec.package_name.split("."))
            / "block"
            / "entity"
            / f"{base_name}BlockEntity.java",
        )
    ]


def _break_delete_entity_spawn_modifier(workspace: Path, spec: ModSpec) -> list[Path]:
    entity = next((entity for entity in spec.entities if entity.spawn is not None and entity.spawn.enabled), None)
    if entity is None:
        raise ValueError("No generated spawning entity was available.")
    return [_delete_or_mark(workspace, workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "neoforge" / "biome_modifier" / f"add_{entity.identifier}.json")]


def _paired_rag_ablation_cases(cases: list[AgentBenchmarkCaseSpec]) -> list[AgentBenchmarkCaseSpec]:
    paired: list[AgentBenchmarkCaseSpec] = []
    for case in cases:
        for mode in ("on", "off"):
            paired.append(
                AgentBenchmarkCaseSpec(
                    identifier=f"{case.identifier}_rag_{mode}",
                    mode=case.mode,
                    request=case.request,
                    setup_request=case.setup_request,
                    breakage=case.breakage,
                    max_iterations=case.max_iterations,
                    rag_mode=mode,
                    category=case.category,
                    expected_issue_prefixes=list(case.expected_issue_prefixes),
                    expected_repair_strategy=case.expected_repair_strategy,
                )
            )
    return paired


def _agent_benchmark_success(cases: list[AgentBenchmarkCaseResult], *, rag_ablation: bool) -> bool:
    if not cases:
        return False
    if not rag_ablation:
        return all(case.success for case in cases)
    rag_on = [case for case in cases if case.rag_mode == "on"]
    return bool(rag_on) and all(case.success for case in rag_on)


def _rollback_evidence_paths(workspace: Path | None, repair_payload: dict[str, Any]) -> list[str]:
    paths = []
    direct = repair_payload.get("structured_patch_rollback_json_path")
    if direct:
        paths.append(str(direct))
    structured = repair_payload.get("structured_patch") if isinstance(repair_payload.get("structured_patch"), dict) else {}
    artifacts = structured.get("artifacts") if isinstance(structured.get("artifacts"), dict) else {}
    if artifacts.get("rollback_json"):
        paths.append(str(artifacts["rollback_json"]))
    if workspace is not None:
        candidate = workspace / ".agent" / "structured-patch-rollback-report.json"
        if candidate.exists():
            paths.append(str(candidate))
    return _unique_strings(path for path in paths if path)


def _load_agent_benchmark_modspec(workspace: Path) -> ModSpec:
    path = workspace / ".agent" / "modspec.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing benchmark modspec: {path}")
    return ModSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _safe_workspace_path(workspace: Path, path: Path) -> Path:
    root = workspace.resolve()
    target = path.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Agent benchmark breakage path escapes workspace: {path}") from exc
    return target


def _delete_or_mark(workspace: Path, path: Path) -> Path:
    target = _safe_workspace_path(workspace, path)
    if target.exists():
        target.unlink()
    return target


def _workspace_relative_path(workspace: Path, path: Path) -> str:
    return _safe_workspace_path(workspace, path).relative_to(workspace.resolve()).as_posix()


def _first_item_like_id(spec: ModSpec) -> str:
    items = list(spec.all_item_like())
    if not items:
        raise ValueError("No generated item-like feature was available.")
    return items[0].identifier


def _first_block_like_id(spec: ModSpec) -> str:
    blocks = [*spec.blocks, *spec.machines, *spec.ores]
    if not blocks:
        raise ValueError("No generated block-like feature was available.")
    return blocks[0].identifier


def _first_recipe_id(spec: ModSpec) -> str:
    if not spec.recipes:
        raise ValueError("No generated recipe was available.")
    return spec.recipes[0].identifier


def _first_ore_id(spec: ModSpec) -> str:
    if not spec.ores:
        raise ValueError("No generated ore was available.")
    return spec.ores[0].identifier


def _matches_issue_prefixes(issue_ids: list[str], prefixes: list[str]) -> bool:
    if not prefixes:
        return bool(issue_ids)
    return any(any(issue_id.startswith(prefix) for prefix in prefixes) for issue_id in issue_ids)


def _load_json_list(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [dict(item) for item in data if isinstance(item, dict)]


def _load_json_dict(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def _limit_cases(cases: list[AgentBenchmarkCaseSpec], limit: int | None) -> list[AgentBenchmarkCaseSpec]:
    if limit is None:
        return list(cases)
    return list(cases[: max(0, int(limit))])


def _case_counts_by_category(cases: list[AgentBenchmarkCaseResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        category = case.category or "uncategorized"
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def _unique_strings(items) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item)
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _provider_kind(provider: str) -> str:
    return "mock" if provider == "mock" else "real"


def _rate(count: int, total: int) -> float:
    return float(count / total) if total else 0.0


def _avg(values: list[int] | list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _format_value(value: Any) -> str:
    if value is None:
        return "not run"
    if isinstance(value, float):
        return f"{value:.2%}" if 0 <= value <= 1 else f"{value:.4f}"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)
