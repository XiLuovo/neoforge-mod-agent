from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .domain_spec import DomainSpecRegistry
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class Capability:
    identifier: str
    name: str
    status: str
    summary: str
    commands: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "commands": list(self.commands),
            "artifacts": list(self.artifacts),
            "notes": list(self.notes),
        }


@dataclass(slots=True)
class CapabilitySection:
    identifier: str
    title: str
    summary: str
    capabilities: list[Capability]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "title": self.title,
            "summary": self.summary,
            "capabilities": [capability.to_dict() for capability in self.capabilities],
        }


@dataclass(slots=True)
class CapabilityMatrixResult:
    success: bool
    run_id: str
    version: str
    project: dict[str, Any]
    sections: list[CapabilitySection]
    limitations: list[str]
    capability_report_json_path: Path
    capability_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        total_capabilities = sum(len(section.capabilities) for section in self.sections)
        return {
            "success": self.success,
            "run_id": self.run_id,
            "version": self.version,
            "project": dict(self.project),
            "sections": [section.to_dict() for section in self.sections],
            "limitations": list(self.limitations),
            "sections_count": len(self.sections),
            "capabilities_count": total_capabilities,
            "capability_report_json_path": str(self.capability_report_json_path),
            "capability_report_md_path": str(self.capability_report_md_path),
        }


