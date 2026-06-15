from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AppConfig
from .java_extension_generator import SUPPORTED_JAVA_EXTENSION_IMPORTS
from .knowledge_base import NeoForgeKnowledgeBase, expand_knowledge_query, summarize_knowledge_hits
from .llm_client import DEFAULT_LLM_SCHEMA_RETRIES, LLMClient, check_llm_provider_health, get_llm_provider_metadata, inspect_llm_provider_config
from .models import BlockSpec, FoodSpec, ItemSpec, ModSpec, OreSpec, RecipeSpec, SwordSpec
from .schema import get_modspec_schema
from .tools import derive_display_name, derive_package_name, ensure_directory, slugify_mod_id, write_json, write_text
from .validator import validate_mod_spec


SUPPORTED_FEATURE_TYPES = {
    "item",
    "block",
    "machine",
    "entity",
    "dimension",
    "biome",
    "world_feature",
    "structure",
    "loot_pool",
    "java_extension",
    "ore",
    "food",
    "sword",
    "tool",
    "armor",
    "recipe",
    "progression",
    "balance_plan",
    "quest",
}
DECOMPOSED_PLANNER_FEATURE_TYPES = {
    "item",
    "ore",
    "machine",
    "tool",
    "sword",
    "recipe",
    "progression",
}
SUPPORTED_QUEST_TASK_TYPES = {
    "obtain_item",
    "craft_item",
    "mine_block",
    "use_machine",
    "kill_entity",
    "enter_dimension",
    "visit_structure",
    "milestone",
}
SUPPORTED_TOOL_MATERIALS = {"wood", "stone", "copper", "iron", "diamond", "gold", "golden", "netherite", "ruby"}
SUPPORTED_TOOL_TIERS = {"stone", "iron", "diamond", "netherite", "copper", "gold", "wood"}
SUPPORTED_TOOL_TYPES = {"pickaxe", "axe", "shovel", "hoe"}
SUPPORTED_ARMOR_TYPES = {"helmet", "chestplate", "leggings", "boots"}
SUPPORTED_ARMOR_MATERIALS = {"leather", "chainmail", "chain", "copper", "iron", "diamond", "gold", "golden", "netherite", "ruby"}
SUPPORTED_BLOCK_KINDS = {
    "cube",
    "stairs",
    "slab",
    "wall",
    "button",
    "pressure_plate",
    "fence",
    "fence_gate",
    "door",
    "trapdoor",
}
SUPPORTED_MACHINE_KINDS = {"furnace", "compressor", "upgrade_table", "magic_altar", "storage"}
SUPPORTED_ENTITY_KINDS = {"monster", "creature", "pet", "boss", "npc", "ambient"}
SUPPORTED_ENTITY_CATEGORIES = {"monster", "creature", "pet", "boss", "npc", "ambient", "misc"}
SUPPORTED_ENTITY_GOALS = {
    "float",
    "melee_attack",
    "random_stroll",
    "look_at_player",
    "random_look_around",
    "hurt_by_target",
    "target_player",
}
SUPPORTED_ENTITY_ATTACK_TYPES = {"none", "melee"}
SUPPORTED_DIMENSION_TYPES = {"overworld_like", "nether_like", "end_like"}
SUPPORTED_DIMENSION_GENERATORS = {"noise"}
SUPPORTED_WORLD_FEATURE_KINDS = {"ore_vein"}
SUPPORTED_WORLDGEN_STEPS = {
    "raw_generation",
    "lakes",
    "local_modifications",
    "underground_structures",
    "surface_structures",
    "strongholds",
    "underground_ores",
    "underground_decoration",
    "fluid_springs",
    "vegetal_decoration",
    "top_layer_modification",
}
SUPPORTED_STRUCTURE_KINDS = {"jigsaw"}
SUPPORTED_STRUCTURE_STEPS = {"surface_structures", "underground_structures"}
SUPPORTED_TERRAIN_ADAPTATION = {"none", "beard_thin", "beard_box", "bury", "encapsulate"}
SUPPORTED_LOOT_TABLE_KINDS = {"chest"}


@dataclass(slots=True)
class PlannerArtifacts:
    planner_mode: str
    provider: str
    input_text: str
    system_prompt: str = ""
    raw_text: str = ""
    raw_json: dict | None = None
    normalized_json: dict | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    rag_query: str = ""
    rag_query_expansions: list[str] = field(default_factory=list)
    rag_context: str = ""
    rag_hits: list[dict] = field(default_factory=list)
    rag_categories: dict[str, int] = field(default_factory=dict)
    rag_capabilities: dict[str, int] = field(default_factory=dict)
    used_knowledge: list[dict] = field(default_factory=list)
    rag_quality: dict[str, Any] = field(default_factory=dict)
    parse_attempts: list[dict[str, Any]] = field(default_factory=list)
    retry_attempts: int = 0
    schema_retry_attempts: int = 0
    schema_validation_attempts: list[dict[str, Any]] = field(default_factory=list)
    json_repair_applied: bool = False
    provider_config: dict[str, Any] = field(default_factory=dict)
    provider_health: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    completion_usage: dict[str, Any] = field(default_factory=dict)
    completion_attempts: list[dict[str, Any]] = field(default_factory=list)
    decomposed_feature_plan_raw_json: dict | None = None
    decomposed_feature_plan_json: dict | None = None
    decomposed_feature_json_outputs: list[dict[str, Any]] = field(default_factory=list)
    decomposed_composed_raw_json: dict | None = None
    decomposed_bad_raw_outputs: list[dict[str, Any]] = field(default_factory=list)


class LLMPlanningError(RuntimeError):
    def __init__(self, message: str, artifacts: PlannerArtifacts) -> None:
        super().__init__(message)
        self.artifacts = artifacts


def plan_with_llm(
    prompt: str,
    client: LLMClient,
    *,
    language: str = "zh_cn",
    config: AppConfig | None = None,
) -> tuple[ModSpec, PlannerArtifacts]:
    config = config or AppConfig.default()
    rag_query, rag_context, rag_hits = _retrieve_rag_context(prompt)
    rag_summary = summarize_knowledge_hits(rag_hits)
    system_prompt = _build_system_prompt(language, rag_context=rag_context)
    artifacts = PlannerArtifacts(
        planner_mode="llm",
        provider=getattr(client, "provider_name", "unknown"),
        input_text=prompt,
        system_prompt=system_prompt,
        rag_query=rag_query,
        rag_query_expansions=expand_knowledge_query(rag_query),
        rag_context=rag_context,
        rag_hits=rag_hits,
        rag_categories=rag_summary["categories"],
        rag_capabilities=rag_summary["capabilities"],
        used_knowledge=_used_knowledge(rag_hits),
        rag_quality=_rag_quality(rag_hits, rag_query),
        provider_config=_provider_config_for_artifact(getattr(client, "provider_name", "unknown")),
        provider_health=_provider_health_for_artifact(getattr(client, "provider_name", "unknown")),
        provider_metadata=_provider_metadata_for_artifact(getattr(client, "provider_name", "unknown")),
    )
    retry_prompt = prompt
    for schema_attempt in range(1, _llm_schema_attempts() + 1):
        raw_json = _complete_json_with_repair(
            client,
            system_prompt,
            retry_prompt,
            artifacts,
            invalid_error="LLM planner returned invalid JSON.",
        )

        normalized, warnings = _normalize_llm_output(raw_json, prompt, config)
        artifacts.normalized_json = normalized
        artifacts.warnings.extend(warnings)

        spec = ModSpec.from_dict(normalized)
        report = validate_mod_spec(spec, config)
        validation_attempt = _schema_validation_attempt(schema_attempt, report)
        artifacts.schema_validation_attempts.append(validation_attempt)
        if report.is_valid:
            artifacts.warnings.extend(issue.message for issue in report.warnings)
            return spec, artifacts

        errors = [issue.message for issue in report.errors]
        artifacts.warnings.extend(issue.message for issue in report.warnings)
        if schema_attempt < _llm_schema_attempts():
            artifacts.schema_retry_attempts += 1
            artifacts.retry_attempts += 1
            artifacts.warnings.append(f"LLM ModSpec schema validation failed on attempt {schema_attempt}; retrying with validator errors.")
            retry_prompt = _schema_retry_user_prompt(prompt, errors, normalized)
            continue
        artifacts.error = "Invalid ModSpec from LLM: " + "; ".join(errors)
        raise LLMPlanningError(artifacts.error, artifacts)

    artifacts.error = "Invalid ModSpec from LLM."
    raise LLMPlanningError(artifacts.error, artifacts)


def plan_with_decomposed_llm(
    prompt: str,
    client: LLMClient,
    *,
    language: str = "zh_cn",
    config: AppConfig | None = None,
) -> tuple[ModSpec, PlannerArtifacts]:
    config = config or AppConfig.default()
    rag_query, rag_context, rag_hits = _retrieve_rag_context(prompt)
    rag_summary = summarize_knowledge_hits(rag_hits)
    system_prompt = _build_decomposed_feature_plan_system_prompt(language, rag_context=rag_context)
    artifacts = PlannerArtifacts(
        planner_mode="decomposed",
        provider=getattr(client, "provider_name", "unknown"),
        input_text=prompt,
        system_prompt=system_prompt,
        rag_query=rag_query,
        rag_query_expansions=expand_knowledge_query(rag_query),
        rag_context=rag_context,
        rag_hits=rag_hits,
        rag_categories=rag_summary["categories"],
        rag_capabilities=rag_summary["capabilities"],
        used_knowledge=_used_knowledge(rag_hits),
        rag_quality=_rag_quality(rag_hits, rag_query),
        provider_config=_provider_config_for_artifact(getattr(client, "provider_name", "unknown")),
        provider_health=_provider_health_for_artifact(getattr(client, "provider_name", "unknown")),
        provider_metadata=_provider_metadata_for_artifact(getattr(client, "provider_name", "unknown")),
    )

    feature_plan_raw = _complete_json_with_repair(
        client,
        system_prompt,
        prompt,
        artifacts,
        invalid_error="Decomposed planner returned invalid feature-plan JSON.",
    )
    artifacts.decomposed_feature_plan_raw_json = feature_plan_raw
    feature_plan, plan_warnings = _normalize_decomposed_feature_plan(feature_plan_raw, prompt, config)
    artifacts.decomposed_feature_plan_json = feature_plan
    artifacts.warnings.extend(plan_warnings)
    if not feature_plan["features"]:
        artifacts.error = "Decomposed planner produced no supported v1 feature plan entries."
        raise LLMPlanningError(artifacts.error, artifacts)

    composed_features: list[dict[str, Any]] = []
    for planned_feature in feature_plan["features"]:
        feature_system_prompt = _build_decomposed_feature_system_prompt(str(planned_feature["type"]), language)
        feature_user_prompt = _decomposed_feature_user_prompt(prompt, feature_plan, planned_feature)
        feature_record: dict[str, Any] = {
            "planned": planned_feature,
            "system_prompt": feature_system_prompt,
            "user_prompt": feature_user_prompt,
            "raw_json": None,
            "feature": None,
            "warnings": [],
        }
        try:
            raw_feature = _complete_json_with_repair(
                client,
                feature_system_prompt,
                feature_user_prompt,
                artifacts,
                invalid_error="Decomposed feature planner returned invalid JSON.",
            )
            feature_record["raw_json"] = raw_feature
            feature, feature_warnings = _extract_decomposed_feature(raw_feature, planned_feature)
            feature_record["warnings"].extend(feature_warnings)
        except LLMPlanningError as exc:
            feature = None
            message = str(exc)
            feature_record["warnings"].append(message)
            artifacts.decomposed_bad_raw_outputs.append(
                {
                    "stage": "feature_json",
                    "planned": planned_feature,
                    "reason": message,
                    "raw_text": exc.artifacts.raw_text,
                    "raw_json": exc.artifacts.raw_json,
                }
            )

        if feature is None:
            artifacts.decomposed_bad_raw_outputs.append(
                {
                    "stage": "feature_json",
                    "planned": planned_feature,
                    "reason": "Could not extract the requested feature JSON; deterministic fallback was used.",
                    "raw_text": artifacts.raw_text,
                    "raw_json": feature_record.get("raw_json"),
                }
            )
            feature = _fallback_decomposed_feature(planned_feature, feature_plan)
            feature_record["warnings"].append("Used deterministic fallback feature JSON.")

        feature_record["feature"] = feature
        artifacts.decomposed_feature_json_outputs.append(feature_record)
        composed_features.append(feature)

    composed_raw = {
        "mod_id": feature_plan["mod_id"],
        "mod_name": feature_plan["mod_name"],
        "package": feature_plan["package"],
        "version": str(feature_plan.get("version", config.default_mod_version)),
        "description": str(feature_plan.get("description", prompt)),
        "authors": [str(author) for author in feature_plan.get("authors", [])],
        "license_name": str(feature_plan.get("license_name", config.default_license_name)),
        "features": composed_features,
    }
    artifacts.decomposed_composed_raw_json = composed_raw

    normalized, warnings = _normalize_llm_output(composed_raw, prompt, config)
    artifacts.normalized_json = normalized
    artifacts.warnings.extend(warnings)
    artifacts.raw_json = {
        "feature_plan": feature_plan,
        "feature_outputs": artifacts.decomposed_feature_json_outputs,
        "composed_modspec_raw": composed_raw,
    }
    artifacts.raw_text = json.dumps(artifacts.raw_json, ensure_ascii=False, indent=2)

    spec = ModSpec.from_dict(normalized)
    report = validate_mod_spec(spec, config)
    artifacts.schema_validation_attempts.append(_schema_validation_attempt(1, report))
    if report.is_valid:
        artifacts.warnings.extend(issue.message for issue in report.warnings)
        return spec, artifacts

    errors = [issue.message for issue in report.errors]
    artifacts.warnings.extend(issue.message for issue in report.warnings)
    artifacts.error = "Invalid decomposed ModSpec: " + "; ".join(errors)
    raise LLMPlanningError(artifacts.error, artifacts)


