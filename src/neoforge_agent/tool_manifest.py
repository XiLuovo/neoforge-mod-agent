from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .tools import ensure_directory, write_json, write_text


MANIFEST_VERSION = "1.0"


@dataclass(slots=True)
class ToolContract:
    name: str
    title: str
    category: str
    description: str
    cli_mapping: str
    input_schema: dict[str, Any]
    output_artifacts: list[str] = field(default_factory=list)
    safety_boundaries: list[str] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)
    maps_to: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "cli_mapping": self.cli_mapping,
            "input_schema": dict(self.input_schema),
            "output_artifacts": list(self.output_artifacts),
            "safety_boundaries": list(self.safety_boundaries),
            "side_effects": list(self.side_effects),
            "maps_to": list(self.maps_to),
        }


@dataclass(slots=True)
class ToolManifestResult:
    success: bool
    run_id: str
    version: str
    manifest_version: str
    tools: list[ToolContract]
    limitations: list[str]
    report_dir: Path
    tools_manifest_json_path: Path
    tools_manifest_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "version": self.version,
            "manifest_version": self.manifest_version,
            "tools": [tool.to_dict() for tool in self.tools],
            "tools_count": len(self.tools),
            "limitations": list(self.limitations),
            "report_dir": str(self.report_dir),
            "tools_manifest_json_path": str(self.tools_manifest_json_path),
            "tools_manifest_md_path": str(self.tools_manifest_md_path),
        }


class ToolManifestRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def build(self, *, run_name: str | None = None) -> ToolManifestResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        report_dir = ensure_directory(self.config.workspace_root / "tool-manifest-runs" / run_id / ".agent")
        report_json = report_dir / "tools-manifest.json"
        report_md = report_dir / "tools-manifest.md"
        result = ToolManifestResult(
            success=True,
            run_id=run_id,
            version=self._project_version(),
            manifest_version=MANIFEST_VERSION,
            tools=self._tools(),
            limitations=self._limitations(),
            report_dir=report_dir,
            tools_manifest_json_path=report_json,
            tools_manifest_md_path=report_md,
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

    def _tools(self) -> list[ToolContract]:
        return [
            ToolContract(
                name="agent_generate",
                title="Agent Generate",
                category="generation",
                description="Run planner, reviewer, executor, auditor, repair, and trace roles for a new NeoForge workspace.",
                cli_mapping="agent generate",
                input_schema=_object_schema(
                    required=["request"],
                    properties={
                        "request": _string("Natural language mod request."),
                        "planner": _enum(["rules", "llm", "decomposed", "auto"], "Planner role implementation."),
                        "llm_provider": _enum(["mock", "openai-compatible"], "LLM provider used when planner needs a model."),
                        "require_llm": _boolean("Fail instead of falling back to rules when real LLM planning fails."),
                        "code_lane": _enum(["hybrid", "modspec", "direct"], "Agent code lane: ModSpec-first hybrid, ModSpec only, or experimental audited Direct Code patch."),
                        "workspace_name": _string("Optional workspace folder name."),
                        "overwrite": _boolean("Replace an existing generated workspace with the same name."),
                        "run_audit": _boolean("Run workspace audit after generation."),
                        "run_build": _boolean("Run Gradle build after generation."),
                        "run_repair": _boolean("Run repair analysis when checks fail."),
                    },
                ),
                output_artifacts=[
                    ".agent/modspec.json",
                    ".agent/agent-run.json",
                    ".agent/agent-decisions.md",
                    ".agent/prompt-trace.json",
                    ".agent/audit-report.json",
                    ".agent/repair-loop-report.json",
                    ".agent/direct-code-plan.json",
                    ".agent/direct-code-review.json",
                    ".agent/direct-code-diff.md",
                    ".agent/direct-code-report.json",
                    ".agent/direct-code-rollback-report.json",
                ],
                safety_boundaries=[
                    "Writes inside a generated workspace under the configured workspace root.",
                    "LLM output is normalized into ModSpec, optional structured Direct Code plan, or repair intent before file generation.",
                    "Direct Code is an experimental opt-in lane; plans are reviewed for path ownership, operation type, risky tokens, snapshots, build/audit gates, and rollback evidence before the run is treated as accepted.",
                ],
                side_effects=["Creates or overwrites a generated workspace when overwrite is true."],
                maps_to=["Function Calling tool", "future MCP tool"],
            ),
            ToolContract(
                name="agent_develop",
                title="Agent Develop",
                category="generation",
                description="Run the full Minecraft mod coding-agent loop: plan, review, retrieve context, generate, audit/build, repair, and trace a new workspace.",
                cli_mapping="agent develop",
                input_schema=_object_schema(
                    required=["request"],
                    properties={
                        "request": _string("Natural language mod development goal."),
                        "planner": _enum(["rules", "llm", "decomposed", "auto"], "Planner role implementation."),
                        "llm_provider": _enum(["mock", "openai-compatible"], "LLM provider used when planner needs a model."),
                        "workspace_name": _string("Optional workspace folder name."),
                        "run_audit": _boolean("Run workspace audit after generation."),
                        "run_build": _boolean("Run Gradle build after generation."),
                        "run_repair": _boolean("Run repair analysis when checks fail."),
                        "max_iterations": _integer("Maximum repair iterations after failed checks.", minimum=1),
                    },
                ),
                output_artifacts=[
                    ".agent/agent-run.json",
                    ".agent/tool-call-trace.json",
                    ".agent/prompt-trace.json",
                    ".agent/rag-context.json",
                    ".agent/reviewer-report.json",
                    ".agent/audit-report.json",
                    ".agent/repair-loop-report.json",
                ],
                safety_boundaries=[
                    "Keeps ModSpec as the first intent contract before generation.",
                    "Repair iterations are bounded by max_iterations and stay inside generated managed files unless an experimental reviewed Direct Code plan is selected.",
                ],
                side_effects=["Creates or overwrites a generated workspace when overwrite is true."],
                maps_to=["Function Calling tool", "future MCP tool"],
            ),
            ToolContract(
                name="agent_modify",
                title="Agent Modify",
                category="generation",
                description="Run the multi-role workflow for a controlled change to an existing generated workspace.",
                cli_mapping="agent modify",
                input_schema=_object_schema(
                    required=["workspace", "change_request"],
                    properties={
                        "workspace": _string("Workspace path or workspace name."),
                        "change_request": _string("Natural language modification request."),
                        "planner": _enum(["rules", "llm", "decomposed", "auto"], "Planner role implementation."),
                        "llm_provider": _enum(["mock", "openai-compatible"], "LLM provider used when planner needs a model."),
                        "require_llm": _boolean("Fail instead of falling back to rules when real LLM planning fails."),
                        "code_lane": _enum(["hybrid", "modspec", "direct"], "Agent code lane: ModSpec-first hybrid, ModSpec only, or experimental audited Direct Code patch."),
                        "run_audit": _boolean("Run workspace audit after modification."),
                        "run_build": _boolean("Run Gradle build after modification."),
                        "run_repair": _boolean("Run repair analysis when checks fail."),
                    },
                ),
                output_artifacts=[
                    ".agent/modspec.before.json",
                    ".agent/modspec.after.json",
                    ".agent/patch-agent-plan.json",
                    ".agent/patch-agent-report.json",
                    ".agent/patch-agent-rollback-report.json",
                    ".agent/agent-run.json",
                    ".agent/direct-code-plan.json",
                    ".agent/direct-code-review.json",
                    ".agent/direct-code-diff.md",
                    ".agent/direct-code-report.json",
                    ".agent/direct-code-rollback-report.json",
                ],
                safety_boundaries=[
                    "When the experimental Direct Code lane is selected, only generated workspace files under approved Direct Code roots are eligible for mutation.",
                    "Patch plans are structured JSON, reviewed before execution, snapshotted before writes, checked by audit/build gates, and recorded with rollback evidence.",
                    "The original ModSpec snapshot is preserved for comparison.",
                ],
                side_effects=["Mutates an existing generated workspace within controlled file boundaries."],
                maps_to=["Function Calling tool", "future MCP tool"],
            ),
            ToolContract(
                name="agent_repair",
                title="Agent Repair",
                category="recovery",
                description="Observe an existing workspace, retrieve repair knowledge, run bounded safe repair iterations, and persist trace evidence.",
                cli_mapping="agent repair",
                input_schema=_object_schema(
                    required=["workspace"],
                    properties={
                        "workspace": _string("Workspace path or workspace name."),
                        "goal": _string("Natural language repair goal."),
                        "llm_provider": _enum(["mock", "openai-compatible"], "LLM provider label recorded in trace evidence."),
                        "max_iterations": _integer("Maximum repair-loop iterations.", minimum=1),
                        "run_audit": _boolean("Run workspace audit during repair checks."),
                        "run_build": _boolean("Run Gradle build during repair checks."),
                    },
                ),
                output_artifacts=[
                    ".agent/agent-run.json",
                    ".agent/tool-call-trace.json",
                    ".agent/agent-repair-plan.json",
                    ".agent/repair-rag-context.json",
                    ".agent/repair-loop-report.json",
                    ".agent/audit-report.json",
                ],
                safety_boundaries=[
                    "Uses .agent/modspec.json as the source of truth for managed-file regeneration.",
                    "Does not modify user-owned files outside generated workspace ownership boundaries.",
                ],
                side_effects=["May rewrite generated managed files during repair attempts."],
                maps_to=["Function Calling tool", "future MCP tool"],
            ),
            ToolContract(
                name="agent_bench",
                title="Agent Bench",
                category="evaluation",
                description="Run eval, failure repair, build/audit, RAG, and workspace-level benchmark aggregation as one coding-agent benchmark command.",
                cli_mapping="agent bench",
                input_schema=_object_schema(
                    properties={
                        "suite": _string("Optional JSON file containing benchmark/eval cases."),
                        "llm_provider": _enum(["mock", "openai-compatible"], "Primary provider to benchmark."),
                        "eval_limit": _integer("Number of eval cases per model run.", minimum=1),
                        "repair_limit": _integer("Number of injected failure repair cases.", minimum=1),
                        "rag_ablation": _boolean("Run paired RAG-on/RAG-off benchmark cases and report deltas."),
                        "repair_holdout": _boolean("Generate seeded randomized repair holdout cases instead of default benchmark cases."),
                        "holdout_seed": _string("Seed for randomized repair holdout case/material selection."),
                        "holdout_limit": _integer("Number of base repair holdout cases before optional RAG pairing.", minimum=1),
                        "run_audit": _boolean("Run workspace audit for benchmark cases."),
                        "run_build": _boolean("Run Gradle build for benchmark cases."),
                    },
                ),
                output_artifacts=[
                    "workspace/benchmark-runs/<run-id>/.agent/benchmark-report.json",
                    "workspace/benchmark-runs/<run-id>/.agent/benchmark-report.md",
                    "workspace/benchmark-runs/<run-id>/.agent/benchmark-report.html",
                ],
                safety_boundaries=[
                    "Reuses local benchmark/eval runners and records skipped real-provider runs instead of hiding configuration failures.",
                    "Aggregates audit/build and optional manual runtime evidence; does not claim automatic Minecraft client/server acceptance.",
                    "Does not mutate project source files; generated benchmark workspaces are isolated under workspace/benchmark-runs.",
                ],
                side_effects=["Creates benchmark run workspaces and report artifacts under the configured workspace root."],
                maps_to=["Function Calling tool", "future MCP tool/resource"],
            ),
            ToolContract(
                name="audit_workspace",
                title="Audit Workspace",
                category="verification",
                description="Check a generated workspace against ModSpec, generation summary, resources, behavior reports, and managed evidence files.",
                cli_mapping="audit",
                input_schema=_object_schema(
                    required=["project"],
                    properties={
                        "project": _string("Workspace path or workspace name."),
                    },
                ),
                output_artifacts=[
                    ".agent/audit-report.json",
                    ".agent/audit-report.md",
                    ".agent/behavior-report.json",
                    ".agent/resource-quality-report.json",
                ],
                safety_boundaries=[
                    "Read-mostly verification command; it writes reports but does not repair files.",
                    "Uses deterministic local rules instead of free-form model judgment.",
                ],
                side_effects=["Writes audit report artifacts under the workspace .agent directory."],
                maps_to=["Function Calling tool", "future MCP tool"],
            ),
            ToolContract(
                name="repair_loop",
                title="Repair Loop",
                category="recovery",
                description="Run safe audit/build checks and regenerate managed files from ModSpec when a known failure can be repaired.",
                cli_mapping="repair-loop",
                input_schema=_object_schema(
                    required=["project"],
                    properties={
                        "project": _string("Workspace path or workspace name."),
                        "max_attempts": _integer("Maximum managed-file regeneration attempts.", minimum=1),
                        "run_audit": _boolean("Run workspace audit inside each repair-loop check."),
                        "run_build": _boolean("Run Gradle build inside each repair-loop check."),
                    },
                ),
                output_artifacts=[
                    ".agent/repair-loop-report.json",
                    ".agent/repair-loop-report.md",
                    ".agent/repair-rag-context.json",
                ],
                safety_boundaries=[
                    "Regenerates from .agent/modspec.json instead of letting the model edit arbitrary files.",
                    "Limits attempts and records each check, action, and final state.",
                    "Build execution is opt-in for slower validation paths.",
                ],
                side_effects=["May rewrite generated managed files during repair attempts."],
                maps_to=["Function Calling tool", "future MCP tool"],
            ),
            ToolContract(
                name="rag_eval",
                title="RAG Eval",
                category="evaluation",
                description="Measure local RAG retrieval quality with Recall@1, Recall@K, MRR, expected category/capability hits, and query rewrite deltas.",
                cli_mapping="rag-eval",
                input_schema=_object_schema(
                    properties={
                        "cases": _string("Optional JSON file containing RAG eval cases."),
                        "run_name": _string("Stable run folder name."),
                        "limit": _integer("Maximum number of snippets to retrieve per query.", minimum=1),
                        "recall_k": _integer("K used for Recall@K and hit-rate checks.", minimum=1),
                    },
                ),
                output_artifacts=[
                    "workspace/rag-eval-runs/<run-id>/.agent/rag-eval-report.json",
                    "workspace/rag-eval-runs/<run-id>/.agent/rag-eval-report.md",
                ],
                safety_boundaries=[
                    "Offline local benchmark; no network or external vector database is required.",
                    "Reports retrieval failures instead of silently treating prompt context as correct.",
                ],
                side_effects=["Writes RAG eval reports under workspace/rag-eval-runs."],
                maps_to=["Function Calling tool", "future MCP resource/tool"],
            ),
            ToolContract(
                name="evidence_chain_report",
                title="Evidence Chain Report",
                category="reporting",
                description="Aggregate stable ModSpec, Behavior DSL, and controlled patch-agent proof into one layered workspace evidence report.",
                cli_mapping="evidence-chain-report",
                input_schema=_object_schema(
                    properties={
                        "run_name": _string("Stable run folder name."),
                        "eval_limit": _integer("Number of stable-layer eval cases.", minimum=1),
                        "repair_limit": _integer("Number of repair cases.", minimum=1),
                    },
                ),
                output_artifacts=[
                    "workspace/evidence-chain-runs/<run-id>/.agent/evidence-chain-report.json",
                    "workspace/evidence-chain-runs/<run-id>/.agent/evidence-chain-report.md",
                ],
                safety_boundaries=[
                    "Aggregates existing local evidence instead of replacing audit/build validation.",
                    "Separates manual runtime evidence from workspace audit/build gates; does not claim automatic Minecraft client/server acceptance.",
                    "Designed for trace and evidence inspection.",
                ],
                side_effects=["Writes evidence-chain report artifacts under workspace/evidence-chain-runs."],
                maps_to=["Function Calling tool", "future MCP tool/resource"],
            ),
        ]

    def _limitations(self) -> list[str]:
        return [
            "This manifest is a local contract for internal CLI capabilities; it is not a running MCP server.",
            "Tool schemas describe safe invocation boundaries but do not grant models direct filesystem access.",
            "Gradle build and real LLM provider calls remain explicit opt-in operations.",
            "Direct Code Lane is available only inside generated workspaces and is constrained by structured patches, path policy, snapshots, audit/build gates, and rollback reporting.",
        ]

    def _render_markdown(self, result: ToolManifestResult) -> str:
        lines = [
            "# Tool Calling Contract",
            "",
            f"- success: `{result.success}`",
            f"- run id: `{result.run_id}`",
            f"- project version: `{result.version}`",
            f"- manifest version: `{result.manifest_version}`",
            f"- tools: `{len(result.tools)}`",
            "",
            "This report describes internal CLI capabilities as tool schemas. It is designed to explain how the project could be wrapped as Function Calling or MCP later without claiming that a full MCP server already exists.",
            "",
            "## Tools",
            "",
        ]
        for tool in result.tools:
            lines.extend(
                [
                    f"### `{tool.name}`",
                    "",
                    f"- title: {tool.title}",
                    f"- category: `{tool.category}`",
                    f"- CLI: `{tool.cli_mapping}`",
                    f"- description: {tool.description}",
                    f"- required inputs: `{', '.join(tool.input_schema.get('required', [])) or 'none'}`",
                    f"- maps to: `{', '.join(tool.maps_to) or 'internal only'}`",
                    "",
                    "Output artifacts:",
                ]
            )
            lines.extend(f"- `{artifact}`" for artifact in tool.output_artifacts)
            lines.append("")
            lines.append("Safety boundaries:")
            lines.extend(f"- {boundary}" for boundary in tool.safety_boundaries)
            if tool.side_effects:
                lines.append("")
                lines.append("Side effects:")
                lines.extend(f"- {effect}" for effect in tool.side_effects)
            lines.append("")
        lines.append("## Limitations")
        lines.append("")
        lines.extend(f"- {item}" for item in result.limitations)
        lines.append("")
        return "\n".join(lines)


def _object_schema(*, properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties or {},
        "required": required or [],
    }


def _string(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _boolean(description: str) -> dict[str, Any]:
    return {"type": "boolean", "description": description}


def _integer(description: str, *, minimum: int | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "integer", "description": description}
    if minimum is not None:
        schema["minimum"] = minimum
    return schema


def _enum(values: list[str], description: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(values), "description": description}