class CapabilityCatalog:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def build(self, *, run_name: str | None = None) -> CapabilityMatrixResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        report_dir = ensure_directory(self.config.workspace_root / "capability-runs" / run_id / ".agent")
        version = self._project_version()
        report_json = report_dir / "capabilities.json"
        report_md = report_dir / "capabilities.md"
        result = CapabilityMatrixResult(
            success=True,
            run_id=run_id,
            version=version,
            project=self._project_metadata(version),
            sections=self._sections(),
            limitations=self._limitations(),
            capability_report_json_path=report_json,
            capability_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_markdown(result))
        return result

    def _project_version(self) -> str:
        pyproject_path = self.config.project_root / "pyproject.toml"
        if not pyproject_path.exists():
            return "unknown"
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version", "unknown"))

    def _project_metadata(self, version: str) -> dict[str, Any]:
        return {
            "name": "neoforge-mod-agent",
            "version": version,
            "loader": self.config.loader,
            "neo_version": self.config.neo_version,
            "java_version": self.config.java_version,
            "template": self.config.template_name,
            "python": ">=3.11",
            "default_workspace_root": str(self.config.workspace_root),
            "domain_specs": DomainSpecRegistry.default().to_dict(),
        }

    def _sections(self) -> list[CapabilitySection]:
        return [
            CapabilitySection(
                identifier="domain_specs",
                title="Domain Spec Plugins",
                summary="Domain-neutral spec registry that makes ModSpec one supported DomainSpec instead of the only possible project shape.",
                capabilities=[
                    Capability(
                        "domain_spec_registry",
                        "DomainSpec Registry",
                        "stable",
                        "List and resolve generation domains through a plugin registry before domain-specific planning, validation, generation, audit, and repair run.",
                        ["domains"],
                        ["src/neoforge_agent/domain_spec.py"],
                    ),
                    Capability(
                        "neoforge_domain_spec",
                        "NeoForge ModSpec Domain",
                        "stable",
                        "Treat Minecraft NeoForge ModSpec as the stable minecraft.neoforge DomainSpec implementation.",
                        ["generate", "generate-from-spec", "agent generate"],
                        [".agent/modspec.json"],
                    ),
                    Capability(
                        "planned_spring_api_spec",
                        "Planned Spring API Spec",
                        "planned",
                        "Reserve a future spring.api DomainSpec slot for endpoints, DTOs, services, validation, tests, and OpenAPI evidence without claiming generation support yet.",
                        ["domains --json"],
                    ),
                    Capability(
                        "planned_unity_component_spec",
                        "Planned Unity Component Spec",
                        "planned",
                        "Reserve a future unity.component DomainSpec slot for MonoBehaviour components, prefab metadata, scenes, tests, and gameplay evidence without claiming generation support yet.",
                        ["domains --json"],
                    ),
                ],
            ),
            CapabilitySection(
                identifier="workflows",
                title="Core Workflows",
                summary="End-user commands for generating, modifying, validating, and presenting mod projects.",
                capabilities=[
                    Capability("generate", "Generate Workspace", "stable", "Create a new NeoForge workspace from natural language or ModSpec.", ["generate", "generate-from-spec"]),
                    Capability("modify", "Modify Existing Workspace", "stable", "Plan a controlled patch, merge natural language changes into an existing generated workspace, and regenerate only managed files.", ["modify"], [".agent/modspec.before.json", ".agent/modspec.after.json", ".agent/modify-summary.json", ".agent/patch-agent-plan.json", ".agent/patch-agent-report.json", ".agent/patch-agent-rollback-report.json"]),
                    Capability("patch_agent", "Controlled Patch Agent", "experimental", "Emit a patch plan, stay inside managed-file boundaries, and require audit, build, and rollback evidence before accepting a modification.", ["modify", "agent modify"], [".agent/patch-agent-plan.json", ".agent/patch-agent-plan.md", ".agent/patch-agent-report.json", ".agent/patch-agent-report.md", ".agent/patch-agent-rollback-report.json"]),
                    Capability("agent_generate", "Agent Generate", "stable", "Run planner, reviewer, executor, auditor, and repair roles for new workspace generation, with ModSpec-first routing and optional Direct Code Lane.", ["agent generate --code-lane hybrid"], [".agent/agent-run.json", ".agent/agent-run.md", ".agent/agent-decisions.md", ".agent/prompt-trace.json"]),
                    Capability("agent_modify", "Agent Modify", "stable", "Run multi-role orchestration for incremental workspace modification, with ModSpec-first routing and optional Direct Code Lane.", ["agent modify --code-lane hybrid"], [".agent/agent-run.json", ".agent/agent-run.md", ".agent/agent-decisions.md", ".agent/prompt-trace.json"]),
                    Capability("direct_code_lane", "Direct Code Lane", "experimental", "Apply audited structured JSON source patches inside generated workspaces when ModSpec is not expressive enough.", ["agent generate --code-lane direct", "agent modify --code-lane direct"], [".agent/direct-code-plan.json", ".agent/direct-code-review.json", ".agent/direct-code-diff.md", ".agent/direct-code-report.json", ".agent/direct-code-rollback-report.json"]),
                    Capability("free_code_lab", "Free-Code Lab", "experimental", "Copy a generated workspace into an isolated lab run, let an LLM propose structured experimental patches, and record audit/build evidence without changing the stable generator.", ["agent lab-generate"], ["workspace/free-code-lab-runs/<run-id>/.agent/free-code-plan.json", "workspace/free-code-lab-runs/<run-id>/.agent/free-code-diff.md", "workspace/free-code-lab-runs/<run-id>/.agent/free-code-report.json", "workspace/free-code-lab-runs/<run-id>/.agent/manual-runtime-checklist.md", "workspace/free-code-lab-runs/<run-id>/.agent/harvest-candidate.json"]),
                    Capability("capability_harvest_report", "Capability Harvest Report", "experimental", "Aggregate Free-Code Lab candidates by generate gap, harvest direction, gate result, and readiness so successful experiments can be deliberately folded back into ModSpec, DSL, generator templates, audit rules, or repair rules.", ["harvest-report"], ["workspace/harvest-runs/<run-id>/.agent/harvest-report.json", "workspace/harvest-runs/<run-id>/.agent/harvest-report.md"]),
                    Capability("multi_agent_trace", "Multi-Agent Trace", "stable", "Persist planner, reviewer, executor, auditor, and repair role inputs, outputs, decisions, and prompt traces for inspection.", ["agent generate", "agent modify"], [".agent/agent-trace-summary.json", ".agent/agent-trace-summary.md"]),
                    Capability("agent_replay", "Agent Run Replay", "stable", "Replay a saved .agent/agent-run.json into a deterministic historical timeline without rerunning LLMs, generators, audit, build, or repair.", ["replay"], [".agent/agent-run-replay.json", ".agent/agent-run-replay.md", ".agent/agent-run-replay.html"]),
                    Capability("session_trace_viewer", "Session Trace Viewer", "stable", "Render a static HTML session viewer with role timeline filters, decision details, LLM provider telemetry, RAG/repair evidence, and artifact links.", ["replay"], [".agent/agent-run-replay.html"]),
                    Capability("replay_repair_rag", "Replay Repair RAG Events", "stable", "Include repair RAG query, retrieved knowledge ids, and repair evidence artifacts in deterministic agent-run replay.", ["replay"], [".agent/agent-run-replay.json", ".agent/repair-rag-context.json"]),
                    Capability("audit", "Project Audit", "stable", "Check generated workspace structure against ModSpec and generation-summary.", ["audit"], [".agent/audit-report.json", ".agent/audit-report.md"]),
                    Capability("build", "Gradle Build", "stable", "Run Gradle build verification for generated workspaces.", ["build", "generate --build", "modify --build"]),
                    Capability("repair", "Repair Artifacts", "stable", "Classify failed build logs and generate repair context.", ["repair", "--repair"], [".agent/debug-context.md", ".agent/fix-request.md", ".agent/suspected-errors.json"]),
                    Capability("repair_loop", "Auto Repair Loop", "stable", "Run audit/build checks, safely regenerate managed files when checks fail, and write a repair-loop report.", ["repair-loop"], [".agent/repair-loop-report.json", ".agent/repair-loop-report.md"]),
                    Capability("repair_agent_execute", "Repair Agent Execute", "stable", "Agent generate/modify can automatically run the safe repair loop after audit or build failures, then use the repaired check result as the final run outcome.", ["agent generate", "agent modify"], [".agent/agent-repair-plan.json", ".agent/repair-loop-report.json"]),
                    Capability("repair_rag", "Repair RAG Advisor", "stable", "Retrieve bundled NeoForge knowledge for audit/build repair root causes and attach the evidence to repair plans.", ["agent generate", "agent modify"], [".agent/repair-rag-context.json", ".agent/repair-rag-context.md"]),
                    Capability("eval", "Benchmark Eval", "stable", "Run offline benchmark prompts and aggregate agent metrics.", ["eval"], ["workspace/eval-runs/<run-id>/.agent/eval-report.json"]),
                    Capability("eval_coverage_metrics", "Eval Coverage Metrics", "stable", "Measure expected capability categories, trace artifact presence, and repeat modify idempotency across benchmark cases.", ["eval --planner llm --llm-provider mock --no-build --audit"], ["workspace/eval-runs/<run-id>/.agent/eval-report.json"]),
                    Capability("eval_compare", "Eval Compare", "stable", "Compare two eval reports and fail when monitored rates or case outcomes regress.", ["eval-compare"], ["workspace/eval-comparisons/<run-id>/.agent/eval-compare-report.json"]),
                    Capability("llm_eval_report", "Real LLM Eval Report", "stable", "Run a mock baseline eval, optional real LLM candidate eval, and an automatic comparison report with provider config diagnostics.", ["llm-eval-report"], ["workspace/llm-eval-runs/<run-id>/.agent/llm-eval-report.json"]),
                    Capability("real_llm_eval_compare", "Real LLM Compare", "stable", "Compare OpenAI-compatible LLM planning quality against the deterministic mock baseline while keeping offline mock mode available for tests.", ["llm-eval-report --candidate-provider openai-compatible"], ["workspace/llm-eval-runs/<run-id>/runs/eval-comparisons/<compare>/.agent/eval-compare-report.json"]),
                    Capability("benchmark_report_page", "Benchmark Report Page", "stable", "Aggregate model A/B, mock/real provider status, failure types, repair rate, build pass rate, and documented runtime pass rate into one static HTML benchmark page.", ["benchmark-report"], ["workspace/benchmark-runs/<run-id>/.agent/benchmark-report.html"]),
                    Capability("evidence_chain_report", "Layered Evidence Chain Report", "stable", "Aggregate Stable ModSpec, Behavior DSL, and controlled patch-agent proof into one report with success rates, failure samples, recovery rates, generated file counts, and runtime validation evidence.", ["evidence-chain-report"], ["workspace/evidence-chain-runs/<run-id>/.agent/evidence-chain-report.json", "workspace/evidence-chain-runs/<run-id>/.agent/evidence-chain-report.md"]),
                    Capability("golden_tests", "Golden Tests", "stable", "Run deterministic snapshot checks for generated feature paths, file counts, ModSpec features, and key JSON fields.", ["golden-test"], ["workspace/golden-runs/<run-id>/.agent/golden-report.json"]),
                    Capability("failure_lab", "Failure Injection Lab", "stable", "Generate controlled broken workspaces, inject common artifact failures, then verify audit detection, repair RAG evidence, and safe repair-loop recovery.", ["failure-lab"], ["workspace/failure-lab-runs/<run-id>/.agent/failure-lab-report.json"]),
                    Capability("repair_eval", "Repair Eval Report", "stable", "Quantify self-healing across failure samples: audit detection, relevant repair RAG hits, repair-loop recovery, and final audit recovery.", ["repair-eval"], ["workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.json"]),
                    Capability("quality_gate", "Quality Gate", "stable", "Run doctor, compile, unittest, schema, examples, eval smoke, golden tests, failure lab, repair eval, and optional build smoke.", ["quality-gate"], ["workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.json"]),
                    Capability("doctor", "Environment Doctor", "stable", "Diagnose local Python, Java, template, workspace, docs, and CI setup.", ["doctor"], ["workspace/doctor-runs/<run-id>/.agent/doctor-report.json"]),
                    Capability("showcase", "Showcase Report", "stable", "Run an offline demo flow and write a consolidated report.", ["showcase"], ["workspace/showcase-runs/<run-id>/.agent/showcase-report.json"]),
                    Capability("portfolio_demo", "Portfolio Demo", "stable", "Run doctor, showcase, dashboard, LLM eval report, Web Demo smoke, and capability matrix as one offline demo flow.", ["portfolio-demo"], ["workspace/portfolio-runs/<run-id>/.agent/portfolio-demo-report.json"]),
                    Capability("portfolio_release_package", "Portfolio Release Package", "stable", "Provide a V5.0 one-command demo script, README entry, architecture diagrams, screenshot checklist, and curated demo cases for public presentation.", ["scripts/v5_portfolio_demo.ps1"], ["README.md", "docs/portfolio-release.md", "docs/architecture.md", "docs/demo-cases.md", "docs/screenshots.md"]),
                    Capability("web_dashboard", "Web Demo Dashboard", "stable", "Generate a local static HTML dashboard that visualizes showcase, capability, and RAG reports.", ["dashboard"], ["workspace/dashboard-runs/<run-id>/index.html", "workspace/dashboard-runs/<run-id>/.agent/dashboard-data.json"]),
                    Capability("interactive_web_demo", "Interactive Web Demo Dashboard", "stable", "Start a local no-dependency Web server where users can enter prompts, choose rules/mock/real LLM planners, and inspect ModSpec, generated files, audit/build/eval results, and agent traces.", ["web-demo"], ["http://127.0.0.1:8765/", "workspace/v35-web-demo-*"]),
                    Capability("web_demo_modify", "Web Demo Modify Flow", "stable", "List existing generated workspaces, load their ModSpec snapshots, run agent modify requests, and display add/update/skip results plus ModSpec diffs.", ["web-demo"], [".agent/modspec.json", ".agent/modify-summary.json", ".agent/agent-run.json"]),
                    Capability("web_demo_live_logs", "Web Demo Live Run Logs", "stable", "Run Web Demo generate/modify actions as background jobs, poll live status, and display run logs plus Gradle build stdout/stderr tails.", ["web-demo"], [".agent/logs/gradle-build.log", ".agent/logs/gradle-build.stdout.log", ".agent/logs/gradle-build.stderr.log"]),
                    Capability("web_demo_knowledge_browser", "Web Demo RAG Knowledge Browser", "stable", "Browse bundled NeoForge RAG knowledge entries and filter them by query, category, capability, and tag inside the Web Demo.", ["web-demo"], ["GET /api/knowledge"]),
                    Capability("web_demo_self_healing", "Web Demo Self-Healing View", "stable", "Display repair-agent status, root causes, safe repair-loop attempts, and repair artifacts in the interactive Web Demo.", ["web-demo"], [".agent/agent-repair-plan.json", ".agent/repair-loop-report.json"]),
                    Capability("web_demo_repair_rag", "Web Demo Repair RAG View", "stable", "Display repair RAG queries, retrieved knowledge hits, and root-cause/action/knowledge mappings in the Self-Healing tab.", ["web-demo"], [".agent/repair-rag-context.json"]),
                    Capability("content_coverage_dashboard", "Content Coverage Dashboard", "stable", "Render generated-content coverage from default eval and golden expectations in the Web dashboard.", ["dashboard"], ["workspace/dashboard-runs/<run-id>/.agent/dashboard-data.json"]),
                    Capability("multi_agent_dashboard", "Multi-Agent Dashboard", "stable", "Render per-agent role traces, decisions, inputs, outputs, and prompt trace links in the Web dashboard.", ["dashboard"], ["workspace/dashboard-runs/<run-id>/index.html"]),
                    Capability("dashboard_repair_summary", "Dashboard Repair Summary", "stable", "Render self-healing repair metrics and artifact links in the static dashboard report.", ["dashboard"], ["workspace/dashboard-runs/<run-id>/.agent/dashboard-data.json"]),
                    Capability("dashboard_repair_rag", "Dashboard Repair RAG Mapping", "stable", "Render repair RAG query, knowledge hits, and deterministic root-cause to repair-action evidence mapping.", ["dashboard"], ["workspace/dashboard-runs/<run-id>/.agent/dashboard-data.json"]),
                    Capability("rag_hit_dashboard", "RAG Hit Dashboard", "stable", "Render RAG hit categories, capabilities, and planner-used knowledge in the Web dashboard.", ["dashboard"], ["workspace/dashboard-runs/<run-id>/.agent/dashboard-data.json"]),
                    Capability("dashboard_rag_citation_chain", "Dashboard RAG Citation Chain", "stable", "Render decision-level planner and repair knowledge references so each RAG-backed decision can be traced to bundled knowledge ids.", ["dashboard"], ["workspace/dashboard-runs/<run-id>/.agent/dashboard-data.json"]),
                    Capability("dashboard_resource_preview", "Dashboard Resource Preview", "stable", "Render V8 texture atlas, resource quality reports, model variant counts, and schematic structure previews from generated workspaces.", ["dashboard"], ["workspace/dashboard-runs/<run-id>/index.html"]),
                    Capability("capabilities", "Capability Matrix", "stable", "Export the supported project capability matrix as JSON and Markdown.", ["capabilities"], ["workspace/capability-runs/<run-id>/.agent/capabilities.json"]),
                    Capability("tools_manifest", "Tool Manifest", "stable", "Export internal CLI capabilities as machine-readable tool schemas with inputs, artifacts, side effects, and safety boundaries for Function Calling or future MCP wrapping.", ["tools-manifest"], ["workspace/tool-manifest-runs/<run-id>/.agent/tools-manifest.json", "workspace/tool-manifest-runs/<run-id>/.agent/tools-manifest.md"]),
                    Capability("knowledge_query", "NeoForge Knowledge Query", "stable", "Query bundled NeoForge knowledge snippets and write RAG retrieval reports.", ["knowledge query"], ["workspace/knowledge-runs/<run-id>/.agent/rag-query.json"]),
                    Capability("knowledge_categories", "Knowledge Categories", "stable", "Group bundled NeoForge knowledge by architecture, assets, behavior, content, data, worldgen, audit, resources, and limits.", ["knowledge query"], ["workspace/knowledge-runs/<run-id>/.agent/rag-query.json"]),
                ],
            ),
            CapabilitySection(
                identifier="content",
                title="Generated Content",
                summary="Deterministic Java and JSON output generated from ModSpec.",
                capabilities=[
                    Capability("item", "Item", "stable", "Generate item registry, model, language, and placeholder resources."),
                    Capability("block", "Block", "stable", "Generate placeable blocks with blockstates, models, item models, loot, and language entries."),
                    Capability("block_variants", "Block Variants", "stable", "Generate stairs, slabs, walls, buttons, pressure plates, fences, fence gates, doors, and trapdoors from block_kind declarations."),
                    Capability("interactive_blocks", "Simple Interactive Blocks", "stable", "Generate vanilla interactive block subclasses such as ButtonBlock, PressurePlateBlock, DoorBlock, and TrapDoorBlock without free-form Java."),
                    Capability("machine", "Machine Block", "stable", "Generate BlockEntity-backed machine blocks with inventory slots, energy/progress fields, and right-click menu opening."),
                    Capability("block_entity_gui", "BlockEntity GUI", "stable", "Generate machine BlockEntity, AbstractContainerMenu, client Screen, RegisterMenuScreensEvent wiring, and ContainerData synchronization."),
                    Capability("machine_progress_energy", "Machine Progress And Energy", "stable", "Generate deterministic progress bars, energy meters, server tick updates, and synced data access for machine screens."),
                    Capability("machine_gui_harvest_target", "Machine GUI Harvest Target", "experimental", "Track advanced machine GUI and BlockEntity behavior as the first capability family to prove the Free-Code Lab -> harvest candidate -> deterministic generator upgrade loop.", ["agent lab-generate \"Add an advanced machine GUI...\"", "generate-from-spec examples/machine_ruby_compressor.json"], ["workspace/free-code-lab-runs/<run-id>/.agent/harvest-candidate.json", "examples/machine_ruby_compressor.json"]),
                    Capability("entity", "Entity / Mob", "stable", "Generate custom mob EntityType registrations, Java entity classes, client renderer wiring, entity textures, language entries, and summonable ids."),
                    Capability("entity_attributes", "Entity Attributes", "stable", "Declare max health, movement speed, attack damage, armor, follow range, knockback resistance, size, tracking range, and XP reward."),
                    Capability("entity_loot_spawn", "Entity Loot And Spawn", "stable", "Generate entity loot tables and NeoForge add_spawns biome modifiers from structured drop and spawn declarations."),
                    Capability("entity_ai_goals", "Entity AI Goals", "stable", "Generate controlled FloatGoal, MeleeAttackGoal, stroll, look, hurt-by-target, and target-player goal templates."),
                    Capability("ore", "Ore", "stable", "Generate ore blocks with drops, tags, loot, and optional worldgen."),
                    Capability("food", "Food", "stable", "Generate edible items with nutrition, saturation, and optional effects."),
                    Capability("sword", "Sword", "stable", "Generate sword items and optional on-hit behavior classes."),
                    Capability("tool", "Tool", "stable", "Generate pickaxe, axe, shovel, and hoe items with material-based tool properties."),
                    Capability("armor", "Armor", "stable", "Generate helmet, chestplate, leggings, and boots with material-based armor properties."),
                    Capability("equipment_sets", "Equipment Sets", "stable", "Expand ruby tool and armor set requests into full playable equipment chains.", ["generate \"... ruby tool set ...\"", "generate \"... ruby armor set ...\""]),
                    Capability("equipment_recipes", "Equipment Recipes", "stable", "Automatically generate shaped crafting recipes for ruby swords, tools, and armor pieces."),
                    Capability("progression_dsl", "Progression / Gameplay Loop DSL", "stable", "Declare an auditable gameplay route across ore, materials, machine processing, equipment, entity drops, structure loot, and dimension entry without free-form Java.", ["generate-from-spec examples/progression_gameplay_loop.json"], [".agent/progression-report.json", ".agent/progression-report.md"]),
                    Capability("progression_report", "Progression Evidence Report", "stable", "Write V7 route coverage, stage links, missing references, and entry-to-end reachability as JSON and Markdown evidence.", ["audit"], [".agent/progression-report.json"]),
                    Capability("balance_planner", "Recipe / Loot / Balance Planner", "stable", "Plan recipes, missing recipe suggestions, item rarity, entity drop chances, machine timing, energy costs, and loot weights as a report-only economy layer.", ["generate-from-spec examples/balance_gameplay_loop.json"], [".agent/balance-report.json", ".agent/balance-report.md"]),
                    Capability("economy_report", "Playable Economy Evidence Report", "stable", "Write V7.1 balance coverage, rarity assignments, machine balance rules, and loot/recipe review statuses for inspection.", ["audit"], [".agent/balance-report.json"]),
                    Capability("quest_dsl", "Quest / Advancement / Guide DSL", "stable", "Declare player-facing quest chains that target a progression or define structured tasks without free-form Java.", ["generate-from-spec examples/quest_guide_gameplay_loop.json"], [".agent/quest-report.json", ".agent/guidebook.md"]),
                    Capability("advancement_generation", "Advancement Generation", "stable", "Generate Minecraft advancement JSON for obtain, craft, mine, machine, kill, dimension, structure, and milestone quest tasks.", ["audit"], ["src/main/resources/data/<modid>/advancement/<quest>/<task>.json"]),
                    Capability("guidebook_generation", "Guidebook Generation", "stable", "Generate a readable Markdown guidebook plus Patchouli-style book, category, and entry JSON from Quest DSL.", ["audit"], [".agent/guidebook.md", "src/main/resources/data/<modid>/patchouli_books/<book>/book.json"]),
                    Capability("recipe", "Recipe", "stable", "Generate shaped and shapeless crafting recipes."),
                    Capability("loot_tag_lang_model", "Assets And Data", "stable", "Generate loot tables, tags, language files, models, blockstates, and pack metadata."),
                    Capability("procedural_textures", "Procedural Textures", "stable", "Generate deterministic 16x16 RGBA PNG textures for item, food, sword, tool, armor, block, machine, entity, and ore features, plus a texture manifest.", artifacts=[".agent/texture-manifest.json"]),
                    Capability("resource_quality_profiles", "Resource Quality Profiles", "stable", "Attach V8 profile metadata to generated textures, including silhouette, shading, palette, readability purpose, and profile ids.", ["generate-from-spec examples/resource_quality_showcase.json"], [".agent/resource-quality-report.json"]),
                    Capability("texture_atlas_preview", "Texture Atlas Preview", "stable", "Write a deterministic PNG atlas under .agent for dashboard-friendly inspection of generated texture profiles.", ["audit"], [".agent/texture-atlas.png"]),
                    Capability("model_variant_report", "Model Variant Report", "stable", "Summarize block_kind model variants such as stairs, slabs, walls, doors, trapdoors, and machine blocks in the V8 resource quality report.", ["audit"], [".agent/resource-quality-report.json"]),
                    Capability("pack_mcmeta", "Pack Metadata", "stable", "Generate and audit src/main/resources/pack.mcmeta."),
                    Capability("controlled_java_extension", "Controlled Java Extension", "experimental", "Generate additive managed Java helper classes from structured ModSpec fields without editing existing sources.", ["generate \"... controlled Java extension ...\""], ["src/main/java/<package>/extension/<ClassName>.java", ".agent/java-extension-report.json", ".agent/java-extension-diff.md"]),
                ],
            ),
            CapabilitySection(
                identifier="behaviors",
                title="Shared Behavior DSL",
                summary="Controlled event-condition-action behavior declarations shared by items, blocks, machines, entities, progressions, and quests.",
                capabilities=[
                    Capability("behavior_dsl", "Behavior DSL", "stable", "Declare shared event-action behavior across item, block, machine, entity, progression, and quest hosts without free-form Java."),
                    Capability("shared_behavior_report", "Shared Behavior Report", "stable", "Write .agent behavior coverage with host counts, compiled/report-only surfaces, trigger counts, combo events, state, resource, cooldown, and chain metrics.", ["audit"], [".agent/behavior-report.json", ".agent/behavior-report.md"]),
                    Capability("behavior_combo_state_resource_chain", "Combo / State / Resource / Chain Rules", "stable", "Represent sequence or all-trigger combos, state predicates, resource costs, cooldown gates, delayed chain events, and follow-up effects in the DSL."),
                    Capability("behavior_report_only_hosts", "Report-Only Semantic Hosts", "stable", "Capture machine, entity, progression, and quest behavior semantics in reports while item/block/sword/ore runtime hooks remain the compiled surface."),
                    Capability("behavior_actions", "Behavior Actions", "stable", "Generate or report controlled heal, apply_effect, ignite, consume_item, cooldown, spawn_particles, play_sound, state, resource, and chain_event actions."),
                    Capability("behavior_conditions", "Behavior Conditions", "stable", "Gate behavior events with sneaking, health, random_chance, state, resource, cooldown_ready, and combo_ready conditions."),
                    Capability("right_click_heal", "Right Click Heal", "stable", "Item behavior that heals the player, supports cooldown and consume."),
                    Capability("right_click_effect", "Right Click Effect", "stable", "Item behavior that applies a MobEffectInstance, supports duration, amplifier, cooldown, and consume."),
                    Capability("food_effects", "Food Effects", "stable", "Food can apply configured effects with duration, amplifier, and probability."),
                    Capability("sword_ignite", "Sword Ignite", "stable", "Sword on-hit behavior can set the target on fire for configured seconds."),
                ],
            ),
            CapabilitySection(
                identifier="worldgen",
                title="Worldgen",
                summary="Data-driven world generation supported by the deterministic generator.",
                capabilities=[
                    Capability("overworld_ore", "Overworld Underground Ore", "stable", "Generate configured_feature, placed_feature, and biome_modifier JSON for overworld underground ores."),
                    Capability("dimension", "Dimension", "stable", "Generate dimension_type and fixed-biome noise dimension JSON from ModSpec declarations."),
                    Capability("biome", "Biome", "stable", "Generate biome JSON with climate, visual effects, and feature-slot scaffolding."),
                    Capability("world_feature", "World Feature", "stable", "Generate configured_feature, placed_feature, and biome_modifier JSON for V5.4 ore-vein world features."),
                    Capability("structure", "Structure", "stable", "Generate jigsaw structure, structure_set, and template_pool JSON metadata."),
                    Capability("structure_preview", "Structure Preview", "stable", "Generate deterministic schematic PNG previews for declared structures as V8 dashboard evidence.", ["generate-from-spec examples/resource_quality_showcase.json"], [".agent/previews/<structure>.png"]),
                    Capability("structure_set", "Structure Set", "stable", "Generate random_spread structure placement with spacing, separation, salt, and biome constraints."),
                    Capability("loot_pool", "Chest Loot Pool", "stable", "Generate chest loot tables with weighted entries, counts, and random chance conditions."),
                    Capability("world_structure_dsl", "World / Structure DSL", "stable", "Declare dimensions, biomes, world features, structures, ore-vein rules, and loot pools without free-form Java or NBT generation."),
                ],
            ),
            CapabilitySection(
                identifier="planning",
                title="Planning And LLM",
                summary="Planning modes and model integration boundaries.",
                capabilities=[
                    Capability("rules_planner", "Rules Planner", "stable", "Default deterministic planner for supported Chinese and English prompts.", ["--planner rules"]),
                    Capability("mock_llm", "Mock LLM", "stable", "Offline deterministic LLM provider for tests, eval, agent, and showcase.", ["--planner llm --llm-provider mock"]),
                    Capability("openai_compatible", "OpenAI-Compatible LLM", "stable", "Optional real LLM provider that normalizes model output into ModSpec without letting the model write generated Java or JSON assets.", ["--planner llm --llm-provider openai-compatible"]),
                    Capability("llm_provider_abstraction", "Unified LLM Provider Layer", "stable", "Expose mock and OpenAI-compatible providers through one metadata, streaming-event, retry, token-usage, and cost-estimation contract.", ["--planner llm"], [".agent/llm-stability.json", ".agent/prompt-trace.json"]),
                    Capability("llm_engineering_report", "LLM Engineering Report", "stable", "Aggregate prompt traces and LLM stability artifacts into a provider engineering report covering response format, temperature, timeout, retry, token/cost, JSON repair, schema retry, and fallback evidence.", ["llm-engineering-report"], ["workspace/llm-engineering-runs/<run-id>/.agent/llm-engineering-report.json", "workspace/llm-engineering-runs/<run-id>/.agent/llm-engineering-report.md"]),
                    Capability("llm_provider_config_check", "LLM Provider Config Check", "stable", "Doctor checks OpenAI-compatible provider environment variables without calling the network or exposing secrets.", ["doctor"], ["workspace/doctor-runs/<run-id>/.agent/doctor-report.json"]),
                    Capability("real_llm_health_check", "Real LLM Health Check", "stable", "Inspect OpenAI-compatible provider readiness before real-model planning and recommend rules fallback when configuration is missing or unsafe.", ["doctor", "agent generate --llm-provider openai-compatible"], [".agent/llm-stability.json"]),
                    Capability("llm_json_repair", "LLM JSON Repair", "stable", "Repair common real-model JSON issues such as Markdown fences, leading prose, balanced JSON extraction, and trailing commas before normalization.", ["--planner llm --llm-provider openai-compatible"], [".agent/llm-stability.json"]),
                    Capability("llm_retry", "LLM Retry", "stable", "Retry provider calls and malformed JSON planner responses while preserving deterministic ModSpec validation boundaries.", ["--planner llm --llm-provider openai-compatible"], [".agent/llm-stability.json"]),
                    Capability("llm_schema_retry", "LLM Schema Retry", "stable", "Retry real LLM planning when parsed JSON fails ModSpec validation, feeding validator errors back into the next constrained JSON attempt.", ["--planner llm --llm-provider openai-compatible"], [".agent/llm-stability.json"]),
                    Capability("llm_rules_fallback", "LLM Rules Fallback", "stable", "Fall back to deterministic rules planning when real LLM provider health or schema validation fails, while preserving warnings and trace artifacts.", ["agent generate", "agent modify", "generate"], [".agent/agent-run.json", ".agent/prompt-trace.json"]),
                    Capability("llm_eval_preflight", "LLM Eval Preflight", "stable", "Inspect real LLM provider configuration before candidate eval and skip safely when credentials or model are missing unless --require-real is used.", ["llm-eval-report"], ["workspace/llm-eval-runs/<run-id>/.agent/llm-eval-report.json"]),
                    Capability("auto_planner", "Auto Planner", "stable", "Try rules first and fall back to LLM when rules output appears incomplete.", ["--planner auto"]),
                    Capability("constrained_llm", "Constrained LLM Boundary", "stable", "LLM produces ModSpec by default; Direct Code Lane requires structured patch JSON plus reviewer, audit, build, and rollback gates.", notes=["No free-form diffs or unbounded repo edits."]),
                    Capability("java_extension_sandbox", "Java Extension Sandbox", "experimental", "Allow LLMs to request only structured java_extension specs: class_name, safe imports, String methods, purpose, and explanation.", notes=["No package lines, imports outside allowlist, Gradle edits, or existing-source patches."]),
                    Capability("direct_code_patch_plan", "Direct Code Patch Plan", "experimental", "Allow LLMs to request write_file or replace_text changes as structured JSON under approved generated-workspace roots.", ["agent generate --code-lane hybrid", "agent modify --code-lane hybrid"], [".agent/direct-code-plan.json", ".agent/direct-code-plan.md"]),
                    Capability("capability_harvest_loop", "Capability Harvest Loop", "experimental", "Use Free-Code Lab for generate gaps, require audit/build/manual runtime evidence, then promote only reviewed patterns back into stable ModSpec, DSL, generator, audit, repair, and regression tests.", ["agent lab-generate", "harvest-report"], ["workspace/free-code-lab-runs/<run-id>/.agent/harvest-candidate.json", "workspace/harvest-runs/<run-id>/.agent/harvest-report.json"]),
                    Capability("rag_planner_context", "Planner RAG Context", "stable", "Inject bundled NeoForge knowledge snippets into LLM planner prompts and persist retrieval artifacts.", artifacts=[".agent/rag-context.json", ".agent/rag-context.md"]),
                    Capability("rag_used_knowledge", "Planner Used Knowledge", "stable", "Persist the exact retrieved knowledge ids, categories, capabilities, and scores used by each LLM planner run.", artifacts=[".agent/llm-used-knowledge.json", ".agent/prompt-trace.json"]),
                    Capability("explainable_rag_citations", "Explainable RAG Citations", "stable", "Attach knowledge ids and compact reference metadata to planner and repair decisions, then surface the same citation chain in agent reports and dashboards.", artifacts=[".agent/agent-run.json", ".agent/agent-decisions.md", "workspace/dashboard-runs/<run-id>/.agent/dashboard-data.json"]),
                    Capability("agent_prompt_trace", "Agent Prompt Trace", "stable", "Record planner role inputs, normalized ModSpec output, warnings, and LLM raw JSON for replayable debugging.", artifacts=[".agent/prompt-trace.json"]),
                ],
            ),
            CapabilitySection(
                identifier="reliability",
                title="Reliability And Verification",
                summary="Validation, testing, CI, and reporting layers around generation.",
                capabilities=[
                    Capability("validator", "ModSpec Validator", "stable", "Validate IDs, references, behavior attachment, ranges, resource locations, and worldgen constraints."),
                    Capability("auditor", "Workspace Auditor", "stable", "Verify generated files, registrations, language keys, recipes, behavior classes, and worldgen JSON."),
                    Capability("java_extension_audit", "Java Extension Audit", "experimental", "Audit controlled Java extension class paths, package declarations, methods, report entries, and forbidden tokens.", ["audit"], [".agent/audit-report.json", ".agent/java-extension-report.json"]),
                    Capability("java_extension_build_gate", "Java Extension Build Gate", "experimental", "Record the Gradle build result inside the V6.1 Java extension report so formal acceptance is tied to compiler proof.", ["generate-from-spec --build --audit"], [".agent/java-extension-report.json", ".agent/logs/gradle-build.log"]),
                    Capability("java_extension_diff_report", "Java Extension Diff Report", "experimental", "Write a reviewable new-file diff for every generated controlled extension class.", ["generate-from-spec"], [".agent/java-extension-diff.md"]),
                    Capability("java_extension_rollback_report", "Java Extension Rollback Report", "experimental", "Write managed-file rollback instructions and mark rollback as recommended when the build gate fails.", ["generate-from-spec --build"], [".agent/java-extension-rollback-report.json", ".agent/java-extension-rollback-report.md"]),
                    Capability("direct_code_review_gate", "Direct Code Review Gate", "experimental", "Review Direct Code paths, operation types, risky tokens, Gradle risk, Java package declarations, and rollback snapshot coverage before applying patches.", ["agent generate --code-lane direct"], [".agent/direct-code-review.json"]),
                    Capability("direct_code_build_audit_gate", "Direct Code Build And Audit Gate", "experimental", "Force audit and Gradle build after Direct Code patches; failed gates mark rollback as recommended.", ["agent generate --code-lane direct --no-build"], [".agent/direct-code-report.json", ".agent/direct-code-rollback-report.json", ".agent/logs/gradle-build.log"]),
                    Capability("free_code_lab_safety_gate", "Free-Code Lab Safety Gate", "experimental", "Constrain lab patches to copied generated workspaces, reject unsafe paths and risky content, write manual runtime checklist evidence, and mark failed audit/build samples as non-harvestable.", ["agent lab-generate --build"], ["workspace/free-code-lab-runs/<run-id>/.agent/free-code-report.json", "workspace/free-code-lab-runs/<run-id>/.agent/manual-runtime-checklist.md", "workspace/free-code-lab-runs/<run-id>/.agent/harvest-candidate.json"]),
                    Capability("texture_audit", "Texture Audit", "stable", "Verify generated texture files exist and are valid 16x16 RGBA PNG assets."),
                    Capability("resource_quality_audit", "Resource Quality Audit", "stable", "Verify V8 resource-quality-report.json, texture atlas PNG, and generated structure preview PNG paths.", ["audit"], [".agent/audit-report.json", ".agent/resource-quality-report.json"]),
                    Capability("unittest", "Automated Unit Tests", "stable", "Standard-library regression suite without pytest dependency.", ["python -m unittest discover -s tests -v"]),
                    Capability("golden_snapshot_checks", "Golden Snapshot Checks", "stable", "Check golden generated file paths, counts, ModSpec feature ids, and JSON fields for item, block, ore, food, sword, tool, armor, recipes, worldgen, and block variants.", ["golden-test"]),
                    Capability("rag_eval_metrics", "RAG Eval Metrics", "stable", "Measure Recall@1, Recall@K, MRR, expected category/capability hits, and query-rewrite delta across fixed local RAG cases.", ["rag-eval"], ["workspace/rag-eval-runs/<run-id>/.agent/rag-eval-report.json"]),
                    Capability("ci", "GitHub Actions CI", "stable", "Run default quality gate in GitHub Actions and upload .agent reports.", artifacts=[".github/workflows/quality-gate.yml"]),
                    Capability("doctor_quality_gate", "Doctor In Quality Gate", "stable", "Quality gate includes environment doctor preflight by default.", ["quality-gate"]),
                    Capability("showcase_report", "Showcase Report", "stable", "Consolidated report for current agent capabilities.", ["showcase"]),
                    Capability("agent_decision_log", "Agent Decision Log", "stable", "Write role decisions and rationales into Markdown for trace review.", artifacts=[".agent/agent-decisions.md"]),
                    Capability("repair_plan", "Repair Plan", "stable", "Classify build/audit failures into deterministic repair actions without directly editing generated code.", artifacts=[".agent/agent-repair-plan.json", ".agent/agent-repair-plan.md"]),
                    Capability("safe_repair_execution", "Safe Repair Execution", "stable", "Automatically regenerate only managed files from .agent/modspec.json and rerun requested audit/build checks when repair is enabled.", ["agent generate", "agent modify", "repair-loop"], [".agent/repair-loop-report.json"]),
                    Capability("self_healing_demo", "Self-Healing Agent Demo", "stable", "Surface the repair agent's safe execution path as JSON, Markdown, Web Demo, and dashboard views.", ["agent generate", "web-demo", "dashboard"], [".agent/agent-repair-plan.json", ".agent/repair-loop-report.json"]),
                ],
            ),
        ]

    def _limitations(self) -> list[str]:
        return [
            "V8 resource profiles and preview atlases improve generated-art inspectability, but they are still deterministic placeholder assets rather than final authored art.",
            "The bundled RAG knowledge base is curated and local; it is not a live mirror of official NeoForge documentation.",
            "V5.4 supports template-based dimensions, biomes, ore-vein world features, jigsaw structure metadata, structure sets, and chest loot pools; custom terrain noise, authored NBT structures, multi-dimension gameplay logic, and complex placement processors remain out of scope.",
            "V7.1 balance planning is report-only: it proposes recipe, loot, rarity, machine timing, energy, and weight settings, but does not replace in-game economy playtests.",
            "V7.2 quest and guidebook generation is data-driven: it emits advancement JSON and Patchouli-style guide structures, but it does not implement custom quest runtime logic or require Patchouli as a Gradle dependency.",
            "V6.1 controlled Java extension is additive only: it can generate managed classes under the extension package, but it cannot patch existing source files or bypass validator, audit, build gate, diff review, or rollback reporting.",
            "Direct Code Lane is a structured patch lane for generated workspaces only; it is not an unbounded coding agent and cannot modify this tool's source tree, .git, Gradle wrapper jars, build outputs, or paths outside the workspace.",
            "Free-Code Lab is an isolated experiment lane: it may explore generate gaps in copied workspaces, but it never writes changes back into the stable generator without manual harvest, tests, and deterministic template work.",
            "Machine GUI generation is template-based: BlockEntity, menu, screen, progress, energy, and slots are supported for declared machine features, while arbitrary custom GUI logic remains out of scope.",
            "Entity generation is template-based: simple mob attributes, loot, spawn modifiers, and basic AI goals are supported, while complex animation/model systems, advanced pathfinding, boss phases, multi-block gameplay systems, and arbitrary Java snippets remain out of scope.",
            "Audit verifies generated structure and references, but does not replace manual in-game playtesting.",
            "Default quality gate skips Gradle build smoke unless --build-smoke is passed.",
        ]

    def _render_markdown(self, result: CapabilityMatrixResult) -> str:
        lines = [
            "# Capability Matrix",
            "",
            f"Version: `{result.version}`",
            f"Run ID: `{result.run_id}`",
            "",
            "## Project",
            "",
        ]
        for key, value in result.project.items():
            lines.append(f"- `{key}`: {value}")
        for section in result.sections:
            lines.extend(["", f"## {section.title}", "", section.summary, ""])
            for capability in section.capabilities:
                lines.append(f"- `{capability.identifier}` `{capability.status}`: {capability.summary}")
                if capability.commands:
                    lines.append(f"  - commands: `{', '.join(capability.commands)}`")
                if capability.artifacts:
                    lines.append(f"  - artifacts: `{', '.join(capability.artifacts)}`")
                for note in capability.notes:
                    lines.append(f"  - note: {note}")
        lines.extend(["", "## Limitations", ""])
        lines.extend(f"- {limitation}" for limitation in result.limitations)
        lines.append("")
        return "\n".join(lines)