def plan_modification_with_llm(
    existing: ModSpec,
    change_request: str,
    client: LLMClient,
    *,
    language: str = "zh_cn",
    config: AppConfig | None = None,
) -> tuple[ModSpec, PlannerArtifacts]:
    config = config or AppConfig.default()
    rag_query = _modify_rag_query(existing, change_request)
    rag_query, rag_context, rag_hits = _retrieve_rag_context(rag_query)
    rag_summary = summarize_knowledge_hits(rag_hits)
    system_prompt = _build_modify_system_prompt(language, rag_context=rag_context)
    existing_spec_json = json.dumps(existing.to_dict(), ensure_ascii=False, indent=2)
    user_prompt = "\n".join(
        [
            "Existing ModSpec JSON:",
            existing_spec_json,
            "",
            "Change Request:",
            change_request,
            "",
            "Return only the patch ModSpec JSON needed for this change.",
        ]
    )
    artifacts = PlannerArtifacts(
        planner_mode="llm-modify",
        provider=getattr(client, "provider_name", "unknown"),
        input_text=user_prompt,
        system_prompt=system_prompt,
        rag_query=rag_query,
        rag_query_expansions=expand_knowledge_query(rag_query),
        rag_context=rag_context,
        rag_hits=rag_hits,
        rag_categories=rag_summary["categories"],
        rag_capabilities=rag_summary["capabilities"],
        used_knowledge=_used_knowledge(rag_hits),
        rag_quality=_rag_quality(rag_hits, rag_query),
        provider_config=_provider_config_for_artifact(getattr(client, "provider_name", "unknown")),
        provider_health=_provider_health_for_artifact(getattr(client, "provider_name", "unknown")),
        provider_metadata=_provider_metadata_for_artifact(getattr(client, "provider_name", "unknown")),
    )
    retry_prompt = user_prompt
    for schema_attempt in range(1, _llm_schema_attempts() + 1):
        raw_json = _complete_json_with_repair(
            client,
            system_prompt,
            retry_prompt,
            artifacts,
            invalid_error="LLM modification planner returned invalid JSON.",
        )

        normalized, warnings = _normalize_llm_patch_output(raw_json, existing, change_request, config)
        artifacts.normalized_json = normalized
        artifacts.warnings.extend(warnings)

        patch_spec = ModSpec.from_dict(normalized)
        report = validate_mod_spec(_merge_preview(existing, patch_spec), config)
        validation_attempt = _schema_validation_attempt(schema_attempt, report)
        artifacts.schema_validation_attempts.append(validation_attempt)
        if report.is_valid:
            artifacts.warnings.extend(issue.message for issue in report.warnings)
            return patch_spec, artifacts

        errors = [issue.message for issue in report.errors]
        artifacts.warnings.extend(issue.message for issue in report.warnings)
        if schema_attempt < _llm_schema_attempts():
            artifacts.schema_retry_attempts += 1
            artifacts.retry_attempts += 1
            artifacts.warnings.append(f"LLM patch schema validation failed on attempt {schema_attempt}; retrying with validator errors.")
            retry_prompt = _schema_retry_user_prompt(user_prompt, errors, normalized)
            continue
        artifacts.error = "Invalid modification patch from LLM: " + "; ".join(errors)
        raise LLMPlanningError(artifacts.error, artifacts)

    artifacts.error = "Invalid modification patch from LLM."
    raise LLMPlanningError(artifacts.error, artifacts)


def write_planner_artifacts(project_dir: Path, config: AppConfig, artifacts: PlannerArtifacts) -> None:
    agent_dir = ensure_directory(config.agent_dir_for(project_dir))
    write_text(agent_dir / "planner-input.txt", artifacts.input_text)
    write_text(agent_dir / "planner-mode.txt", f"{artifacts.planner_mode}:{artifacts.provider}\n")
    if artifacts.system_prompt:
        write_text(agent_dir / "planner-system-prompt.txt", artifacts.system_prompt)

    if artifacts.raw_json is not None:
        write_json(agent_dir / "llm-plan-raw.json", artifacts.raw_json)
    elif artifacts.raw_text:
        write_json(agent_dir / "llm-plan-raw.json", {"raw_text": artifacts.raw_text})

    if artifacts.normalized_json is not None:
        write_json(agent_dir / "llm-plan-normalized.json", artifacts.normalized_json)

    if (
        artifacts.decomposed_feature_plan_raw_json is not None
        or artifacts.decomposed_feature_plan_json is not None
        or artifacts.decomposed_feature_json_outputs
        or artifacts.decomposed_composed_raw_json is not None
        or artifacts.decomposed_bad_raw_outputs
    ):
        _write_decomposed_planner_artifacts(agent_dir, artifacts)

    write_json(agent_dir / "llm-plan-warnings.json", artifacts.warnings)
    write_json(
        agent_dir / "llm-stability.json",
        {
            "provider": artifacts.provider,
            "provider_config": artifacts.provider_config,
            "provider_health": artifacts.provider_health,
            "provider_metadata": artifacts.provider_metadata,
            "completion_usage": artifacts.completion_usage,
            "completion_attempts": artifacts.completion_attempts,
            "retry_attempts": artifacts.retry_attempts,
            "schema_retry_attempts": artifacts.schema_retry_attempts,
            "schema_validation_attempts": artifacts.schema_validation_attempts,
            "json_repair_applied": artifacts.json_repair_applied,
            "parse_attempts": artifacts.parse_attempts,
        },
    )
    write_json(
        agent_dir / "rag-context.json",
        {
            "query": artifacts.rag_query,
            "query_expansions": artifacts.rag_query_expansions,
            "hits": artifacts.rag_hits,
            "categories": artifacts.rag_categories,
            "capabilities": artifacts.rag_capabilities,
            "used_knowledge": artifacts.used_knowledge,
            "quality": artifacts.rag_quality,
            "context": artifacts.rag_context,
        },
    )
    write_json(agent_dir / "llm-used-knowledge.json", artifacts.used_knowledge)
    if artifacts.rag_context:
        write_text(agent_dir / "rag-context.md", _render_rag_context_md(artifacts))

    if artifacts.error:
        lines = [
            "# LLM Plan Error",
            "",
            artifacts.error,
            "",
            "## Raw Output",
            "",
            "```text",
            artifacts.raw_text,
            "```",
            "",
        ]
        write_text(agent_dir / "llm-plan-error.md", "\n".join(lines))


def _write_decomposed_planner_artifacts(agent_dir: Path, artifacts: PlannerArtifacts) -> None:
    decomposed_dir = ensure_directory(agent_dir / "decomposed-planner")
    if artifacts.decomposed_feature_plan_raw_json is not None:
        write_json(decomposed_dir / "feature-plan-raw.json", artifacts.decomposed_feature_plan_raw_json)
    if artifacts.decomposed_feature_plan_json is not None:
        write_json(decomposed_dir / "feature-plan.json", artifacts.decomposed_feature_plan_json)
    if artifacts.decomposed_composed_raw_json is not None:
        write_json(decomposed_dir / "composed-modspec-raw.json", artifacts.decomposed_composed_raw_json)
    if artifacts.decomposed_feature_json_outputs:
        feature_json_dir = ensure_directory(decomposed_dir / "feature-json")
        write_json(decomposed_dir / "feature-jsons.json", artifacts.decomposed_feature_json_outputs)
        for index, record in enumerate(artifacts.decomposed_feature_json_outputs, start=1):
            planned = record.get("planned") if isinstance(record.get("planned"), dict) else {}
            feature_type = slugify_mod_id(str(planned.get("type", "feature")), fallback="feature")
            feature_id = slugify_mod_id(str(planned.get("id", f"feature_{index}")), fallback=f"feature_{index}")
            write_json(feature_json_dir / f"{index:02d}-{feature_type}-{feature_id}.json", record)
    if artifacts.decomposed_bad_raw_outputs:
        bad_dir = ensure_directory(decomposed_dir / "bad-raw-output")
        write_json(decomposed_dir / "bad-raw-outputs.json", artifacts.decomposed_bad_raw_outputs)
        for index, record in enumerate(artifacts.decomposed_bad_raw_outputs, start=1):
            write_json(bad_dir / f"{index:02d}-bad-raw-output.json", record)
            raw_text = str(record.get("raw_text", ""))
            if raw_text:
                write_text(bad_dir / f"{index:02d}-bad-raw-output.txt", raw_text)


def _complete_json_with_repair(
    client: LLMClient,
    system_prompt: str,
    user_prompt: str,
    artifacts: PlannerArtifacts,
    *,
    invalid_error: str,
) -> dict:
    max_attempts = _llm_completion_attempts()
    retry_prompt = user_prompt
    for attempt in range(1, max_attempts + 1):
        try:
            completion = client.complete_json(system_prompt, retry_prompt)
        except Exception as exc:  # noqa: BLE001 - normalized into planner artifacts.
            artifacts.error = f"LLM provider request failed: {exc}"
            if attempt >= max_attempts:
                raise LLMPlanningError(artifacts.error, artifacts) from exc
            artifacts.retry_attempts += 1
            artifacts.warnings.append(f"LLM provider request failed on attempt {attempt}; retrying.")
            retry_prompt = _retry_user_prompt(user_prompt)
            continue

        artifacts.provider = completion.provider
        artifacts.raw_text = completion.raw_text
        artifacts.raw_json = completion.parsed_json
        artifacts.completion_usage = completion.telemetry_dict()
        artifacts.completion_attempts.append({"completion_attempt": attempt, **completion.telemetry_dict()})
        if completion.parsed_json is not None:
            artifacts.parse_attempts.append(
                {
                    "completion_attempt": attempt,
                    "strategy": "provider_parsed_json",
                    "success": True,
                }
            )
            return completion.parsed_json

        parsed_json, parse_attempts, repair_applied = _parse_or_repair_llm_json(completion.raw_text)
        artifacts.parse_attempts.extend(
            {"completion_attempt": attempt, **parse_attempt} for parse_attempt in parse_attempts
        )
        if repair_applied:
            artifacts.json_repair_applied = True
        if parsed_json is not None:
            artifacts.raw_json = parsed_json
            return parsed_json

        if attempt < max_attempts:
            artifacts.retry_attempts += 1
            artifacts.warnings.append(f"LLM JSON parse failed on attempt {attempt}; retrying.")
            retry_prompt = _retry_user_prompt(user_prompt)

    artifacts.error = invalid_error
    raise LLMPlanningError(invalid_error, artifacts)


def _parse_or_repair_llm_json(raw_text: str) -> tuple[dict | None, list[dict[str, Any]], bool]:
    attempts: list[dict[str, Any]] = []
    repair_applied = False

    direct = raw_text.strip()
    parsed = _try_parse_json_candidate("direct", direct, attempts)
    if parsed is not None:
        return parsed, attempts, repair_applied

    fenced = _strip_markdown_json_fence(direct)
    if fenced != direct:
        repair_applied = True
        parsed = _try_parse_json_candidate("strip_markdown_fence", fenced, attempts)
        if parsed is not None:
            return parsed, attempts, repair_applied

    balanced = _extract_balanced_json_object(fenced)
    if balanced and balanced != fenced:
        repair_applied = True
        parsed = _try_parse_json_candidate("extract_balanced_object", balanced, attempts)
        if parsed is not None:
            return parsed, attempts, repair_applied

    trailing_comma_fixed = _remove_trailing_commas(balanced or fenced)
    if trailing_comma_fixed != (balanced or fenced):
        repair_applied = True
        parsed = _try_parse_json_candidate("remove_trailing_commas", trailing_comma_fixed, attempts)
        if parsed is not None:
            return parsed, attempts, repair_applied

    return None, attempts, repair_applied


def _try_parse_json_candidate(strategy: str, candidate: str, attempts: list[dict[str, Any]]) -> dict | None:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        attempts.append(
            {
                "strategy": strategy,
                "success": False,
                "error": exc.msg,
                "position": exc.pos,
                "preview": candidate[:160],
            }
        )
        return None
    success = isinstance(parsed, dict)
    attempts.append(
        {
            "strategy": strategy,
            "success": success,
            "error": None if success else "Top-level JSON value is not an object.",
            "preview": candidate[:160],
        }
    )
    return parsed if success else None


def _strip_markdown_json_fence(text: str) -> str:
    match = re.match(r"^```(?:json|JSON)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _extract_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1].strip()
    return None


def _remove_trailing_commas(text: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", text)


def _llm_completion_attempts() -> int:
    for name in ("NEOFORGE_AGENT_LLM_RETRIES", "NEOFORGE_AGENT_LLM_MAX_RETRIES", "OPENAI_MAX_RETRIES"):
        value = os.environ.get(name)
        if not value:
            continue
        try:
            retries = int(value)
        except ValueError:
            continue
        return max(1, retries + 1)
    return 3


def _llm_schema_attempts() -> int:
    for name in ("NEOFORGE_AGENT_LLM_SCHEMA_RETRIES", "OPENAI_SCHEMA_RETRIES"):
        value = os.environ.get(name)
        if not value:
            continue
        try:
            retries = int(value)
        except ValueError:
            continue
        return max(1, retries + 1)
    return DEFAULT_LLM_SCHEMA_RETRIES + 1


def _retry_user_prompt(user_prompt: str) -> str:
    return "\n".join(
        [
            user_prompt,
            "",
            "The previous response could not be parsed as a single JSON object.",
            "Retry now. Return only valid JSON. Do not use Markdown fences, prose, or trailing commas.",
        ]
    )


def _schema_retry_user_prompt(user_prompt: str, errors: list[str], normalized_json: dict) -> str:
    return "\n".join(
        [
            user_prompt,
            "",
            "The previous JSON parsed successfully but failed ModSpec validation.",
            "Retry now. Return only valid JSON matching the ModSpec schema.",
            "Fix these validator errors:",
            *[f"- {error}" for error in errors[:8]],
            "",
            "Previous normalized JSON preview:",
            json.dumps(normalized_json, ensure_ascii=False, indent=2)[:4000],
        ]
    )


def _provider_config_for_artifact(provider: str) -> dict[str, Any]:
    try:
        return inspect_llm_provider_config(provider).to_dict()
    except Exception as exc:  # noqa: BLE001 - artifact collection must not block planning.
        return {"provider": provider, "valid": False, "errors": [str(exc)]}


def _provider_health_for_artifact(provider: str) -> dict[str, Any]:
    try:
        return check_llm_provider_health(provider).to_dict()
    except Exception as exc:  # noqa: BLE001 - artifact collection must not block planning.
        return {
            "provider": provider,
            "status": "fail",
            "healthy": False,
            "can_attempt_request": False,
            "fallback_recommended": True,
            "errors": [str(exc)],
            "warnings": [],
        }


def _provider_metadata_for_artifact(provider: str) -> dict[str, Any]:
    try:
        return get_llm_provider_metadata(provider).to_dict()
    except Exception as exc:  # noqa: BLE001 - artifact collection must not block planning.
        return {"provider": provider, "errors": [str(exc)]}


def _schema_validation_attempt(attempt: int, report) -> dict[str, Any]:
    return {
        "attempt": attempt,
        "success": bool(report.is_valid),
        "errors": [issue.message for issue in report.errors],
        "warnings": [issue.message for issue in report.warnings],
    }


def _rag_quality(hits: list[dict], query: str) -> dict[str, Any]:
    scores = [int(hit.get("score", 0) or 0) for hit in hits if isinstance(hit, dict)]
    capabilities = sorted({str(hit.get("capability", hit.get("category", ""))) for hit in hits if isinstance(hit, dict) and (hit.get("capability") or hit.get("category"))})
    categories = sorted({str(hit.get("category", "")) for hit in hits if isinstance(hit, dict) and hit.get("category")})
    top_score = max(scores) if scores else 0
    return {
        "query": query,
        "hits_count": len(hits),
        "top_score": top_score,
        "average_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "categories_count": len(categories),
        "capabilities_count": len(capabilities),
        "categories": categories,
        "capabilities": capabilities,
        "quality": "strong" if top_score >= 80 else "moderate" if top_score >= 30 else "weak" if hits else "none",
    }


def _real_llm_planner_contract_lines(*, patch_mode: bool = False) -> list[str]:
    prefix = "For patch requests, " if patch_mode else ""
    return [
        "Real LLM planner contract:",
        f"{prefix}Interpret every user request as a request for ModSpec JSON, not source code.",
        "Use only supported feature types and fields from the ModSpec schema.",
        "If a request is broad or ambitious, select the closest supported DSL/template representation instead of inventing Java, resources, registries, or unsupported fields.",
        "Prefer deterministic, template-backed features: item, block, ore, tool, armor, recipe, machine, progression, balance_plan, and quest.",
        "For machines, output one 'machine' feature with machine_kind, inventory_slots, input_slots, output_slots, energy_capacity, energy_per_tick, max_progress, and menu_title; never emit GUI, Screen, menu, or BlockEntity Java.",
        "For gameplay/progression requests, output explicit generated feature ids plus progression stages and links; every stage/link/quest/balance reference must point to an existing or generated id.",
        "For recipes, results and keys must use the same mod namespace and existing or generated ids.",
        "If unsupported behavior is requested, omit it or capture the limitation in top-level extra_notes; never create invalid feature types or arbitrary schema fields.",
    ]


def _build_system_prompt(language: str, *, rag_context: str = "") -> str:
    schema = json.dumps(get_modspec_schema(), ensure_ascii=False, indent=2)
    lines = [
            "You are a ModSpec planner for a NeoForge 26.1 Minecraft mod generator.",
            "You must output only valid JSON.",
            "Do not output Markdown.",
            "Default to ModSpec-first routing. If the request fits the schema, output ModSpec only.",
            "If the request clearly needs source edits beyond ModSpec, set requires_direct_code=true and attach direct_code_plan while still returning a minimal valid ModSpec.",
            "Direct Code plans must use structured JSON only, never free-form diffs.",
            "Direct Code changes support only write_file and replace_text with path, operation, reason, risk_level, and content or search/replace.",
            "Direct Code paths must stay relative to the generated workspace and under src/main/java, src/main/resources, build.gradle, gradle.properties, or .agent.",
            "Do not generate Java code outside direct_code_plan.",
            "Do not generate Gradle files outside direct_code_plan.",
            "Do not invent unsupported feature types.",
            "",
            *_real_llm_planner_contract_lines(),
            "",
            "Supported feature types:",
            "- item",
            "- block",
            "- machine",
            "- entity",
            "- dimension",
            "- biome",
            "- world_feature",
            "- structure",
            "- loot_pool",
            "- java_extension",
            "- ore",
            "- food",
            "- sword",
            "- tool",
            "- armor",
            "- recipe",
            "- progression",
            "- balance_plan",
            "- quest",
            "",
            "For ruby equipment set requests, output ruby item material plus ruby_sword, ruby_pickaxe, ruby_axe, ruby_shovel, ruby_hoe or ruby_helmet, ruby_chestplate, ruby_leggings, ruby_boots, and shaped recipe features.",
            "tool_material and armor_material may be 'ruby' for ruby equipment; the deterministic generator maps it to the supported Java baseline.",
            "For block variant requests, use feature type 'block' with block_kind set to one of cube, stairs, slab, wall, button, pressure_plate, fence, fence_gate, door, trapdoor.",
            "For ruby building block sets, include ruby_block as the base cube block, then ruby_stairs, ruby_slab, ruby_wall, ruby_button, ruby_pressure_plate, ruby_fence, ruby_fence_gate, ruby_door, and ruby_trapdoor with base_block='ruby_block'.",
            "For machine requests, use feature type 'machine' with machine_kind set to furnace, compressor, upgrade_table, magic_altar, or storage. Machines generate BlockEntity, menu, screen, progress, energy, slots, and data sync templates.",
            "For entity or mob requests, use feature type 'entity' with entity_kind, category, attributes, drops, spawn, goals, and attack. Entity templates support simple PathfinderMob AI and melee attack only.",
            "For world or structure requests, use dimension, biome, world_feature, structure, and loot_pool features. V5.4 supports fixed-biome noise dimensions, biome JSON, ore_vein world features, jigsaw structure metadata, structure sets, template pools, and chest loot tables.",
            "Structures are template-pool placeholders unless explicit NBT templates are added later; do not invent arbitrary Java, NBT, or complex terrain noise.",
            "For controlled Java extension requests, use feature type 'java_extension' only for additive sandbox classes. Provide class_name, purpose, explanation, allowed_imports from the schema enum, and String-returning methods with return_value; do not output raw Java, package lines, import lines, Gradle changes, or edits to existing sources.",
            "For progression or gameplay loop requests, use feature type 'progression'. It should reference existing generated feature ids through stages and links; it must not emit Java patches.",
            "For recipe, loot, rarity, machine timing, energy, or economy-balance requests, use feature type 'balance_plan'. It should target a progression and request report-only balance planning; it must not emit Java patches.",
            "For quest, advancement, guidebook, or Patchouli requests, use feature type 'quest'. It should target an existing progression or define structured tasks; it must not emit Java patches.",
            "",
            "Use snake_case ids.",
            "Use mod namespace references where needed.",
            "Recipes must reference existing generated ids.",
            "If the user asks for unsupported content and no safe Direct Code plan is appropriate, do not generate invalid features.",
            f"Preferred natural language output locale: {language}.",
            "",
            "Return JSON matching this schema as closely as possible:",
            schema,
    ]
    if rag_context:
        lines.extend(["", rag_context])
    return "\n".join(lines)


def _build_decomposed_feature_plan_system_prompt(language: str, *, rag_context: str = "") -> str:
    lines = [
        "DECOMPOSED_FEATURE_PLAN_V1",
        "You are a NeoForge ModSpec decomposition planner.",
        "Return only one valid JSON object. Do not output Markdown.",
        "Do not write Java, Gradle, registry code, resource JSON, or free-form patches.",
        "First split the natural language request into a small feature plan.",
        "V1 supports only these feature types: item, ore, machine, tool, sword, recipe, progression.",
        "Use ore.worldgen for ore world generation; do not create a separate worldgen feature type.",
        "Keep each plan entry small and debuggable; detailed fields can go under fields.",
        "Every id must be snake_case and every dependency must reference another planned or existing id.",
        f"Preferred natural language output locale: {language}.",
        "",
        "Return this JSON shape:",
        "{",
        '  "mod_id": "snake_case_mod_id",',
        '  "mod_name": "Display Name",',
        '  "package": "com.generated.snake_case_mod_id",',
        '  "version": "0.1.0",',
        '  "description": "short request summary",',
        '  "features": [',
        "    {",
        '      "type": "item|ore|machine|tool|sword|recipe|progression",',
        '      "id": "snake_case_id",',
        '      "display_name_en_us": "Display Name",',
        '      "intent": "short reason this feature exists",',
        '      "depends_on": ["other_feature_id"],',
        '      "fields": {}',
        "    }",
        "  ]",
        "}",
    ]
    if rag_context:
        lines.extend(["", rag_context])
    return "\n".join(lines)


def _build_decomposed_feature_system_prompt(feature_type: str, language: str) -> str:
    return "\n".join(
        [
            "DECOMPOSED_FEATURE_JSON_V1",
            "You fill one small NeoForge ModSpec feature JSON object from a feature plan entry.",
            "Return only one valid JSON object. Do not output Markdown.",
            "Do not output a full ModSpec. Do not write Java, Gradle, registry code, or resource files.",
            f"The JSON object must use type '{feature_type}'.",
            "Use only fields supported by the ModSpec schema for that feature type.",
            "For ore, put world generation under worldgen with enabled=true when natural generation is requested.",
            "For machines, use one machine feature and machine_kind rather than GUI or BlockEntity code.",
            "For recipes, reference existing/generated ids with the mod namespace.",
            "For progression, reference generated feature ids through stages and links.",
            f"Preferred natural language output locale: {language}.",
        ]
    )


def _decomposed_feature_user_prompt(prompt: str, feature_plan: dict[str, Any], planned_feature: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Original request:",
            prompt,
            "",
            "Mod metadata JSON:",
            json.dumps(_compact_decomposed_mod_metadata(feature_plan), ensure_ascii=False, indent=2),
            "",
            "Reference map JSON:",
            json.dumps(_compact_decomposed_reference_map(feature_plan), ensure_ascii=False, indent=2),
            "",
            "Dependency summary JSON:",
            json.dumps(_decomposed_dependency_summary(feature_plan, planned_feature), ensure_ascii=False, indent=2),
            "",
            "Field contract JSON:",
            json.dumps(_decomposed_field_contract(str(planned_feature.get("type", ""))), ensure_ascii=False, indent=2),
            "",
            "Target feature plan item JSON:",
            json.dumps(planned_feature, ensure_ascii=False, indent=2),
            "",
            "Return only the target feature JSON object.",
        ]
    )


def _compact_decomposed_mod_metadata(feature_plan: dict[str, Any]) -> dict[str, Any]:
    authors = feature_plan.get("authors", [])
    if not isinstance(authors, list):
        authors = []
    return {
        "mod_id": str(feature_plan.get("mod_id", "")),
        "mod_name": str(feature_plan.get("mod_name", "")),
        "package": str(feature_plan.get("package", "")),
        "version": str(feature_plan.get("version", "")),
        "description": str(feature_plan.get("description", "")),
        "authors": [str(author) for author in authors],
        "license_name": str(feature_plan.get("license_name", "")),
    }


def _compact_decomposed_reference_map(feature_plan: dict[str, Any]) -> list[dict[str, Any]]:
    mod_id = str(feature_plan.get("mod_id", ""))
    references: list[dict[str, Any]] = []
    features = feature_plan.get("features", [])
    if not isinstance(features, list):
        return references
    for feature in features:
        if not isinstance(feature, dict):
            continue
        feature_id = str(feature.get("id", ""))
        depends_on = feature.get("depends_on", [])
        references.append(
            {
                "type": str(feature.get("type", "")),
                "id": feature_id,
                "resource_id": _decomposed_resource_id(mod_id, feature_id),
                "display_name_en_us": str(feature.get("display_name_en_us", "")),
                "depends_on": [str(item) for item in depends_on] if isinstance(depends_on, list) else [],
            }
        )
    return references


def _decomposed_dependency_summary(feature_plan: dict[str, Any], planned_feature: dict[str, Any]) -> list[dict[str, Any]]:
    depends_on = planned_feature.get("depends_on", [])
    if not isinstance(depends_on, list):
        return []
    references = {str(item.get("id", "")): item for item in _compact_decomposed_reference_map(feature_plan)}
    mod_id = str(feature_plan.get("mod_id", ""))
    summary: list[dict[str, Any]] = []
    for dependency in depends_on:
        dependency_id = str(dependency)
        if dependency_id in references:
            summary.append(references[dependency_id])
        else:
            summary.append(
                {
                    "id": dependency_id,
                    "resource_id": _decomposed_resource_id(mod_id, dependency_id),
                    "missing_from_reference_map": True,
                }
            )
    return summary


def _decomposed_resource_id(mod_id: str, feature_id: str) -> str:
    if not feature_id:
        return ""
    if ":" in feature_id:
        return feature_id
    if mod_id:
        return f"{mod_id}:{feature_id}"
    return feature_id


def _decomposed_field_contract(feature_type: str) -> dict[str, Any]:
    base = {
        "required": ["type", "id", "display_name_en_us"],
        "shared_optional": ["display_name_zh_cn", "behavior"],
    }
    contracts: dict[str, dict[str, Any]] = {
        "item": {
            **base,
            "optional": ["max_stack_size", "rarity", "fire_resistant", "food"],
        },
        "ore": {
            **base,
            "optional": [
                "drop",
                "strength",
                "resistance",
                "sound",
                "requires_correct_tool",
                "tool_tier",
                "worldgen",
            ],
            "worldgen": ["enabled", "dimension", "min_y", "max_y", "vein_size", "veins_per_chunk"],
        },
        "machine": {
            **base,
            "optional": [
                "machine_kind",
                "inventory_slots",
                "input_slots",
                "output_slots",
                "energy_capacity",
                "energy_per_tick",
                "max_progress",
                "menu_title",
            ],
        },
        "tool": {
            **base,
            "optional": ["tool_type", "tool_material", "attack_damage_bonus", "attack_speed", "durability"],
        },
        "sword": {
            **base,
            "optional": ["tool_material", "attack_damage_bonus", "attack_speed", "durability", "on_hit"],
        },
        "recipe": {
            **base,
            "optional": ["recipe_type", "ingredients", "pattern", "keys", "result", "count", "category", "group"],
        },
        "progression": {
            **base,
            "optional": ["title", "summary", "entry_stage", "end_stage", "stages", "links"],
            "stage_fields": ["id", "type", "title", "requires", "provides", "unlocks", "evidence"],
            "link_fields": ["from", "to", "trigger", "requirement"],
        },
    }
    return contracts.get(
        feature_type,
        {
            **base,
            "optional": [],
        },
    )


def _build_modify_system_prompt(language: str, *, rag_context: str = "") -> str:
    schema = json.dumps(get_modspec_schema(), ensure_ascii=False, indent=2)
    lines = [
            "You are a ModSpec patch planner for a NeoForge 26.1 Minecraft mod generator.",
            "You must output only valid JSON.",
            "Do not output Markdown.",
            "Default to ModSpec-first routing. If the change fits the schema, output a ModSpec patch only.",
            "If the change clearly needs source edits beyond ModSpec, set requires_direct_code=true and attach direct_code_plan while still returning a minimal valid patch ModSpec.",
            "Direct Code plans must use structured JSON only, never free-form diffs.",
            "Direct Code changes support only write_file and replace_text with path, operation, reason, risk_level, and content or search/replace.",
            "Direct Code paths must stay relative to the generated workspace and under src/main/java, src/main/resources, build.gradle, gradle.properties, or .agent.",
            "Do not generate Java code outside direct_code_plan.",
            "Do not generate Gradle files outside direct_code_plan.",
            "Do not repeat the entire project unless the change request truly requires it.",
            "Only output the features that need to be added or updated.",
            "The modify flow is a controlled patch-agent: plan the patch first, keep the scope limited to managed files, and never emit raw repository edits.",
            "",
            *_real_llm_planner_contract_lines(patch_mode=True),
            "",
            "Supported feature types:",
            "- item",
            "- block",
            "- machine",
            "- entity",
            "- dimension",
            "- biome",
            "- world_feature",
            "- structure",
            "- loot_pool",
            "- java_extension",
            "- ore",
            "- food",
            "- sword",
            "- tool",
            "- armor",
            "- recipe",
            "- progression",
            "- balance_plan",
            "- quest",
            "",
            "For ruby equipment set change requests, output only the ruby equipment items and shaped recipe features that need to be added or updated.",
            "tool_material and armor_material may be 'ruby' for ruby equipment; the deterministic generator maps it to the supported Java baseline.",
            "For block variant change requests, output only the relevant block features with block_kind and base_block plus any required recipe features.",
            "For machine change requests, output machine features with machine_kind, inventory_slots, input_slots, output_slots, energy_capacity, energy_per_tick, max_progress, and menu_title.",
            "For entity or mob change requests, output entity features with entity_kind, category, attributes, drops, spawn, goals, and attack. Entity templates support simple PathfinderMob AI and melee attack only.",
            "For world or structure change requests, output only the dimension, biome, world_feature, structure, and loot_pool features that need to be added or updated.",
            "For controlled Java extension change requests, output only additive java_extension features. Never patch existing source files or emit raw Java code.",
            "For progression or gameplay loop change requests, output progression features that reference existing generated ids; do not patch Java.",
            "For balance change requests, output balance_plan features that target existing progression ids; do not patch Java.",
            "For quest, advancement, guidebook, or Patchouli change requests, output quest features that target existing progression ids or define structured tasks; do not patch Java.",
            "",
            "Use snake_case ids.",
            "Use the existing mod namespace for references.",
            f"Preferred natural language output locale: {language}.",
            "",
            "Return JSON matching this schema as closely as possible:",
            schema,
    ]
    if rag_context:
        lines.extend(["", rag_context])
    return "\n".join(lines)


def _retrieve_rag_context(query: str) -> tuple[str, str, list[dict]]:
    knowledge_base = NeoForgeKnowledgeBase()
    hits = knowledge_base.query(query, limit=4)
    context = knowledge_base.render_context(query, limit=4)
    return query, context, [hit.to_dict() for hit in hits]


def _used_knowledge(hits: list[dict]) -> list[dict]:
    return [
        {
            "id": str(hit.get("id", "")),
            "title": str(hit.get("title", "")),
            "category": str(hit.get("category", "")),
            "capability": str(hit.get("capability", hit.get("category", ""))),
            "score": int(hit.get("score", 0) or 0),
            "reason": "Retrieved as a relevant NeoForge generation constraint for this planner prompt.",
        }
        for hit in hits
    ]


def _modify_rag_query(existing: ModSpec, change_request: str) -> str:
    feature_ids = ", ".join(feature.identifier for feature in existing.iter_features())
    return "\n".join(
        [
            change_request,
            f"Existing feature ids: {feature_ids}" if feature_ids else "Existing feature ids: none",
        ]
    )


def _render_rag_context_md(artifacts: PlannerArtifacts) -> str:
    lines = [
        "# RAG Context",
        "",
        f"Query: `{artifacts.rag_query}`",
        f"Expansions: `{', '.join(artifacts.rag_query_expansions)}`",
        f"Hits: {len(artifacts.rag_hits)}",
        "",
        "## Categories",
        "",
    ]
    if artifacts.rag_categories:
        lines.extend(f"- `{key}`: {value}" for key, value in artifacts.rag_categories.items())
    else:
        lines.append("- No category hits.")
    lines.extend(
        [
            "",
            "## Used Knowledge",
            "",
        ]
    )
    if artifacts.used_knowledge:
        for item in artifacts.used_knowledge:
            lines.append(f"- `{item.get('id')}` `{item.get('capability')}` score={item.get('score')}: {item.get('title')}")
    else:
        lines.append("- No retrieved knowledge was used.")
    lines.extend(
        [
            "",
            "## Hits",
            "",
        ]
    )
    if not artifacts.rag_hits:
        lines.append("- No retrieved snippets.")
    for hit in artifacts.rag_hits:
        lines.append(f"- `{hit.get('id')}` score={hit.get('score')}: {hit.get('title')}")
    lines.extend(["", "## Context", "", "```text", artifacts.rag_context, "```", ""])
    return "\n".join(lines)


def _normalize_decomposed_feature_plan(raw: dict, prompt: str, config: AppConfig) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    plan_source = raw.get("feature_plan") if isinstance(raw.get("feature_plan"), dict) else raw
    mod_id = slugify_mod_id(str(plan_source.get("mod_id", plan_source.get("id", plan_source.get("mod_name", prompt)))))
    mod_name = str(plan_source.get("mod_name", plan_source.get("display_name", derive_display_name(mod_id)))) or derive_display_name(mod_id)
    package_name = str(plan_source.get("package", plan_source.get("package_name", derive_package_name(mod_id, config.default_group_prefix))))

    raw_features: list[dict[str, Any]] = []
    for candidate_source in (plan_source, raw):
        if not isinstance(candidate_source, dict):
            continue
        features = candidate_source.get("features")
        if isinstance(features, list):
            raw_features.extend(feature for feature in features if isinstance(feature, dict))
        raw_features.extend(feature for feature in _expand_typed_feature_lists(candidate_source) if isinstance(feature, dict))

    seen: set[tuple[str, str]] = set()
    planned_features: list[dict[str, Any]] = []
    for raw_feature in raw_features:
        planned = _planned_decomposed_feature_from_raw(raw_feature, warnings)
        if planned is None:
            continue
        key = (str(planned["type"]), str(planned["id"]))
        if key in seen:
            continue
        seen.add(key)
        planned_features.append(planned)

    planned_features = _ensure_decomposed_material_items(planned_features, mod_id)
    planned_features = _sort_decomposed_features(planned_features)
    planned_features = _trim_decomposed_progression_references(planned_features)
    return (
        {
            "mod_id": mod_id,
            "mod_name": mod_name,
            "package": package_name,
            "version": str(plan_source.get("version", config.default_mod_version)),
            "description": str(plan_source.get("description", prompt)),
            "authors": [str(author) for author in plan_source.get("authors", [])],
            "license_name": str(plan_source.get("license_name", config.default_license_name)),
            "features": planned_features,
        },
        warnings,
    )


def _trim_decomposed_progression_references(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known_ids = {str(feature.get("id")) for feature in features if feature.get("id")}
    for feature in features:
        if feature.get("type") != "progression":
            continue
        fields = feature.get("fields") if isinstance(feature.get("fields"), dict) else {}
        raw_stages = fields.get("stages") if isinstance(fields.get("stages"), list) else []
        kept_stages: list[dict[str, Any]] = []
        kept_stage_ids: set[str] = set()
        for raw_stage in raw_stages:
            if not isinstance(raw_stage, dict):
                continue
            stage = dict(raw_stage)
            for key in ("requires", "provides", "unlocks", "evidence"):
                values = stage.get(key) if isinstance(stage.get(key), list) else []
                stage[key] = [str(value) for value in values if _decomposed_ref_known(str(value), known_ids)]
            stage_id = slugify_mod_id(str(stage.get("id", stage.get("identifier", stage.get("title", "stage")))), fallback="stage")
            has_known_reference = any(stage.get(key) for key in ("requires", "provides", "unlocks", "evidence"))
            if not has_known_reference and stage_id not in known_ids:
                continue
            stage["id"] = stage_id
            kept_stage_ids.add(stage_id)
            kept_stages.append(stage)

        if kept_stages:
            fields["stages"] = kept_stages
            fields["entry_stage"] = str(fields.get("entry_stage", "")) if str(fields.get("entry_stage", "")) in kept_stage_ids else str(kept_stages[0]["id"])
            fields["end_stage"] = str(fields.get("end_stage", "")) if str(fields.get("end_stage", "")) in kept_stage_ids else str(kept_stages[-1]["id"])
            raw_links = fields.get("links") if isinstance(fields.get("links"), list) else []
            fields["links"] = [
                link
                for link in raw_links
                if isinstance(link, dict)
                and str(link.get("from", link.get("from_stage", ""))) in kept_stage_ids
                and str(link.get("to", link.get("to_stage", ""))) in kept_stage_ids
            ]
        feature["fields"] = fields
    return features


def _decomposed_ref_known(reference: str, known_ids: set[str]) -> bool:
    value = reference.split(":", 1)[1] if ":" in reference else reference
    return value in known_ids


def _planned_decomposed_feature_from_raw(feature: dict[str, Any], warnings: list[str]) -> dict[str, Any] | None:
    feature_type = str(feature.get("type", feature.get("feature_type", ""))).strip().lower()
    if feature_type == "worldgen":
        feature_type = "ore"
    if feature_type not in DECOMPOSED_PLANNER_FEATURE_TYPES:
        if feature_type:
            warnings.append(f"Decomposed planner v1 ignored unsupported feature type: {feature_type}")
        return None

    display_name = str(feature.get("display_name_en_us", feature.get("display_name", ""))).strip()
    identifier_source = str(feature.get("id", feature.get("identifier", display_name))).strip()
    identifier = slugify_mod_id(identifier_source, fallback=f"generated_{feature_type}")
    if not display_name:
        display_name = derive_display_name(identifier)

    fields = dict(feature.get("fields")) if isinstance(feature.get("fields"), dict) else {}
    for key, value in feature.items():
        if key in {"intent", "depends_on", "dependencies", "fields"}:
            continue
        fields.setdefault(key, value)

    depends_on = feature.get("depends_on", feature.get("dependencies", []))
    if not isinstance(depends_on, list):
        depends_on = [depends_on] if depends_on else []

    return {
        "type": feature_type,
        "id": identifier,
        "display_name_en_us": display_name,
        "intent": str(feature.get("intent", feature.get("description", ""))),
        "depends_on": [slugify_mod_id(str(item), fallback="dependency") for item in depends_on if str(item).strip()],
        "fields": fields,
    }


def _ensure_decomposed_material_items(features: list[dict[str, Any]], mod_id: str) -> list[dict[str, Any]]:
    existing_ids = {str(feature["id"]) for feature in features}
    required_ids: list[str] = []
    vanilla_tool_materials = {"wood", "stone", "iron", "diamond", "gold", "golden", "netherite", "copper"}
    for feature in features:
        fields = feature.get("fields") if isinstance(feature.get("fields"), dict) else {}
        if feature.get("type") == "ore":
            drop = str(fields.get("drop", ""))
            if drop.startswith(f"{mod_id}:"):
                required_ids.append(drop.split(":", 1)[1])
        if feature.get("type") in {"tool", "sword"}:
            material = slugify_mod_id(str(fields.get("tool_material", "")), fallback="")
            if material and material not in vanilla_tool_materials:
                required_ids.append(material)

    injected: list[dict[str, Any]] = []
    for identifier in required_ids:
        if identifier in existing_ids:
            continue
        existing_ids.add(identifier)
        injected.append(
            {
                "type": "item",
                "id": identifier,
                "display_name_en_us": derive_display_name(identifier),
                "intent": "Material item required by decomposed feature references.",
                "depends_on": [],
                "fields": {
                    "type": "item",
                    "id": identifier,
                    "display_name_en_us": derive_display_name(identifier),
                },
            }
        )
    return [*injected, *features]


def _sort_decomposed_features(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {
        "item": 0,
        "ore": 10,
        "machine": 20,
        "tool": 30,
        "sword": 30,
        "recipe": 40,
        "progression": 50,
    }
    return [feature for _, feature in sorted(enumerate(features), key=lambda item: (priority.get(str(item[1].get("type")), 99), item[0]))]


def _extract_decomposed_feature(raw: dict[str, Any], planned: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    candidates = _decomposed_feature_candidates(raw)
    if not candidates:
        return None, ["Feature JSON response did not contain a feature object."]

    planned_type = str(planned["type"])
    planned_id = str(planned["id"])
    candidate = next(
        (
            item
            for item in candidates
            if str(item.get("type", "")).lower() == planned_type
            and slugify_mod_id(str(item.get("id", item.get("identifier", ""))), fallback="") == planned_id
        ),
        None,
    )
    if candidate is None:
        candidate = next((item for item in candidates if str(item.get("type", "")).lower() == planned_type), None)
    if candidate is None:
        return None, [f"Feature JSON response did not contain requested type/id: {planned_type}/{planned_id}."]

    feature = _flatten_decomposed_feature(candidate, planned)
    raw_type = str(feature.get("type", "")).lower()
    raw_id = slugify_mod_id(str(feature.get("id", feature.get("identifier", ""))), fallback="")
    if raw_type and raw_type != planned_type:
        warnings.append(f"Feature JSON type '{raw_type}' was forced to planned type '{planned_type}'.")
    if raw_id and raw_id != planned_id:
        warnings.append(f"Feature JSON id '{raw_id}' was forced to planned id '{planned_id}'.")
    feature["type"] = planned_type
    feature["id"] = planned_id
    feature.setdefault("display_name_en_us", planned.get("display_name_en_us", derive_display_name(planned_id)))
    return feature, warnings


def _decomposed_feature_candidates(raw: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(raw.get("feature"), dict):
        candidates.append(raw["feature"])
    if raw.get("type") or raw.get("feature_type"):
        candidates.append(raw)
    features = raw.get("features")
    if isinstance(features, list):
        candidates.extend(item for item in features if isinstance(item, dict))
    candidates.extend(item for item in _expand_typed_feature_lists(raw) if isinstance(item, dict))
    return candidates


def _flatten_decomposed_feature(candidate: dict[str, Any], planned: dict[str, Any]) -> dict[str, Any]:
    fields = dict(planned.get("fields")) if isinstance(planned.get("fields"), dict) else {}
    if isinstance(candidate.get("fields"), dict):
        fields.update(candidate["fields"])
    for key, value in candidate.items():
        if key in {"intent", "depends_on", "dependencies", "fields"}:
            continue
        fields[key] = value
    fields.setdefault("type", planned.get("type"))
    fields.setdefault("id", planned.get("id"))
    fields.setdefault("display_name_en_us", planned.get("display_name_en_us", derive_display_name(str(planned.get("id", "feature")))))
    return fields


def _fallback_decomposed_feature(planned: dict[str, Any], feature_plan: dict[str, Any]) -> dict[str, Any]:
    feature = _flatten_decomposed_feature({}, planned)
    feature_type = str(planned["type"])
    identifier = str(planned["id"])
    mod_id = str(feature_plan["mod_id"])
    feature["type"] = feature_type
    feature["id"] = identifier
    feature.setdefault("display_name_en_us", derive_display_name(identifier))

    if feature_type == "ore":
        material_id = identifier.removesuffix("_ore") or identifier
        feature.setdefault("drop", f"{mod_id}:{material_id}")
        feature.setdefault("strength", 3.0)
        feature.setdefault("resistance", 3.0)
        feature.setdefault("sound", "stone")
        feature.setdefault("requires_correct_tool", True)
        feature.setdefault("tool_tier", "iron")
        feature.setdefault(
            "worldgen",
            {
                "enabled": True,
                "dimension": "minecraft:overworld",
                "min_y": -64,
                "max_y": 32,
                "vein_size": 6,
                "veins_per_chunk": 4,
            },
        )
    elif feature_type == "machine":
        feature.setdefault("machine_kind", "compressor")
        feature.setdefault("inventory_slots", 2)
        feature.setdefault("input_slots", 1)
        feature.setdefault("output_slots", 1)
        feature.setdefault("energy_capacity", 10000)
        feature.setdefault("energy_per_tick", 20)
        feature.setdefault("max_progress", 100)
        feature.setdefault("menu_title", feature.get("display_name_en_us", derive_display_name(identifier)))
    elif feature_type == "tool":
        tool_type = next((value for value in SUPPORTED_TOOL_TYPES if identifier.endswith(f"_{value}")), "pickaxe")
        material = identifier.removesuffix(f"_{tool_type}") if identifier.endswith(f"_{tool_type}") else "iron"
        damage, speed = _tool_defaults(tool_type)
        feature.setdefault("tool_type", tool_type)
        feature.setdefault("tool_material", material or "iron")
        feature.setdefault("attack_damage_bonus", damage)
        feature.setdefault("attack_speed", speed)
    elif feature_type == "sword":
        material = identifier.removesuffix("_sword") if identifier.endswith("_sword") else "iron"
        feature.setdefault("tool_material", material or "iron")
        feature.setdefault("attack_damage_bonus", 4.0)
        feature.setdefault("attack_speed", -2.4)
    elif feature_type == "recipe":
        material_id = _first_decomposed_item_id(feature_plan) or "ruby"
        result_id = identifier
        feature.setdefault("recipe_type", "shapeless")
        feature.setdefault("ingredients", [f"{mod_id}:{material_id}"])
        feature.setdefault("result", f"{mod_id}:{result_id}")
        feature.setdefault("count", 1)
        feature.setdefault("category", "misc")
    elif feature_type == "progression":
        stage_ids = [str(item["id"]) for item in feature_plan.get("features", []) if item.get("id") != identifier]
        first_stage = stage_ids[0] if stage_ids else "start"
        last_stage = stage_ids[-1] if stage_ids else first_stage
        feature.setdefault("title", derive_display_name(identifier))
        feature.setdefault("summary", "Decomposed progression generated from the feature plan.")
        feature.setdefault("entry_stage", first_stage)
        feature.setdefault("end_stage", last_stage)
        feature.setdefault(
            "stages",
            [
                {
                    "id": slugify_mod_id(stage_id, fallback="stage"),
                    "type": "milestone",
                    "title": derive_display_name(stage_id),
                    "evidence": [stage_id],
                }
                for stage_id in stage_ids[:8]
            ]
            or [{"id": "start", "type": "milestone", "title": "Start"}],
        )
        feature.setdefault("links", [])
    return feature


def _first_decomposed_item_id(feature_plan: dict[str, Any]) -> str | None:
    for feature in feature_plan.get("features", []):
        if isinstance(feature, dict) and feature.get("type") == "item":
            return str(feature.get("id"))
    return None


def _normalize_llm_output(raw: dict, prompt: str, config: AppConfig) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    mod_id = slugify_mod_id(str(raw.get("mod_id", raw.get("id", raw.get("mod_name", raw.get("display_name", prompt))))))
    mod_name = str(raw.get("mod_name", raw.get("display_name", derive_display_name(mod_id)))) or derive_display_name(mod_id)
    package_name = str(raw.get("package", raw.get("package_name", derive_package_name(mod_id, config.default_group_prefix))))

    normalized: dict = {
        "raw_request": prompt,
        "mod_id": mod_id,
        "mod_name": mod_name,
        "display_name": mod_name,
        "package": package_name,
        "package_name": package_name,
        "version": str(raw.get("version", config.default_mod_version)),
        "description": str(raw.get("description", prompt)),
        "authors": [str(author) for author in raw.get("authors", [])],
        "license_name": str(raw.get("license_name", config.default_license_name)),
        "loader": config.loader,
        "neo_version": config.neo_version,
        "java_version": config.java_version,
        "features": [],
        "requested_features": [],
        "extra_notes": [],
    }

    raw_features = list(raw.get("features", []))
    raw_features.extend(_expand_typed_feature_lists(raw))

    normalized_features: list[dict] = []
    referenceable_ids: set[str] = set()
    pending_recipes: list[dict] = []
    pending_ores: list[dict] = []

    for feature in raw_features:
        feature_type = str(feature.get("type", "")).lower()
        if feature_type not in SUPPORTED_FEATURE_TYPES:
            warnings.append(f"Unsupported feature type from LLM ignored: {feature_type or '(missing)'}")
            continue

        if feature_type == "recipe":
            pending_recipes.append(feature)
            continue
        if feature_type == "progression":
            normalized_progression = _normalize_progression_feature(feature, warnings)
            if normalized_progression is not None:
                normalized_features.append(normalized_progression)
            continue
        if feature_type == "balance_plan":
            normalized_balance_plan = _normalize_balance_plan_feature(feature, warnings)
            if normalized_balance_plan is not None:
                normalized_features.append(normalized_balance_plan)
            continue
        if feature_type == "quest":
            normalized_quest = _normalize_quest_feature(feature, warnings)
            if normalized_quest is not None:
                normalized_features.append(normalized_quest)
            continue

        normalized_feature = _normalize_content_feature(feature, feature_type, warnings)
        if normalized_feature is None:
            continue
        normalized_features.append(normalized_feature)
        referenceable_ids.add(str(normalized_feature["id"]))
        if feature_type == "ore":
            pending_ores.append(normalized_feature)

    for ore_feature in pending_ores:
        drop_value = ore_feature.get("drop")
        if drop_value:
            ore_feature["drop"] = _normalize_reference(str(drop_value), mod_id, referenceable_ids)

    for feature in pending_recipes:
        normalized_recipe = _normalize_recipe_feature(feature, mod_id, referenceable_ids, warnings)
        if normalized_recipe is not None:
            normalized_features.append(normalized_recipe)

    normalized["features"] = normalized_features
    normalized["requested_features"] = _requested_features_from_prompt(prompt, normalized_features)
    _preserve_direct_code_intent(raw, normalized)

    unsupported_requests = _unsupported_request_warnings(prompt)
    warnings.extend(unsupported_requests)
    return normalized, warnings


def _normalize_llm_patch_output(raw: dict, existing: ModSpec, prompt: str, config: AppConfig) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    normalized: dict = {
        "raw_request": prompt,
        "mod_id": existing.mod_id,
        "mod_name": existing.display_name,
        "display_name": existing.display_name,
        "package": existing.package_name,
        "package_name": existing.package_name,
        "version": existing.version,
        "description": existing.description,
        "authors": list(existing.authors),
        "license_name": existing.license_name,
        "loader": config.loader,
        "neo_version": config.neo_version,
        "java_version": config.java_version,
        "features": [],
        "requested_features": [],
        "extra_notes": [],
    }

    raw_features = list(raw.get("features", []))
    raw_features.extend(_expand_typed_feature_lists(raw))
    normalized_features: list[dict] = []
    referenceable_ids = {
        feature.identifier
        for feature in [*existing.all_content(), *existing.entities, *existing.all_world_like(), *existing.java_extensions]
    }
    pending_recipes: list[dict] = []
    pending_ores: list[dict] = []

    for feature in raw_features:
        feature_type = str(feature.get("type", "")).lower()
        if feature_type not in SUPPORTED_FEATURE_TYPES:
            warnings.append(f"Unsupported feature type from LLM ignored: {feature_type or '(missing)'}")
            continue
        if feature_type == "recipe":
            pending_recipes.append(feature)
            continue
        if feature_type == "progression":
            normalized_progression = _normalize_progression_feature(feature, warnings)
            if normalized_progression is not None:
                normalized_features.append(normalized_progression)
            continue
        if feature_type == "balance_plan":
            normalized_balance_plan = _normalize_balance_plan_feature(feature, warnings)
            if normalized_balance_plan is not None:
                normalized_features.append(normalized_balance_plan)
            continue
        if feature_type == "quest":
            normalized_quest = _normalize_quest_feature(feature, warnings)
            if normalized_quest is not None:
                normalized_features.append(normalized_quest)
            continue
        normalized_feature = _normalize_content_feature(feature, feature_type, warnings)
        if normalized_feature is None:
            continue
        normalized_features.append(normalized_feature)
        referenceable_ids.add(str(normalized_feature["id"]))
        if feature_type == "ore":
            pending_ores.append(normalized_feature)

    for ore_feature in pending_ores:
        drop_value = ore_feature.get("drop")
        if drop_value:
            ore_feature["drop"] = _normalize_reference(str(drop_value), existing.mod_id, referenceable_ids)

    for feature in pending_recipes:
        normalized_recipe = _normalize_recipe_feature(feature, existing.mod_id, referenceable_ids, warnings)
        if normalized_recipe is not None:
            normalized_features.append(normalized_recipe)

    normalized["features"] = normalized_features
    normalized["requested_features"] = _requested_features_from_prompt(prompt, normalized_features)
    _preserve_direct_code_intent(raw, normalized)
    warnings.extend(_unsupported_request_warnings(prompt))
    return normalized, warnings


def _preserve_direct_code_intent(raw: dict, normalized: dict) -> None:
    if raw.get("requires_direct_code") is True:
        normalized["requires_direct_code"] = True
    routing_decision = raw.get("routing_decision")
    if isinstance(routing_decision, dict):
        normalized["routing_decision"] = routing_decision
    direct_code_plan = raw.get("direct_code_plan")
    if isinstance(direct_code_plan, dict):
        normalized["direct_code_plan"] = direct_code_plan
        normalized["requires_direct_code"] = True


def _expand_typed_feature_lists(raw: dict) -> list[dict]:
    expanded: list[dict] = []
    for key, feature_type in {
        "items": "item",
        "blocks": "block",
        "machines": "machine",
        "entities": "entity",
        "dimensions": "dimension",
        "biomes": "biome",
        "world_features": "world_feature",
        "structures": "structure",
        "loot_pools": "loot_pool",
        "java_extensions": "java_extension",
        "ores": "ore",
        "foods": "food",
        "swords": "sword",
        "tools": "tool",
        "armors": "armor",
        "recipes": "recipe",
        "progressions": "progression",
        "balance_plans": "balance_plan",
        "quests": "quest",
    }.items():
        for feature in raw.get(key, []):
            if isinstance(feature, dict) and "type" not in feature:
                copied = dict(feature)
                copied["type"] = feature_type
                expanded.append(copied)
            else:
                expanded.append(feature)
    return expanded


def _normalize_progression_feature(feature: dict, warnings: list[str]) -> dict | None:
    title = str(feature.get("title", feature.get("display_name_en_us", feature.get("display_name", "")))).strip()
    identifier = slugify_mod_id(str(feature.get("id", feature.get("identifier", title))).strip(), fallback="progression")
    if not title:
        title = derive_display_name(identifier)
        warnings.append(f"Progression '{identifier}' was missing title; derived '{title}'.")

    stages = []
    for raw_stage in feature.get("stages", []):
        if not isinstance(raw_stage, dict):
            continue
        stage_title = str(raw_stage.get("title", raw_stage.get("display_name_en_us", ""))).strip()
        stage_id = slugify_mod_id(str(raw_stage.get("id", raw_stage.get("identifier", stage_title))).strip(), fallback="stage")
        stage_type = str(raw_stage.get("stage_type", raw_stage.get("type", "milestone"))).lower()
        if not stage_title:
            stage_title = derive_display_name(stage_id)
        stages.append(
            {
                "id": stage_id,
                "type": stage_type,
                "title": stage_title,
                "description": str(raw_stage.get("description", "")),
                "requires": [str(item) for item in raw_stage.get("requires", [])],
                "provides": [str(item) for item in raw_stage.get("provides", [])],
                "unlocks": [str(item) for item in raw_stage.get("unlocks", [])],
                "evidence": [str(item) for item in raw_stage.get("evidence", [])],
            }
        )

    if not stages:
        warnings.append(f"Progression '{identifier}' was ignored because it has no stages.")
        return None

    links = []
    for raw_link in feature.get("links", []):
        if not isinstance(raw_link, dict):
            continue
        links.append(
            {
                "from": str(raw_link.get("from", raw_link.get("from_stage", ""))),
                "to": str(raw_link.get("to", raw_link.get("to_stage", ""))),
                "trigger": str(raw_link.get("trigger", "")),
                "requirement": str(raw_link.get("requirement", "")),
            }
        )

    return {
        "type": "progression",
        "id": identifier,
        "title": title,
        "summary": str(feature.get("summary", feature.get("description", ""))),
        "entry_stage": str(feature.get("entry_stage", "")),
        "end_stage": str(feature.get("end_stage", "")),
        "stages": stages,
        "links": links,
    }


def _normalize_balance_plan_feature(feature: dict, warnings: list[str]) -> dict | None:
    title = str(feature.get("title", feature.get("display_name_en_us", feature.get("display_name", "")))).strip()
    identifier = slugify_mod_id(str(feature.get("id", feature.get("identifier", title))).strip(), fallback="balance_plan")
    if not title:
        title = derive_display_name(identifier)
        warnings.append(f"Balance plan '{identifier}' was missing title; derived '{title}'.")
    profile = str(feature.get("profile", "standard")).lower()
    if profile not in {"easy", "standard", "expert"}:
        warnings.append(f"Balance plan '{identifier}' used unsupported profile '{profile}'; defaulted to 'standard'.")
        profile = "standard"
    return {
        "type": "balance_plan",
        "id": identifier,
        "title": title,
        "target_progression": str(feature.get("target_progression", "")),
        "profile": profile,
        "summary": str(feature.get("summary", feature.get("description", ""))),
    }


def _normalize_quest_feature(feature: dict, warnings: list[str]) -> dict | None:
    title = str(feature.get("title", feature.get("display_name_en_us", feature.get("display_name", "")))).strip()
    identifier = slugify_mod_id(str(feature.get("id", feature.get("identifier", title))).strip(), fallback="quest")
    if not title:
        title = derive_display_name(identifier)
        warnings.append(f"Quest '{identifier}' was missing title; derived '{title}'.")

    tasks = []
    for raw_task in feature.get("tasks", []):
        if not isinstance(raw_task, dict):
            continue
        task_title = str(raw_task.get("title", raw_task.get("display_name_en_us", raw_task.get("display_name", "")))).strip()
        task_id = slugify_mod_id(str(raw_task.get("id", raw_task.get("identifier", task_title))).strip(), fallback="task")
        task_type = str(raw_task.get("task_type", raw_task.get("type", "milestone"))).lower()
        if task_type not in SUPPORTED_QUEST_TASK_TYPES:
            warnings.append(f"Quest task '{task_id}' used unsupported task_type '{task_type}'; defaulted to 'milestone'.")
            task_type = "milestone"
        if not task_title:
            task_title = derive_display_name(task_id)
        tasks.append(
            {
                "id": task_id,
                "title": task_title,
                "description": str(raw_task.get("description", "")),
                "task_type": task_type,
                "target": str(raw_task.get("target", "")),
                "icon": str(raw_task.get("icon", "")),
                "parent": str(raw_task.get("parent", "")),
                "guide_text": str(raw_task.get("guide_text", "")),
                "reward_xp": _non_negative_int(raw_task.get("reward_xp", 0), 0),
            }
        )

    target_progression = str(feature.get("target_progression", ""))
    if not tasks and not target_progression:
        warnings.append(f"Quest '{identifier}' was ignored because it has no tasks or target_progression.")
        return None

    return {
        "type": "quest",
        "id": identifier,
        "title": title,
        "summary": str(feature.get("summary", feature.get("description", ""))),
        "target_progression": target_progression,
        "guidebook_id": slugify_mod_id(str(feature.get("guidebook_id", "guidebook")), fallback="guidebook"),
        "category": slugify_mod_id(str(feature.get("category", "getting_started")), fallback="getting_started"),
        "tasks": tasks,
    }


def _normalize_content_feature(feature: dict, feature_type: str, warnings: list[str]) -> dict | None:
    display_name = str(feature.get("display_name_en_us", feature.get("display_name", ""))).strip()
    identifier_source = str(feature.get("id", feature.get("identifier", ""))).strip()
    if not identifier_source and feature_type == "java_extension" and feature.get("class_name"):
        identifier_source = _camel_to_snake(str(feature["class_name"]))
    if not identifier_source:
        identifier_source = display_name
    identifier = slugify_mod_id(identifier_source, fallback=f"generated_{feature_type}")
    if not display_name:
        display_name = derive_display_name(identifier)
        warnings.append(f"Feature '{identifier}' was missing display_name_en_us; derived '{display_name}'.")

    normalized: dict = {
        "type": feature_type,
        "id": identifier,
        "display_name_en_us": display_name,
        "display_name_zh_cn": str(feature.get("display_name_zh_cn", "")).strip(),
        "description": str(feature.get("description", "")).strip(),
    }

    if feature_type == "block":
        normalized.update(
            {
                "strength": float(feature.get("strength", 1.5)),
                "resistance": float(feature.get("resistance", 1.5)),
                "sound": str(feature.get("sound", "stone")),
                "requires_correct_tool": bool(feature.get("requires_correct_tool", False)),
                "tool_tier": _normalize_tool_tier(feature.get("tool_tier", "iron"), warnings, identifier),
                "block_kind": _normalize_block_kind(feature.get("block_kind", "cube"), warnings, identifier),
                "base_block": str(feature["base_block"]) if feature.get("base_block") is not None else None,
            }
        )
        if isinstance(feature.get("behavior"), dict):
            normalized["behavior"] = _normalize_behavior(feature["behavior"])
    elif feature_type == "machine":
        machine_kind = _normalize_machine_kind(feature.get("machine_kind", "compressor"), warnings, identifier)
        storage = machine_kind == "storage"
        normalized.update(
            {
                "strength": float(feature.get("strength", 4.0)),
                "resistance": float(feature.get("resistance", 6.0)),
                "sound": str(feature.get("sound", "metal")),
                "requires_correct_tool": bool(feature.get("requires_correct_tool", True)),
                "tool_tier": _normalize_tool_tier(feature.get("tool_tier", "iron"), warnings, identifier),
                "block_kind": "cube",
                "base_block": str(feature["base_block"]) if feature.get("base_block") is not None else None,
                "machine_kind": machine_kind,
                "inventory_slots": int(feature.get("inventory_slots", 9 if storage else 2)),
                "input_slots": int(feature.get("input_slots", 9 if storage else 1)),
                "output_slots": int(feature.get("output_slots", 0 if storage else 1)),
                "energy_capacity": int(feature.get("energy_capacity", 0 if storage else 10000)),
                "energy_per_tick": int(feature.get("energy_per_tick", 0 if storage else 20)),
                "max_progress": int(feature.get("max_progress", 1 if storage else 100)),
                "menu_title": str(feature.get("menu_title", feature.get("display_name_en_us", feature.get("display_name", "")))),
            }
        )
        if isinstance(feature.get("behavior"), dict):
            normalized["behavior"] = _normalize_behavior(feature["behavior"])
    elif feature_type == "entity":
        entity_kind = _normalize_entity_kind(feature.get("entity_kind", feature.get("mob_kind", "monster")), warnings, identifier)
        category = _normalize_entity_category(feature.get("category", entity_kind), warnings, identifier)
        normalized.update(
            {
                "entity_kind": entity_kind,
                "category": category,
                "width": _positive_float(feature.get("width", 0.6), 0.6),
                "height": _positive_float(feature.get("height", 1.95), 1.95),
                "tracking_range": _positive_int(feature.get("tracking_range", 8), 8),
                "update_interval": _positive_int(feature.get("update_interval", 3), 3),
                "xp_reward": _non_negative_int(feature.get("xp_reward", 5), 5),
                "fire_immune": bool(feature.get("fire_immune", False)),
            }
        )
        if isinstance(feature.get("attributes"), dict):
            normalized["attributes"] = _normalize_entity_attributes(feature["attributes"])
        if isinstance(feature.get("drops"), list):
            normalized["drops"] = _normalize_entity_drops(feature["drops"])
        if isinstance(feature.get("spawn"), dict):
            normalized["spawn"] = _normalize_entity_spawn(feature["spawn"])
        if isinstance(feature.get("goals"), list):
            normalized["goals"] = _normalize_entity_goals(feature["goals"], warnings, identifier)
        if isinstance(feature.get("attack"), dict):
            normalized["attack"] = _normalize_entity_attack(feature["attack"], warnings, identifier)
    elif feature_type == "dimension":
        normalized.update(
            {
                "dimension_type": _normalize_choice(feature.get("dimension_type", "overworld_like"), SUPPORTED_DIMENSION_TYPES, "overworld_like", warnings, identifier, "dimension_type"),
                "biome": str(feature.get("biome", "minecraft:plains")),
                "generator": _normalize_choice(feature.get("generator", "noise"), SUPPORTED_DIMENSION_GENERATORS, "noise", warnings, identifier, "generator"),
                "min_y": int(feature.get("min_y", -64)),
                "height": _positive_int(feature.get("height", 384), 384),
                "logical_height": _positive_int(feature.get("logical_height", feature.get("height", 384)), 384),
                "coordinate_scale": _positive_float(feature.get("coordinate_scale", 1.0), 1.0),
                "ambient_light": _clamp(_non_negative_float(feature.get("ambient_light", 0.0), 0.0), 0.0, 1.0),
                "has_skylight": bool(feature.get("has_skylight", True)),
                "has_ceiling": bool(feature.get("has_ceiling", False)),
                "ultrawarm": bool(feature.get("ultrawarm", False)),
                "natural": bool(feature.get("natural", True)),
                "bed_works": bool(feature.get("bed_works", True)),
                "respawn_anchor_works": bool(feature.get("respawn_anchor_works", False)),
            }
        )
        if feature.get("fixed_time") is not None:
            normalized["fixed_time"] = int(feature["fixed_time"])
    elif feature_type == "biome":
        normalized.update(
            {
                "temperature": float(feature.get("temperature", 0.8)),
                "downfall": _clamp(_non_negative_float(feature.get("downfall", 0.4), 0.4), 0.0, 1.0),
                "has_precipitation": bool(feature.get("has_precipitation", True)),
                "sky_color": _rgb_int(feature.get("sky_color", 7907327), 7907327),
                "water_color": _rgb_int(feature.get("water_color", 4159204), 4159204),
                "water_fog_color": _rgb_int(feature.get("water_fog_color", 329011), 329011),
                "fog_color": _rgb_int(feature.get("fog_color", 12638463), 12638463),
                "features": [str(item) for item in feature.get("features", [])],
            }
        )
        if feature.get("grass_color") is not None:
            normalized["grass_color"] = _rgb_int(feature.get("grass_color"), 0)
        if feature.get("foliage_color") is not None:
            normalized["foliage_color"] = _rgb_int(feature.get("foliage_color"), 0)
    elif feature_type == "world_feature":
        min_y = int(feature.get("min_y", -64))
        max_y = int(feature.get("max_y", 32))
        if min_y >= max_y:
            max_y = min_y + 1
        normalized.update(
            {
                "feature_kind": _normalize_choice(feature.get("feature_kind", "ore_vein"), SUPPORTED_WORLD_FEATURE_KINDS, "ore_vein", warnings, identifier, "feature_kind"),
                "target_block": str(feature.get("target_block", "minecraft:stone_ore_replaceables")),
                "placed_block": str(feature.get("placed_block", feature.get("block", "minecraft:diamond_ore"))),
                "biomes": str(feature.get("biomes", "#minecraft:is_overworld")),
                "step": _normalize_choice(feature.get("step", "underground_ores"), SUPPORTED_WORLDGEN_STEPS, "underground_ores", warnings, identifier, "step"),
                "vein_size": _positive_int(feature.get("vein_size", 6), 6),
                "veins_per_chunk": _positive_int(feature.get("veins_per_chunk", feature.get("count", 4)), 4),
                "min_y": min_y,
                "max_y": max_y,
                "discard_chance_on_air_exposure": _clamp(_non_negative_float(feature.get("discard_chance_on_air_exposure", 0.0), 0.0), 0.0, 1.0),
            }
        )
    elif feature_type == "structure":
        spacing = _positive_int(feature.get("spacing", 32), 32)
        separation = _non_negative_int(feature.get("separation", 8), 8)
        normalized.update(
            {
                "structure_kind": _normalize_choice(feature.get("structure_kind", "jigsaw"), SUPPORTED_STRUCTURE_KINDS, "jigsaw", warnings, identifier, "structure_kind"),
                "biomes": str(feature.get("biomes", "#minecraft:is_overworld")),
                "step": _normalize_choice(feature.get("step", "surface_structures"), SUPPORTED_STRUCTURE_STEPS, "surface_structures", warnings, identifier, "step"),
                "terrain_adaptation": _normalize_choice(feature.get("terrain_adaptation", "beard_thin"), SUPPORTED_TERRAIN_ADAPTATION, "beard_thin", warnings, identifier, "terrain_adaptation"),
                "spacing": spacing,
                "separation": min(separation, max(0, spacing - 1)),
                "salt": _non_negative_int(feature.get("salt", 14357617), 14357617),
                "size": _positive_int(feature.get("size", 1), 1),
                "start_height": int(feature.get("start_height", 0)),
            }
        )
        if feature.get("loot_table") is not None:
            normalized["loot_table"] = str(feature["loot_table"])
    elif feature_type == "loot_pool":
        normalized.update(
            {
                "table_kind": _normalize_choice(feature.get("table_kind", "chest"), SUPPORTED_LOOT_TABLE_KINDS, "chest", warnings, identifier, "table_kind"),
                "rolls": _positive_int(feature.get("rolls", 1), 1),
                "entries": _normalize_loot_entries(feature.get("entries", [])),
            }
        )
    elif feature_type == "java_extension":
        class_name = str(feature.get("class_name", "")).strip()
        if not class_name:
            class_name = "".join(part.capitalize() for part in identifier.split("_") if part) or "SafeInfoExtension"
        if not re.fullmatch(r"^[A-Z][A-Za-z0-9]*$", class_name):
            class_name = "".join(part[:1].upper() + part[1:] for part in re.split(r"[^A-Za-z0-9]+", class_name) if part) or "SafeInfoExtension"
        methods = _normalize_java_extension_methods(feature.get("methods", []), warnings, identifier)
        if not methods:
            methods = [
                {
                    "name": "describe",
                    "return_type": "String",
                    "return_value": "Controlled Java extension generated from ModSpec.",
                    "explanation": "Default safe method inserted because the planner omitted methods.",
                }
            ]
        allowed_imports = [
            str(import_line)
            for import_line in feature.get("allowed_imports", [])
            if str(import_line) in SUPPORTED_JAVA_EXTENSION_IMPORTS
        ]
        normalized.update(
            {
                "class_name": class_name,
                "purpose": str(feature.get("purpose", "Add a small managed helper class inside the Java extension sandbox.")),
                "methods": methods,
                "allowed_imports": allowed_imports,
                "explanation": str(feature.get("explanation", "This is an additive managed class; the generator does not edit existing Java sources.")),
            }
        )
    elif feature_type == "ore":
        normalized.update(
            {
                "strength": float(feature.get("strength", 3.0)),
                "resistance": float(feature.get("resistance", 3.0)),
                "sound": str(feature.get("sound", "stone")),
                "requires_correct_tool": bool(feature.get("requires_correct_tool", True)),
                "tool_tier": _normalize_tool_tier(feature.get("tool_tier", "iron"), warnings, identifier),
                "block_kind": "cube",
                "base_block": str(feature["base_block"]) if feature.get("base_block") is not None else None,
                "drop": feature.get("drop"),
                "min_drop": int(feature.get("min_drop", 1)),
                "max_drop": int(feature.get("max_drop", 1)),
                "affected_by_fortune": bool(feature.get("affected_by_fortune", False)),
                "silk_touch_drops_self": bool(feature.get("silk_touch_drops_self", False)),
            }
        )
        if isinstance(feature.get("worldgen"), dict):
            normalized["worldgen"] = {
                "enabled": bool(feature["worldgen"].get("enabled", False)),
                "dimension": str(feature["worldgen"].get("dimension", "minecraft:overworld")),
                "min_y": int(feature["worldgen"].get("min_y", -64)),
                "max_y": int(feature["worldgen"].get("max_y", 32)),
                "vein_size": int(feature["worldgen"].get("vein_size", 6)),
                "veins_per_chunk": int(feature["worldgen"].get("veins_per_chunk", 4)),
            }
        if isinstance(feature.get("behavior"), dict):
            normalized["behavior"] = _normalize_behavior(feature["behavior"])
    elif feature_type == "food":
        normalized.update(
            {
                "nutrition": int(feature.get("nutrition", 4)),
                "saturation": float(feature.get("saturation", 0.3)),
                "effects": [
                    {
                        "effect": str(effect.get("effect", "")),
                        "duration_ticks": int(effect.get("duration_ticks", 0)),
                        "amplifier": int(effect.get("amplifier", 0)),
                        "probability": float(effect.get("probability", 1.0)),
                    }
                    for effect in feature.get("effects", [])
                    if isinstance(effect, dict)
                ],
            }
        )
    elif feature_type == "sword":
        normalized.update(
            {
                "attack_damage_bonus": float(feature.get("attack_damage_bonus", 4.0)),
                "attack_speed": float(feature.get("attack_speed", -2.4)),
                "tool_material": _normalize_tool_material(feature.get("tool_material", "iron"), warnings, identifier),
            }
        )
        if isinstance(feature.get("on_hit"), dict):
            normalized["on_hit"] = {
                "type": str(feature["on_hit"].get("type", "")),
                "seconds": int(feature["on_hit"].get("seconds", 0)),
            }
        if isinstance(feature.get("behavior"), dict):
            normalized["behavior"] = _normalize_behavior(feature["behavior"])
    elif feature_type == "tool":
        tool_type = _normalize_tool_type(feature.get("tool_type", "pickaxe"), warnings, identifier)
        default_attack, default_speed = _tool_defaults(tool_type)
        normalized.update(
            {
                "tool_type": tool_type,
                "tool_material": _normalize_tool_material(feature.get("tool_material", "iron"), warnings, identifier),
                "attack_damage_bonus": float(feature.get("attack_damage_bonus", default_attack)),
                "attack_speed": float(feature.get("attack_speed", default_speed)),
            }
        )
    elif feature_type == "armor":
        normalized.update(
            {
                "armor_type": _normalize_armor_type(feature.get("armor_type", "helmet"), warnings, identifier),
                "armor_material": _normalize_armor_material(feature.get("armor_material", "iron"), warnings, identifier),
            }
        )
    elif feature_type == "item":
        if isinstance(feature.get("behavior"), dict):
            normalized["behavior"] = _normalize_behavior(feature["behavior"])
    return normalized


def _normalize_choice(
    value: object,
    supported: set[str],
    default: str,
    warnings: list[str],
    identifier: str,
    field_name: str,
) -> str:
    normalized = str(value or default).lower()
    if normalized not in supported:
        warnings.append(f"Feature '{identifier}' requested unsupported {field_name} '{normalized}', normalized to '{default}'.")
        return default
    return normalized


def _rgb_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return int(_clamp(float(parsed), 0, 0xFFFFFF))


def _normalize_loot_entries(entries: object) -> list[dict]:
    normalized: list[dict] = []
    if not isinstance(entries, list):
        entries = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("item"):
            continue
        min_count = _positive_int(entry.get("min_count", 1), 1)
        max_count = max(min_count, _positive_int(entry.get("max_count", min_count), min_count))
        normalized.append(
            {
                "item": str(entry["item"]),
                "min_count": min_count,
                "max_count": max_count,
                "weight": _positive_int(entry.get("weight", 1), 1),
                "chance": _clamp(_non_negative_float(entry.get("chance", 1.0), 1.0), 0.0, 1.0),
            }
        )
    if not normalized:
        normalized.append({"item": "minecraft:emerald", "min_count": 1, "max_count": 1, "weight": 1, "chance": 1.0})
    return normalized


def _normalize_java_extension_methods(methods: object, warnings: list[str], identifier: str) -> list[dict]:
    normalized: list[dict] = []
    if not isinstance(methods, list):
        warnings.append(f"Java extension '{identifier}' methods were not a list; default method will be used.")
        return normalized
    for method in methods:
        if not isinstance(method, dict):
            continue
        normalized.append(
            {
                "name": str(method.get("name", "describe")),
                "return_type": str(method.get("return_type", "String")),
                "return_value": str(method.get("return_value", "")),
                "explanation": str(method.get("explanation", "")),
            }
        )
    return normalized


def _normalize_behavior(behavior: dict) -> dict:
    events = [
        _normalize_behavior_event(event)
        for event in behavior.get("events", [])
        if isinstance(event, dict)
    ]
    normalized = {
        "type": str(behavior.get("type", "event_action" if events else "")),
        "amount": float(behavior["amount"]) if behavior.get("amount") is not None else None,
        "effect": str(behavior["effect"]) if behavior.get("effect") is not None else None,
        "duration_ticks": int(behavior["duration_ticks"]) if behavior.get("duration_ticks") is not None else None,
        "amplifier": int(behavior.get("amplifier", 0)),
        "cooldown_ticks": int(behavior.get("cooldown_ticks", 0)),
        "consume": bool(behavior.get("consume", False)),
    }
    if events:
        normalized["events"] = events
    return normalized


def _normalize_behavior_event(event: dict) -> dict:
    normalized = {
        "trigger": str(event.get("trigger", event.get("event", ""))),
        "triggers": [str(trigger) for trigger in event.get("triggers", []) if str(trigger).strip()],
        "trigger_mode": str(event.get("trigger_mode", "any")),
        "conditions": [
            _normalize_behavior_condition(condition)
            for condition in event.get("conditions", [])
            if isinstance(condition, dict)
        ],
        "actions": [
            _normalize_behavior_action(action)
            for action in event.get("actions", [])
            if isinstance(action, dict)
        ],
        "cooldown_ticks": int(event.get("cooldown_ticks", 0)),
        "interval_ticks": int(event.get("interval_ticks", 0)),
        "window_ticks": int(event.get("window_ticks", 0)),
        "state_key": str(event.get("state_key")) if event.get("state_key") is not None else None,
        "state_value": event.get("state_value"),
        "resource": str(event.get("resource")) if event.get("resource") is not None else None,
        "resource_amount": float(event["resource_amount"]) if event.get("resource_amount") is not None else None,
    }
    return {key: value for key, value in normalized.items() if value not in (None, [], "")}


def _normalize_behavior_action(action: dict) -> dict:
    normalized: dict[str, Any] = {
        "type": str(action.get("type", action.get("action", ""))),
        "target": str(action.get("target", "self")),
    }
    for key in ("effect", "particle", "sound"):
        if action.get(key) is not None:
            normalized[key] = str(action[key])
    for key in ("amount", "volume", "pitch"):
        if action.get(key) is not None:
            normalized[key] = float(action[key])
    for key in ("duration_ticks", "amplifier", "seconds", "count", "cooldown_ticks"):
        if action.get(key) is not None:
            normalized[key] = int(action[key])
    for key in ("state_key", "state_value", "state_delta", "resource", "resource_amount", "delay_ticks", "chain_trigger", "chain_target", "chain_window_ticks"):
        if action.get(key) is not None:
            value = action[key]
            if key in {"state_value"}:
                normalized[key] = value
            elif key in {"state_key", "resource", "chain_trigger", "chain_target"}:
                normalized[key] = str(value)
            elif key in {"state_delta", "resource_amount"}:
                normalized[key] = float(value)
            else:
                normalized[key] = int(value)
    return normalized


def _normalize_behavior_condition(condition: dict) -> dict:
    normalized: dict[str, Any] = {
        "type": str(condition.get("type", condition.get("condition", ""))),
    }
    if condition.get("threshold") is not None:
        normalized["threshold"] = float(condition["threshold"])
    if condition.get("chance") is not None:
        normalized["chance"] = float(condition["chance"])
    if condition.get("target") is not None:
        normalized["target"] = str(condition["target"])
    if condition.get("state_key") is not None:
        normalized["state_key"] = str(condition["state_key"])
    if condition.get("state_value") is not None:
        normalized["state_value"] = condition["state_value"]
    if condition.get("resource") is not None:
        normalized["resource"] = str(condition["resource"])
    if condition.get("resource_amount") is not None:
        normalized["resource_amount"] = float(condition["resource_amount"])
    if condition.get("window_ticks") is not None:
        normalized["window_ticks"] = int(condition["window_ticks"])
    return normalized


def _normalize_entity_attributes(attributes: dict) -> dict:
    return {
        "max_health": _positive_float(attributes.get("max_health", 20.0), 20.0),
        "movement_speed": _positive_float(attributes.get("movement_speed", 0.25), 0.25),
        "attack_damage": _non_negative_float(attributes.get("attack_damage", 3.0), 3.0),
        "armor": _non_negative_float(attributes.get("armor", 0.0), 0.0),
        "follow_range": _positive_float(attributes.get("follow_range", 24.0), 24.0),
        "knockback_resistance": _non_negative_float(attributes.get("knockback_resistance", 0.0), 0.0),
    }


def _normalize_entity_drops(drops: list) -> list[dict]:
    normalized: list[dict] = []
    for drop in drops:
        if not isinstance(drop, dict) or not drop.get("item"):
            continue
        min_count = _positive_int(drop.get("min_count", 1), 1)
        max_count = max(min_count, _positive_int(drop.get("max_count", min_count), min_count))
        normalized.append(
            {
                "item": str(drop["item"]),
                "min_count": min_count,
                "max_count": max_count,
                "chance": _clamp(_non_negative_float(drop.get("chance", 1.0), 1.0), 0.0, 1.0),
            }
        )
    return normalized


def _normalize_entity_spawn(spawn: dict) -> dict:
    min_count = _positive_int(spawn.get("min_count", 1), 1)
    max_count = max(min_count, _positive_int(spawn.get("max_count", 3), 3))
    return {
        "enabled": bool(spawn.get("enabled", True)),
        "biomes": str(spawn.get("biomes", "#minecraft:is_overworld")),
        "weight": _positive_int(spawn.get("weight", 80), 80),
        "min_count": min_count,
        "max_count": max_count,
        "placement": "on_ground",
    }


def _normalize_entity_goals(goals: list, warnings: list[str], identifier: str) -> list[dict]:
    normalized: list[dict] = []
    aliases = {
        "melee": "melee_attack",
        "wander": "random_stroll",
        "stroll": "random_stroll",
        "look_at": "look_at_player",
        "look": "look_at_player",
        "hurt_by": "hurt_by_target",
        "target": "target_player",
        "target_nearest_player": "target_player",
    }
    for goal in goals:
        if not isinstance(goal, dict):
            continue
        goal_type = str(goal.get("type", goal.get("goal", ""))).lower()
        goal_type = aliases.get(goal_type, goal_type)
        if goal_type not in SUPPORTED_ENTITY_GOALS:
            warnings.append(f"Entity '{identifier}' requested unsupported goal '{goal_type}', ignored.")
            continue
        normalized_goal: dict[str, Any] = {
            "type": goal_type,
            "priority": _non_negative_int(goal.get("priority", 0), 0),
            "target": str(goal.get("target", "minecraft:player")),
        }
        if goal.get("speed") is not None:
            normalized_goal["speed"] = _positive_float(goal.get("speed"), 1.0)
        if goal.get("distance") is not None:
            normalized_goal["distance"] = _positive_float(goal.get("distance"), 8.0)
        normalized.append(normalized_goal)
    return normalized


def _normalize_entity_attack(attack: dict, warnings: list[str], identifier: str) -> dict:
    attack_type = str(attack.get("type", attack.get("attack_type", "melee"))).lower()
    aliases = {"none": "none", "no_attack": "none", "passive": "none", "melee_attack": "melee"}
    attack_type = aliases.get(attack_type, attack_type)
    if attack_type not in SUPPORTED_ENTITY_ATTACK_TYPES:
        warnings.append(f"Entity '{identifier}' requested unsupported attack type '{attack_type}', normalized to 'melee'.")
        attack_type = "melee"
    normalized: dict[str, Any] = {
        "type": attack_type,
        "speed": _positive_float(attack.get("speed", 1.0), 1.0),
    }
    if attack.get("damage") is not None:
        normalized["damage"] = _non_negative_float(attack.get("damage"), 0.0)
    elif attack_type == "none":
        normalized["damage"] = 0.0
    return normalized


def _normalize_recipe_feature(feature: dict, mod_id: str, referenceable_ids: set[str], warnings: list[str]) -> dict | None:
    recipe_type = str(feature.get("recipe_type", "shaped")).lower()
    identifier = slugify_mod_id(str(feature.get("id", feature.get("identifier", "generated_recipe"))), fallback="generated_recipe")
    result = feature.get("result")
    if not result:
        warnings.append(f"LLM recipe '{identifier}' is missing result and was ignored.")
        return None

    normalized = {
        "type": "recipe",
        "id": identifier,
        "recipe_type": recipe_type,
        "result": _normalize_reference(str(result), mod_id, referenceable_ids),
        "count": int(feature.get("count", 1)),
        "category": str(feature.get("category", "misc")),
        "group": feature.get("group"),
    }

    if recipe_type == "shapeless":
        ingredients = [str(item) for item in feature.get("ingredients", [])]
        normalized["ingredients"] = [_normalize_reference(item, mod_id, referenceable_ids) for item in ingredients]
        normalized["pattern"] = []
        normalized["keys"] = {}
    else:
        keys = {str(key): _normalize_reference(str(value), mod_id, referenceable_ids) for key, value in feature.get("keys", {}).items()}
        normalized["pattern"] = [str(row) for row in feature.get("pattern", [])]
        normalized["keys"] = keys
        normalized["ingredients"] = []
    return normalized


def _normalize_reference(reference: str, mod_id: str, referenceable_ids: set[str]) -> str:
    if ":" in reference:
        namespace, value = reference.split(":", 1)
        return f"{namespace}:{slugify_mod_id(value, fallback='generated_ref')}"
    normalized_id = slugify_mod_id(reference, fallback="generated_ref")
    if normalized_id in referenceable_ids:
        return f"{mod_id}:{normalized_id}"
    return f"{mod_id}:{normalized_id}"


def _camel_to_snake(value: str) -> str:
    value = re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()
    return re.sub(r"[^a-z0-9_]+", "_", value).strip("_")


def _normalize_entity_kind(value: object, warnings: list[str], identifier: str) -> str:
    normalized = str(value or "monster").lower()
    aliases = {"mob": "monster", "hostile": "monster", "animal": "creature", "passive": "creature"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_ENTITY_KINDS:
        warnings.append(f"Entity '{identifier}' requested unsupported entity_kind '{normalized}', normalized to 'monster'.")
        return "monster"
    return normalized


def _normalize_entity_category(value: object, warnings: list[str], identifier: str) -> str:
    normalized = str(value or "monster").lower()
    aliases = {"mob": "monster", "hostile": "monster", "animal": "creature", "passive": "creature"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_ENTITY_CATEGORIES:
        warnings.append(f"Entity '{identifier}' requested unsupported category '{normalized}', normalized to 'monster'.")
        return "monster"
    return normalized


def _positive_float(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_float(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize_tool_material(value: object, warnings: list[str], identifier: str) -> str:
    normalized = str(value or "iron").lower()
    if normalized not in SUPPORTED_TOOL_MATERIALS:
        warnings.append(f"Feature '{identifier}' requested unsupported tool_material '{normalized}', normalized to 'iron'.")
        return "iron"
    return normalized


def _normalize_tool_type(value: object, warnings: list[str], identifier: str) -> str:
    normalized = str(value or "pickaxe").lower()
    aliases = {
        "pick": "pickaxe",
        "pick_axe": "pickaxe",
        "spade": "shovel",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_TOOL_TYPES:
        warnings.append(f"Tool '{identifier}' requested unsupported tool_type '{normalized}', normalized to 'pickaxe'.")
        return "pickaxe"
    return normalized


def _normalize_armor_type(value: object, warnings: list[str], identifier: str) -> str:
    normalized = str(value or "helmet").lower()
    aliases = {
        "chest": "chestplate",
        "body": "chestplate",
        "legs": "leggings",
        "pants": "leggings",
        "boot": "boots",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_ARMOR_TYPES:
        warnings.append(f"Armor '{identifier}' requested unsupported armor_type '{normalized}', normalized to 'helmet'.")
        return "helmet"
    return normalized


def _normalize_armor_material(value: object, warnings: list[str], identifier: str) -> str:
    normalized = str(value or "iron").lower()
    aliases = {"golden": "gold", "chain": "chainmail"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_ARMOR_MATERIALS:
        warnings.append(f"Armor '{identifier}' requested unsupported armor_material '{normalized}', normalized to 'iron'.")
        return "iron"
    return normalized


def _tool_defaults(tool_type: str) -> tuple[float, float]:
    defaults = {
        "pickaxe": (1.0, -2.8),
        "axe": (5.0, -3.0),
        "shovel": (1.5, -3.0),
        "hoe": (0.0, -3.0),
    }
    return defaults.get(tool_type, defaults["pickaxe"])


def _normalize_tool_tier(value: object, warnings: list[str], identifier: str) -> str:
    normalized = str(value or "iron").lower()
    if normalized not in SUPPORTED_TOOL_TIERS:
        warnings.append(f"Block '{identifier}' requested unsupported tool_tier '{normalized}', normalized to 'iron'.")
        return "iron"
    return normalized


def _normalize_block_kind(value: object, warnings: list[str], identifier: str) -> str:
    normalized = str(value or "cube").lower()
    aliases = {
        "stair": "stairs",
        "steps": "stairs",
        "half_block": "slab",
        "pressureplate": "pressure_plate",
        "fencegate": "fence_gate",
        "trap_door": "trapdoor",
        "trap door": "trapdoor",
        "normal": "cube",
        "solid": "cube",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_BLOCK_KINDS:
        warnings.append(f"Block '{identifier}' requested unsupported block_kind '{normalized}', normalized to 'cube'.")
        return "cube"
    return normalized


def _normalize_machine_kind(value: object, warnings: list[str], identifier: str) -> str:
    normalized = str(value or "compressor").lower()
    aliases = {
        "altar": "magic_altar",
        "magic table": "magic_altar",
        "upgrade": "upgrade_table",
        "upgrader": "upgrade_table",
        "container": "storage",
        "chest": "storage",
        "smelter": "furnace",
        "press": "compressor",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_MACHINE_KINDS:
        warnings.append(f"Machine '{identifier}' requested unsupported machine_kind '{normalized}', normalized to 'compressor'.")
        return "compressor"
    return normalized


def _requested_features_from_prompt(prompt: str, features: list[dict]) -> list[str]:
    labels = {
        "item": "Items",
        "block": "Blocks",
        "machine": "Machines",
        "entity": "Entities",
        "dimension": "Dimensions",
        "biome": "Biomes",
        "world_feature": "World Features",
        "structure": "Structures",
        "loot_pool": "Loot Pools",
        "java_extension": "Java Extensions",
        "ore": "Ores",
        "food": "Foods",
        "sword": "Swords",
        "tool": "Tools",
        "armor": "Armor",
        "recipe": "Recipes",
        "progression": "Progression",
        "balance_plan": "Balance Planner",
        "quest": "Quests",
    }
    requested = []
    for feature in features:
        label = labels.get(str(feature.get("type", "")).lower())
        if label and label not in requested:
            requested.append(label)
        if str(feature.get("type", "")).lower() == "machine":
            for machine_label in ("BlockEntity", "GUI"):
                if machine_label not in requested:
                    requested.append(machine_label)
    if (any(token in prompt.lower() for token in ("entity", "mob", "monster", "creature", "pet", "boss", "npc")) or "实体" in prompt) and "Entities" not in requested:
        requested.append("Entities")
    if ("gui" in prompt.lower() or "界面" in prompt) and "GUI" not in requested:
        requested.append("GUI")
    if ("worldgen" in prompt.lower() or "世界生成" in prompt) and "Worldgen" not in requested:
        requested.append("Worldgen")
    if any(token in prompt.lower() for token in ("dimension", "biome", "structure", "world feature", "loot pool", "vein")):
        for label in ("Dimensions", "Biomes", "World Features", "Structures", "Loot Pools"):
            if label not in requested:
                requested.append(label)
    if any(token in prompt.lower() for token in ("java extension", "controlled java extension", "safe java extension")) or "受控 java 扩展" in prompt.lower():
        if "Java Extensions" not in requested:
            requested.append("Java Extensions")
    if any(token in prompt.lower() for token in ("progression", "gameplay loop", "gameplay route")) or any(token in prompt for token in ("玩法线", "成长路线", "玩法路线", "维度推进")):
        if "Progression" not in requested:
            requested.append("Progression")
    if any(token in prompt.lower() for token in ("balance", "economy", "rarity", "loot weight", "machine cost", "energy cost")) or any(token in prompt for token in ("经济系统", "平衡", "稀有度", "机器耗时", "能量消耗", "战利品权重")):
        if "Balance Planner" not in requested:
            requested.append("Balance Planner")
    if any(token in prompt.lower() for token in ("quest", "questline", "task chain", "advancement", "guidebook", "guide book", "patchouli")) or any(token in prompt for token in ("任务", "任务链", "成就", "引导", "指南")):
        for label in ("Quests", "Advancements", "Guidebook"):
            if label not in requested:
                requested.append(label)
    return requested


def _unsupported_request_warnings(prompt: str) -> list[str]:
    warnings: list[str] = []
    lowered = prompt.lower()
    gui_supported_by_machine = any(
        token in lowered
        for token in ("machine", "compressor", "furnace machine", "upgrade table", "magic altar", "storage block")
    )
    checks = {
        "GUI": ["gui", "screen", "界面"],
    }
    for label, tokens in checks.items():
        if label == "GUI" and gui_supported_by_machine:
            continue
        if any(_prompt_contains_token(lowered, prompt, token) for token in tokens):
            warnings.append(f"Prompt requested unsupported content category '{label}'. It was not added to the generated ModSpec.")
    return warnings


def _prompt_contains_token(lowered: str, prompt: str, token: str) -> bool:
    if token.isascii():
        return re.search(rf"\b{re.escape(token)}\b", lowered) is not None
    return token in prompt


def _merge_preview(existing: ModSpec, patch: ModSpec) -> ModSpec:
    merged = ModSpec.from_dict(existing.to_dict())
    for collection_name in (
        "items",
        "blocks",
        "machines",
        "entities",
        "dimensions",
        "biomes",
        "world_features",
        "structures",
        "loot_pools",
        "java_extensions",
        "ores",
        "foods",
        "swords",
        "tools",
        "armors",
        "progressions",
        "balance_plans",
        "quests",
    ):
        existing_list = getattr(merged, collection_name)
        patch_list = getattr(patch, collection_name)
        for feature in patch_list:
            current = next((item for item in existing_list if item.identifier == feature.identifier), None)
            if current is None:
                existing_list.append(feature)
            else:
                existing_list[existing_list.index(current)] = feature

    recipe_map = {recipe.identifier: recipe for recipe in merged.recipes}
    for recipe in patch.recipes:
        recipe_map[recipe.identifier] = recipe
    merged.recipes = list(recipe_map.values())
    return merged
