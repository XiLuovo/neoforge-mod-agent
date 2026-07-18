from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AppConfig
from .evidence_writer import AgentEvidenceWriter
from .llm_output_normalizer import (
    DECOMPOSED_PLANNER_NORMALIZATION as DECOMPOSED_NORMALIZATION,
    VANILLA_RECIPE_REFERENCE_IDS,
    normalize_llm_modspec_output,
    normalize_llm_patch_output,
)
from .feature_catalog import FeatureMergePolicy, iter_feature_kind_definitions
from .java_extension_generator import SUPPORTED_JAVA_EXTENSION_IMPORTS
from .knowledge_base import NeoForgeKnowledgeBase, expand_knowledge_query, summarize_knowledge_hits
from .llm_client import DEFAULT_LLM_SCHEMA_RETRIES, LLMClient, check_llm_provider_health, get_llm_provider_metadata, inspect_llm_provider_config
from .models import BlockSpec, FoodSpec, ItemSpec, ModSpec, OreSpec, ProgressionLinkSpec, ProgressionSpec, RecipeSpec, SwordSpec
from .schema import get_modspec_schema
from .tools import derive_display_name, derive_package_name, slugify_mod_id
from .validator import SUPPORTED_ITEM_BEHAVIORS, validate_mod_spec


DECOMPOSED_PLANNER_FEATURE_TYPES = {
    "item",
    "ore",
    "machine",
    "tool",
    "sword",
    "recipe",
    "progression",
}
SUPPORTED_RECIPE_TYPES = {"shaped", "shapeless"}
SUPPORTED_PROGRESSION_STAGE_TYPES = {
    "ore",
    "material",
    "recipe",
    "machine",
    "equipment",
    "item",
    "block",
    "entity",
    "structure",
    "loot_pool",
    "dimension",
    "biome",
    "world_feature",
    "milestone",
}
DECOMPOSED_RECIPE_TYPE_ALIASES = {
    "crafting_shaped": "shaped",
    "minecraft:crafting_shaped": "shaped",
    "crafting_shapeless": "shapeless",
    "minecraft:crafting_shapeless": "shapeless",
    "craft": "shaped",
    "crafting": "shaped",
    "compressor": "shapeless",
    "machine": "shapeless",
    "smelting": "shapeless",
}
DECOMPOSED_STAGE_TYPE_ALIASES = {
    "start": "milestone",
    "end": "milestone",
    "finish": "milestone",
    "complete": "milestone",
    "completion": "milestone",
    "tool": "equipment",
    "tools": "equipment",
    "sword": "equipment",
}


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
    bad_json_outputs: list[dict[str, Any]] = field(default_factory=list)
    decomposed_feature_plan_raw_json: dict | None = None
    decomposed_feature_plan_json: dict | None = None
    decomposed_feature_json_outputs: list[dict[str, Any]] = field(default_factory=list)
    decomposed_composed_raw_json: dict | None = None
    decomposed_bad_raw_outputs: list[dict[str, Any]] = field(default_factory=list)
    decomposed_modify_existing_context: dict | None = None
    decomposed_modify_feature_plan_raw_json: dict | None = None
    decomposed_modify_feature_plan_json: dict | None = None
    decomposed_modify_feature_patch_outputs: list[dict[str, Any]] = field(default_factory=list)
    decomposed_modify_composed_patch_raw_json: dict | None = None
    decomposed_modify_merge_preview_json: dict | None = None
    decomposed_modify_bad_raw_outputs: list[dict[str, Any]] = field(default_factory=list)


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

        normalization = normalize_llm_modspec_output(raw_json, prompt, config)
        normalized = normalization.normalized_json
        artifacts.normalized_json = normalized
        artifacts.warnings.extend(normalization.warnings)

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

    composed_features, hardening_warnings = _harden_decomposed_composed_features(composed_features, feature_plan)
    artifacts.warnings.extend(hardening_warnings)
    for record, feature in zip(artifacts.decomposed_feature_json_outputs, composed_features):
        record["feature"] = feature
        record["warnings"].extend(
            warning
            for warning in hardening_warnings
            if f"'{feature.get('id')}'" in warning or f"`{feature.get('id')}`" in warning
        )

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

    normalization = normalize_llm_modspec_output(composed_raw, prompt, config)
    normalized = normalization.normalized_json
    artifacts.normalized_json = normalized
    artifacts.warnings.extend(normalization.warnings)
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

        normalization = normalize_llm_patch_output(raw_json, existing, change_request, config)
        normalized = normalization.normalized_json
        artifacts.normalized_json = normalized
        artifacts.warnings.extend(normalization.warnings)

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


def plan_modification_with_decomposed_llm(
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
    existing_context = _compact_decomposed_modify_existing_context(existing, change_request)
    system_prompt = _build_decomposed_modify_plan_system_prompt(language, rag_context=rag_context)
    user_prompt = "\n".join(
        [
            "Existing workspace compact context JSON:",
            json.dumps(existing_context, ensure_ascii=False, indent=2),
            "",
            "Change Request:",
            change_request,
            "",
            "Return only the decomposed modify feature plan JSON for the requested change.",
        ]
    )
    artifacts = PlannerArtifacts(
        planner_mode="decomposed-modify",
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
        decomposed_modify_existing_context=existing_context,
    )

    feature_plan_raw = _complete_json_with_repair(
        client,
        system_prompt,
        user_prompt,
        artifacts,
        invalid_error="Decomposed modify planner returned invalid feature-plan JSON.",
    )
    artifacts.decomposed_modify_feature_plan_raw_json = feature_plan_raw
    feature_plan, plan_warnings = _normalize_decomposed_modify_feature_plan(feature_plan_raw, existing, change_request)
    artifacts.decomposed_modify_feature_plan_json = feature_plan
    artifacts.warnings.extend(plan_warnings)
    actionable_features = [
        feature
        for feature in feature_plan["features"]
        if str(feature.get("operation", "add")).lower() != "skip"
    ]
    if not actionable_features:
        artifacts.warnings.append("Decomposed modify plan contained no actionable features; returning an empty patch ModSpec.")

    composed_features: list[dict[str, Any]] = []
    for planned_feature in actionable_features:
        feature_system_prompt = _build_decomposed_modify_feature_system_prompt(str(planned_feature["type"]), language)
        feature_user_prompt = _decomposed_modify_feature_user_prompt(
            change_request,
            existing_context,
            feature_plan,
            planned_feature,
        )
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
                invalid_error="Decomposed modify feature planner returned invalid JSON.",
            )
            feature_record["raw_json"] = raw_feature
            feature, feature_warnings = _extract_decomposed_feature(raw_feature, planned_feature)
            feature_record["warnings"].extend(feature_warnings)
        except LLMPlanningError as exc:
            feature = None
            message = str(exc)
            feature_record["warnings"].append(message)
            artifacts.decomposed_modify_bad_raw_outputs.append(
                {
                    "stage": "feature_patch_json",
                    "planned": planned_feature,
                    "reason": message,
                    "raw_text": exc.artifacts.raw_text,
                    "raw_json": exc.artifacts.raw_json,
                }
            )

        if feature is None:
            fallback = _decomposed_modify_fallback_feature(planned_feature)
            if fallback is None:
                feature_record["warnings"].append("No deterministic fallback was available for this modify feature.")
                artifacts.decomposed_modify_bad_raw_outputs.append(
                    {
                        "stage": "feature_patch_json",
                        "planned": planned_feature,
                        "reason": "Could not extract feature JSON and no deterministic fallback was available.",
                        "raw_text": artifacts.raw_text,
                        "raw_json": feature_record.get("raw_json"),
                    }
                )
                artifacts.decomposed_modify_feature_patch_outputs.append(feature_record)
                continue
            feature = fallback
            feature_record["warnings"].append("Used deterministic fallback modify feature JSON.")

        feature_record["feature"] = feature
        artifacts.decomposed_modify_feature_patch_outputs.append(feature_record)
        composed_features.append(feature)

    composed_features, hardening_warnings = _harden_decomposed_composed_features(
        composed_features,
        feature_plan,
        extra_known_ids={item["id"] for item in existing_context.get("reference_map", []) if item.get("id")},
        extra_stage_ids_by_progression=_decomposed_existing_stage_ids_by_progression(existing),
    )
    artifacts.warnings.extend(hardening_warnings)
    for record, feature in zip(
        [record for record in artifacts.decomposed_modify_feature_patch_outputs if record.get("feature") is not None],
        composed_features,
    ):
        record["feature"] = feature
        record["warnings"].extend(
            warning
            for warning in hardening_warnings
            if f"'{feature.get('id')}'" in warning or f"`{feature.get('id')}`" in warning
        )

    composed_raw = {
        "mod_id": existing.mod_id,
        "mod_name": existing.display_name,
        "display_name": existing.display_name,
        "package": existing.package_name,
        "package_name": existing.package_name,
        "version": existing.version,
        "description": existing.description,
        "authors": list(existing.authors),
        "license_name": existing.license_name,
        "features": composed_features,
    }
    artifacts.decomposed_modify_composed_patch_raw_json = composed_raw
    normalization = normalize_llm_patch_output(composed_raw, existing, change_request, config)
    normalized = normalization.normalized_json
    artifacts.normalized_json = normalized
    artifacts.warnings.extend(normalization.warnings)
    artifacts.raw_json = {
        "existing_context": existing_context,
        "modify_feature_plan": feature_plan,
        "feature_patch_outputs": artifacts.decomposed_modify_feature_patch_outputs,
        "composed_patch_modspec": composed_raw,
    }
    artifacts.raw_text = json.dumps(artifacts.raw_json, ensure_ascii=False, indent=2)

    patch_spec = ModSpec.from_dict(normalized)
    merged_preview = _merge_preview(existing, patch_spec)
    artifacts.decomposed_modify_merge_preview_json = merged_preview.to_dict()
    report = validate_mod_spec(merged_preview, config)
    artifacts.schema_validation_attempts.append(_schema_validation_attempt(1, report))
    if report.is_valid:
        artifacts.warnings.extend(issue.message for issue in report.warnings)
        return patch_spec, artifacts

    errors = [issue.message for issue in report.errors]
    artifacts.warnings.extend(issue.message for issue in report.warnings)
    artifacts.error = "Invalid decomposed modification patch: " + "; ".join(errors)
    raise LLMPlanningError(artifacts.error, artifacts)


def write_planner_artifacts(project_dir: Path, config: AppConfig, artifacts: PlannerArtifacts) -> None:
    AgentEvidenceWriter(config).write_planner_artifacts(project_dir, artifacts)


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
            provider_parse_attempts = [
                {
                    "strategy": "provider_parsed_json",
                    "success": True,
                }
            ]
            parsed_json, unwrapped = _parsed_json_or_unwrapped(
                completion.parsed_json, provider_parse_attempts
            )
            artifacts.parse_attempts.extend(
                {"completion_attempt": attempt, **parse_attempt}
                for parse_attempt in provider_parse_attempts
            )
            if unwrapped:
                artifacts.json_repair_applied = True
            artifacts.raw_json = parsed_json
            return parsed_json

        parsed_json, parse_attempts, repair_applied = _parse_or_repair_llm_json(completion.raw_text)
        artifacts.parse_attempts.extend(
            {"completion_attempt": attempt, **parse_attempt} for parse_attempt in parse_attempts
        )
        if repair_applied:
            artifacts.json_repair_applied = True
        if parsed_json is not None:
            artifacts.raw_json = parsed_json
            return parsed_json

        artifacts.bad_json_outputs.append(
            {
                "completion_attempt": attempt,
                "reason": "LLM response could not be parsed as a JSON object.",
                "raw_text": completion.raw_text,
                "parse_attempts": parse_attempts,
                "completion_usage": completion.telemetry_dict(),
            }
        )
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
        parsed, unwrapped = _parsed_json_or_unwrapped(parsed, attempts)
        if unwrapped:
            repair_applied = True
        return parsed, attempts, repair_applied

    fenced = _extract_markdown_json_fence(direct)
    if fenced is not None and fenced != direct:
        repair_applied = True
        parsed = _try_parse_json_candidate("strip_markdown_fence", fenced, attempts)
        if parsed is not None:
            parsed, _ = _parsed_json_or_unwrapped(parsed, attempts)
            return parsed, attempts, repair_applied
    elif fenced is None:
        fenced = direct

    balanced = _extract_balanced_json_object(fenced)
    if balanced and balanced != fenced:
        repair_applied = True
        parsed = _try_parse_json_candidate("extract_balanced_object", balanced, attempts)
        if parsed is not None:
            parsed, _ = _parsed_json_or_unwrapped(parsed, attempts)
            return parsed, attempts, repair_applied

    unwrapped = _extract_json_from_common_wrappers(balanced or fenced, attempts)
    if unwrapped is not None:
        repair_applied = True
        return unwrapped, attempts, repair_applied

    trailing_comma_fixed = _remove_trailing_commas(balanced or fenced)
    if trailing_comma_fixed != (balanced or fenced):
        repair_applied = True
        parsed = _try_parse_json_candidate("remove_trailing_commas", trailing_comma_fixed, attempts)
        if parsed is not None:
            parsed, _ = _parsed_json_or_unwrapped(parsed, attempts)
            return parsed, attempts, repair_applied

    return None, attempts, repair_applied


def _parsed_json_or_unwrapped(
    parsed: dict[str, Any],
    attempts: list[dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    unwrapped = _unwrap_common_json_wrapper(parsed, attempts)
    if unwrapped is not None:
        return unwrapped, True
    return parsed, False


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


def _extract_markdown_json_fence(text: str) -> str | None:
    match = re.search(r"```(?:json|JSON)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _extract_json_from_common_wrappers(candidate: str, attempts: list[dict[str, Any]]) -> dict | None:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return _unwrap_common_json_wrapper(parsed, attempts)


def _unwrap_common_json_wrapper(parsed: dict[str, Any], attempts: list[dict[str, Any]]) -> dict | None:
    wrapper_keys = ("json", "data", "payload", "modspec", "mod_spec", "result", "arguments")
    for key in wrapper_keys:
        value = parsed.get(key)
        if isinstance(value, dict):
            attempts.append(
                {
                    "strategy": f"unwrap_{key}",
                    "success": True,
                    "error": None,
                    "preview": json.dumps(value, ensure_ascii=False)[:160],
                }
            )
            return value
        if isinstance(value, str):
            nested, nested_attempts, _ = _parse_or_repair_llm_json(value)
            attempts.extend({**item, "strategy": f"unwrap_{key}:{item['strategy']}"} for item in nested_attempts)
            if nested is not None:
                attempts.append(
                    {
                        "strategy": f"unwrap_{key}",
                        "success": True,
                        "error": None,
                        "preview": value[:160],
                    }
                )
                return nested
    return None


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
        "Output a single JSON object only: the first non-whitespace character must be '{' and the last non-whitespace character must be '}'.",
        "Do not output Markdown fences, explanations, XML/thinking tags, comments, or any prose before or after the JSON object.",
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
        "Recipe features are crafting recipes only; recipe_type must be shaped or shapeless.",
        "Do not emit compressor, furnace, smelting, or other machine-processing recipe types in decomposed v1.",
        "Progression stage type must be one of: ore, material, recipe, machine, equipment, item, block, entity, structure, loot_pool, dimension, biome, world_feature, milestone.",
        "Use milestone for start/end/checkpoint stages; do not use stage types named start or end.",
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
            "For recipes, recipe_type must be shaped or shapeless; reference existing/generated ids with the mod namespace.",
            "For progression, stage type must be ore, material, recipe, machine, equipment, item, block, entity, structure, loot_pool, dimension, biome, world_feature, or milestone.",
            "For progression, use milestone for start/end/checkpoint stages and reference generated feature ids through stages and links.",
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
            "recipe_type_enum": ["shaped", "shapeless"],
            "notes": [
                "Crafting only. Do not use crafting_shaped, crafting_shapeless, compressor, furnace, smelting, or machine recipe types.",
                "For shaped recipes provide pattern and keys. For shapeless recipes provide ingredients.",
            ],
        },
        "progression": {
            **base,
            "optional": ["title", "summary", "entry_stage", "end_stage", "stages", "links"],
            "stage_fields": ["id", "type", "title", "requires", "provides", "unlocks", "evidence"],
            "stage_type_enum": [
                "ore",
                "material",
                "recipe",
                "machine",
                "equipment",
                "item",
                "block",
                "entity",
                "structure",
                "loot_pool",
                "dimension",
                "biome",
                "world_feature",
                "milestone",
            ],
            "stage_notes": ["Use milestone for start/end/checkpoint stages; do not use stage types named start or end."],
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


def _build_decomposed_modify_plan_system_prompt(language: str, *, rag_context: str = "") -> str:
    lines = [
        "DECOMPOSED_MODIFY_PLAN_V2",
        "You are a NeoForge ModSpec modify decomposition planner.",
        "You must output only valid JSON.",
        "Do not output Markdown.",
        "Plan a small ModSpec patch for an existing generated workspace.",
        "Use the compact existing context; do not ask for full Java, Gradle, or resource files.",
        "Do not emit complete project specs. Emit only features that the change request adds, updates, or intentionally skips.",
        "Every feature entry must include type, id, operation, intent, depends_on, and fields.",
        "operation must be add, update, or skip.",
        "Supported feature types in v2: item, ore, machine, tool, sword, recipe, progression.",
        "If a request needs source edits beyond ModSpec, mark needs_direct_code=true and keep fields as a minimal ModSpec patch.",
        "Do not write Java code or free-form diffs.",
        f"Preferred natural language output locale: {language}.",
        "",
        "Return JSON shaped like:",
        json.dumps(
            {
                "mod_id": "existing_mod_id",
                "mod_name": "Existing Mod Name",
                "package": "existing.package",
                "version": "0.1.0",
                "description": "Small modify plan.",
                "features": [
                    {
                        "type": "ore",
                        "id": "ruby_ore",
                        "operation": "update",
                        "intent": "Add overworld ore generation.",
                        "depends_on": ["ruby"],
                        "needs_direct_code": False,
                        "fields": {"type": "ore", "id": "ruby_ore"},
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
    ]
    if rag_context:
        lines.extend(["", rag_context])
    return "\n".join(lines)


def _build_decomposed_modify_feature_system_prompt(feature_type: str, language: str) -> str:
    return "\n".join(
        [
            "DECOMPOSED_MODIFY_FEATURE_JSON_V2",
            "You fill one small NeoForge ModSpec feature patch JSON object from a decomposed modify plan entry.",
            "Output only one feature JSON object.",
            "Do not output a full ModSpec.",
            "Do not write Java, Gradle, registry code, resource files, or free-form diffs.",
            "Use only fields supported by the ModSpec schema for that feature type.",
            f"Target feature type: {feature_type}.",
            f"Preferred natural language output locale: {language}.",
        ]
    )


def _decomposed_modify_feature_user_prompt(
    change_request: str,
    existing_context: dict[str, Any],
    feature_plan: dict[str, Any],
    planned_feature: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "Change Request:",
            change_request,
            "",
            "Existing workspace compact context JSON:",
            json.dumps(existing_context, ensure_ascii=False, indent=2),
            "",
            "Modify feature plan metadata JSON:",
            json.dumps(_compact_decomposed_mod_metadata(feature_plan), ensure_ascii=False, indent=2),
            "",
            "Existing reference map JSON:",
            json.dumps(existing_context.get("reference_map", []), ensure_ascii=False, indent=2),
            "",
            "Target modify feature plan item JSON:",
            json.dumps(planned_feature, ensure_ascii=False, indent=2),
            "",
            "Field contract JSON:",
            json.dumps(_decomposed_field_contract(str(planned_feature.get("type", ""))), ensure_ascii=False, indent=2),
            "",
            "Return only the feature patch JSON for this target.",
        ]
    )


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
        raw_features.extend(feature for feature in DECOMPOSED_NORMALIZATION.expand_typed_feature_lists(candidate_source) if isinstance(feature, dict))

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

    planned_features, canonical_warnings = _canonicalize_decomposed_feature_ids(planned_features, prompt)
    warnings.extend(canonical_warnings)
    planned_features, progression_warnings = _collapse_decomposed_progression_fragments(planned_features, prompt)
    warnings.extend(progression_warnings)
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


def _compact_decomposed_modify_existing_context(existing: ModSpec, change_request: str) -> dict[str, Any]:
    lowered = change_request.lower()
    features = [_decomposed_modify_feature_summary(feature) for feature in existing.iter_features()]
    reference_map = [
        {
            "id": item["id"],
            "type": item["type"],
            "resource_id": _decomposed_resource_id(existing.mod_id, item["id"]),
        }
        for item in features
        if item.get("id")
    ]
    relevant_features = [
        feature
        for feature in features
        if _decomposed_modify_feature_is_relevant(feature, lowered)
    ]
    if not relevant_features:
        relevant_features = features[:12]
    return {
        "mod_id": existing.mod_id,
        "mod_name": existing.display_name,
        "package": existing.package_name,
        "version": existing.version,
        "feature_count": len(features),
        "features": features,
        "relevant_features": relevant_features[:16],
        "reference_map": reference_map,
    }


def _decomposed_existing_stage_ids_by_progression(existing: ModSpec) -> dict[str, set[str]]:
    return {
        progression.identifier: {stage.identifier for stage in progression.stages}
        for progression in existing.progressions
    }


def _decomposed_modify_feature_summary(feature: Any) -> dict[str, Any]:
    data = feature.to_dict() if hasattr(feature, "to_dict") else {}
    feature_type = str(data.get("type", feature.__class__.__name__.replace("Spec", "").lower()))
    identifier = str(data.get("id", data.get("identifier", getattr(feature, "identifier", ""))))
    summary: dict[str, Any] = {
        "type": feature_type,
        "id": identifier,
        "display_name_en_us": data.get("display_name_en_us") or data.get("display_name") or identifier.replace("_", " ").title(),
    }
    for key in (
        "drop",
        "worldgen",
        "behavior",
        "tool_material",
        "tier",
        "result",
        "ingredients",
        "keys",
        "machine_kind",
        "stages",
        "references",
    ):
        value = data.get(key)
        if value not in (None, "", [], {}):
            summary[key] = value
    return summary


def _decomposed_modify_feature_is_relevant(feature: dict[str, Any], lowered_prompt: str) -> bool:
    identifier = str(feature.get("id", "")).lower()
    feature_type = str(feature.get("type", "")).lower()
    tokens = {identifier, feature_type}
    tokens.update(part for part in identifier.split("_") if part)
    if feature_type == "ore" and any(token in lowered_prompt for token in ("ore", "worldgen", "overworld", "underground")):
        return True
    if feature_type in {"item", "tool", "sword"} and any(token in lowered_prompt for token in ("item", "tool", "sword", "charm")):
        return True
    if feature_type == "machine" and any(token in lowered_prompt for token in ("machine", "compressor")):
        return True
    return any(token and token in lowered_prompt for token in tokens)


def _normalize_decomposed_modify_feature_plan(
    raw: dict,
    existing: ModSpec,
    change_request: str,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    features: list[dict[str, Any]] = []
    for raw_feature in raw.get("features", []) if isinstance(raw.get("features"), list) else []:
        if not isinstance(raw_feature, dict):
            warnings.append("Ignored non-object decomposed modify feature plan entry.")
            continue
        feature = _planned_decomposed_modify_feature_from_raw(raw_feature, warnings)
        if feature is not None:
            features.append(feature)
    features = _dedupe_decomposed_modify_features(features, warnings)
    if not features:
        fallback_features = _fallback_decomposed_modify_plan_features(existing, change_request)
        if fallback_features:
            warnings.append("Decomposed modify plan had no supported entries; deterministic fallback plan was used.")
            features = fallback_features
    feature_plan = {
        "mod_id": existing.mod_id,
        "mod_name": existing.display_name,
        "package": existing.package_name,
        "version": existing.version,
        "description": str(raw.get("description", f"Modify plan for: {change_request}")),
        "features": features,
    }
    return feature_plan, warnings


def _planned_decomposed_modify_feature_from_raw(raw_feature: dict[str, Any], warnings: list[str]) -> dict[str, Any] | None:
    feature_type = str(raw_feature.get("type", "")).strip().lower()
    if feature_type not in {"item", "ore", "machine", "tool", "sword", "recipe", "progression"}:
        warnings.append(f"Unsupported decomposed modify feature type ignored: {feature_type or '(missing)'}")
        return None
    identifier = slugify_mod_id(str(raw_feature.get("id", raw_feature.get("identifier", ""))), fallback="")
    if not identifier:
        warnings.append(f"Decomposed modify feature entry missing id for type {feature_type}.")
        return None
    operation = str(raw_feature.get("operation", "add")).strip().lower()
    if operation not in {"add", "update", "skip"}:
        warnings.append(f"Unsupported decomposed modify operation '{operation}' for {identifier}; using add.")
        operation = "add"
    fields = raw_feature.get("fields") if isinstance(raw_feature.get("fields"), dict) else {}
    fields = dict(fields)
    fields["type"] = feature_type
    fields["id"] = identifier
    return {
        "type": feature_type,
        "id": identifier,
        "operation": operation,
        "intent": str(raw_feature.get("intent", f"{operation} {identifier}")),
        "depends_on": [str(item) for item in raw_feature.get("depends_on", []) if str(item).strip()] if isinstance(raw_feature.get("depends_on"), list) else [],
        "needs_direct_code": bool(raw_feature.get("needs_direct_code", False)),
        "fields": fields,
    }


def _dedupe_decomposed_modify_features(features: list[dict[str, Any]], warnings: list[str]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for feature in features:
        key = (str(feature.get("type", "")), str(feature.get("id", "")))
        if key in by_key:
            warnings.append(f"Duplicate decomposed modify feature plan entry collapsed: {key[0]}:{key[1]}")
        by_key[key] = feature
    return list(by_key.values())


def _fallback_decomposed_modify_plan_features(existing: ModSpec, change_request: str) -> list[dict[str, Any]]:
    lowered = change_request.lower()
    if any(token in lowered for token in ("ore", "worldgen", "overworld", "underground")):
        ore_id = next((ore.identifier for ore in existing.ores if "ore" in ore.identifier), "ruby_ore")
        material_id = ore_id.removesuffix("_ore") or "ruby"
        return [
            {
                "type": "ore",
                "id": ore_id,
                "operation": "update",
                "intent": "Add or update ore worldgen from modify request.",
                "depends_on": [material_id],
                "needs_direct_code": False,
                "fields": {
                    "type": "ore",
                    "id": ore_id,
                    "display_name_en_us": ore_id.replace("_", " ").title(),
                    "drop": _decomposed_resource_id(existing.mod_id, material_id),
                    "worldgen": {
                        "enabled": True,
                        "dimension": "minecraft:overworld",
                        "min_y": -64,
                        "max_y": 32,
                        "vein_size": 6,
                        "veins_per_chunk": 4,
                    },
                },
            }
        ]
    return []


def _decomposed_modify_fallback_feature(planned_feature: dict[str, Any]) -> dict[str, Any] | None:
    fields = planned_feature.get("fields") if isinstance(planned_feature.get("fields"), dict) else {}
    if not fields:
        return None
    fields = dict(fields)
    fields["type"] = str(planned_feature.get("type", fields.get("type", "")))
    fields["id"] = str(planned_feature.get("id", fields.get("id", "")))
    return fields


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


def _canonicalize_decomposed_feature_ids(
    features: list[dict[str, Any]],
    prompt: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    material = _decomposed_material_prefix(features, prompt)
    if not material:
        return features, warnings

    id_map: dict[str, str] = {}
    for feature in features:
        feature_type = str(feature.get("type", ""))
        identifier = str(feature.get("id", ""))
        if not identifier:
            continue
        canonical = identifier
        if feature_type == "machine" and identifier in DECOMPOSED_NORMALIZATION.supported_machine_kinds and not identifier.startswith(f"{material}_"):
            canonical = f"{material}_{identifier}"
        elif feature_type == "progression":
            if identifier in {"progression", "progression_loop", "gameplay_loop", f"{material}_progression_loop"}:
                canonical = f"{material}_progression"
        if canonical != identifier:
            id_map[identifier] = canonical
            warnings.append(f"Decomposed feature id '{identifier}' normalized to '{canonical}' for stable benchmark evidence.")

    if not id_map:
        return features, warnings

    canonicalized: list[dict[str, Any]] = []
    for feature in features:
        updated = _rewrite_decomposed_references(feature, id_map)
        if isinstance(updated, dict):
            canonicalized.append(updated)
    return canonicalized, warnings


def _collapse_decomposed_progression_fragments(
    features: list[dict[str, Any]],
    prompt: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    progression_features = [feature for feature in features if feature.get("type") == "progression"]
    if len(progression_features) <= 1:
        return features, []

    material = _decomposed_material_prefix(features, prompt) or "generated"
    progression_id = f"{material}_progression"
    stage_features: list[dict[str, Any]] = []
    for feature in progression_features:
        fields = feature.get("fields") if isinstance(feature.get("fields"), dict) else {}
        raw_stage_type = str(fields.get("stage_type", fields.get("type", feature.get("stage_type", "milestone")))).lower()
        stage_type = DECOMPOSED_STAGE_TYPE_ALIASES.get(raw_stage_type, raw_stage_type)
        if stage_type not in SUPPORTED_PROGRESSION_STAGE_TYPES:
            stage_type = "milestone"
        stage_id = slugify_mod_id(str(feature.get("id", feature.get("display_name_en_us", "stage"))), fallback="stage")
        depends_on = feature.get("depends_on") if isinstance(feature.get("depends_on"), list) else []
        stage_features.append(
            {
                "id": stage_id,
                "type": stage_type,
                "title": str(feature.get("display_name_en_us") or derive_display_name(stage_id)),
                "description": str(fields.get("description", feature.get("intent", ""))),
                "requires": [str(item) for item in depends_on],
                "provides": [str(item) for item in depends_on],
                "unlocks": [],
                "evidence": [str(item) for item in depends_on],
            }
        )

    links = [
        {
            "from": str(stage_features[index]["id"]),
            "to": str(stage_features[index + 1]["id"]),
            "trigger": "progression_step",
            "requirement": str(stage_features[index + 1]["title"]),
        }
        for index in range(len(stage_features) - 1)
    ]
    dependencies: list[str] = []
    seen_dependencies: set[str] = set()
    for feature in progression_features:
        depends_on = feature.get("depends_on") if isinstance(feature.get("depends_on"), list) else []
        for dependency in depends_on:
            dependency_id = slugify_mod_id(str(dependency), fallback="")
            if dependency_id and dependency_id not in seen_dependencies:
                seen_dependencies.add(dependency_id)
                dependencies.append(dependency_id)

    collapsed = {
        "type": "progression",
        "id": progression_id,
        "display_name_en_us": derive_display_name(progression_id),
        "intent": "Collapsed decomposed progression fragments into one auditable progression loop.",
        "depends_on": dependencies,
        "fields": {
            "type": "progression",
            "id": progression_id,
            "title": derive_display_name(progression_id),
            "summary": "Auditable progression loop assembled from decomposed progression fragments.",
            "entry_stage": str(stage_features[0]["id"]) if stage_features else "start",
            "end_stage": str(stage_features[-1]["id"]) if stage_features else "start",
            "stages": stage_features,
            "links": links,
        },
    }

    non_progression = [feature for feature in features if feature.get("type") != "progression"]
    warning = (
        f"Collapsed {len(progression_features)} decomposed progression fragments into '{progression_id}' "
        "for stable ModSpec evidence."
    )
    return [*non_progression, collapsed], [warning]


def _decomposed_material_prefix(features: list[dict[str, Any]], prompt: str) -> str:
    prompt_slug = slugify_mod_id(prompt, fallback="")
    for feature in features:
        feature_id = str(feature.get("id", ""))
        if feature.get("type") == "item" and feature_id:
            if feature_id in {"ruby", "sapphire", "copper", "amber"}:
                return feature_id
            if feature_id.endswith("_gem"):
                return feature_id.removesuffix("_gem")
    for feature in features:
        feature_id = str(feature.get("id", ""))
        for suffix in ("_ore", "_pickaxe", "_axe", "_shovel", "_hoe", "_sword"):
            if feature_id.endswith(suffix):
                return feature_id.removesuffix(suffix)
    if "ruby" in prompt_slug:
        return "ruby"
    return ""


def _rewrite_decomposed_references(value: Any, id_map: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite_decomposed_references(item, id_map) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_decomposed_references(item, id_map) for item in value]
    if isinstance(value, str):
        return _rewrite_decomposed_reference_string(value, id_map)
    return value


def _rewrite_decomposed_reference_string(value: str, id_map: dict[str, str]) -> str:
    if value in id_map:
        return id_map[value]
    if ":" in value:
        namespace, local_id = value.split(":", 1)
        if local_id in id_map:
            return f"{namespace}:{id_map[local_id]}"
    return value


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
    candidates.extend(item for item in DECOMPOSED_NORMALIZATION.expand_typed_feature_lists(raw) if isinstance(item, dict))
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
        tool_type = next((value for value in DECOMPOSED_NORMALIZATION.supported_tool_types if identifier.endswith(f"_{value}")), "pickaxe")
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


def _harden_decomposed_composed_features(
    features: list[dict[str, Any]],
    feature_plan: dict[str, Any],
    *,
    extra_known_ids: set[str] | None = None,
    extra_stage_ids_by_progression: dict[str, set[str]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    mod_id = str(feature_plan.get("mod_id", ""))
    known_ids = {str(feature.get("id")) for feature in features if feature.get("id")}
    known_ids.update(extra_known_ids or set())
    result_ids = {
        str(feature.get("id"))
        for feature in features
        if feature.get("id") and str(feature.get("type")) not in {"recipe", "progression"}
    }
    result_ids.update(extra_known_ids or set())
    hardened = [dict(feature) for feature in features]
    extra_stage_ids_by_progression = extra_stage_ids_by_progression or {}
    planned_recipes = {
        str(feature.get("id")): feature
        for feature in feature_plan.get("features", [])
        if isinstance(feature, dict) and feature.get("type") == "recipe" and feature.get("id")
    }

    dependency_checked: list[dict[str, Any]] = []
    for feature in hardened:
        if feature.get("type") == "recipe":
            planned = planned_recipes.get(str(feature.get("id", "")), {})
            missing = _missing_decomposed_recipe_dependencies(planned, mod_id, result_ids)
            if missing:
                warnings.append(
                    f"Decomposed recipe '{feature.get('id', 'generated_recipe')}' was removed because its "
                    f"missing internal dependency could not be generated: {', '.join(missing)}."
                )
                continue
        dependency_checked.append(feature)
    hardened = dependency_checked

    used_recipe_ids: set[str] = set()
    for feature in hardened:
        feature_type = str(feature.get("type", ""))
        identifier = str(feature.get("id", ""))
        source_recipe_id = identifier
        _harden_decomposed_behavior(feature, warnings)
        if feature_type == "ore":
            _harden_decomposed_ore_feature(feature, feature_plan, mod_id, known_ids, warnings)
        elif feature_type == "recipe":
            _harden_decomposed_recipe_feature(feature, feature_plan, mod_id, known_ids, result_ids, warnings)
            canonical_recipe_id = str(feature.get("id", ""))
            if canonical_recipe_id in used_recipe_ids:
                fallback_id = source_recipe_id
                suffix = 2
                while fallback_id in used_recipe_ids:
                    fallback_id = f"{source_recipe_id}_{suffix}"
                    suffix += 1
                feature["id"] = fallback_id
                warnings.append(
                    f"Decomposed recipe id collision on '{canonical_recipe_id}'; kept unique id '{fallback_id}'."
                )
                canonical_recipe_id = fallback_id
            used_recipe_ids.add(canonical_recipe_id)
        elif feature_type == "progression":
            _harden_decomposed_progression_feature(
                feature,
                known_ids,
                warnings,
                extra_stage_ids=extra_stage_ids_by_progression.get(identifier, set()),
            )

    return hardened, warnings


def _missing_decomposed_recipe_dependencies(
    planned_recipe: dict[str, Any],
    mod_id: str,
    result_ids: set[str],
) -> list[str]:
    dependencies = planned_recipe.get("depends_on", [])
    if not isinstance(dependencies, list):
        return []

    missing: list[str] = []
    for dependency in dependencies:
        reference = str(dependency).strip()
        if not reference:
            continue
        if ":" in reference:
            namespace, _ = reference.split(":", 1)
            if namespace and namespace != mod_id:
                continue
        local_id = _local_reference_id(reference)
        if local_id in result_ids or local_id in VANILLA_RECIPE_REFERENCE_IDS:
            continue
        missing.append(local_id or reference)
    return missing


def _harden_decomposed_behavior(feature: dict[str, Any], warnings: list[str]) -> None:
    behavior = DECOMPOSED_NORMALIZATION.feature_behavior_from_aliases(feature)
    if not isinstance(behavior, dict):
        return

    identifier = str(feature.get("id", "feature"))
    raw_behavior_type = str(behavior.get("type", "")).strip().lower()
    if not raw_behavior_type:
        feature.pop("behavior", None)
        warnings.append(f"Decomposed feature '{identifier}' had empty behavior type; removed behavior.")
        return
    behavior_type = DECOMPOSED_NORMALIZATION.normalize_behavior_type_alias(raw_behavior_type)
    if behavior_type != raw_behavior_type:
        warnings.append(f"Decomposed feature '{identifier}' behavior type '{raw_behavior_type}' normalized to '{behavior_type}'.")
    if behavior_type not in SUPPORTED_ITEM_BEHAVIORS:
        feature.pop("behavior", None)
        warnings.append(f"Decomposed feature '{identifier}' used unsupported behavior type '{raw_behavior_type}'; removed behavior.")
        return
    behavior["type"] = behavior_type
    feature["behavior"] = behavior


def _harden_decomposed_ore_feature(
    feature: dict[str, Any],
    feature_plan: dict[str, Any],
    mod_id: str,
    known_ids: set[str],
    warnings: list[str],
) -> None:
    identifier = str(feature.get("id", "ore"))
    drop = feature.get("drop")
    local_drop = _local_reference_id(str(drop)) if not DECOMPOSED_NORMALIZATION.is_blank_value(drop) else ""
    if local_drop and local_drop in known_ids:
        feature["drop"] = _decomposed_resource_id(mod_id, local_drop)
    else:
        material_id = _decomposed_material_id_for_ore(identifier, feature_plan, known_ids)
        feature["drop"] = _decomposed_resource_id(mod_id, material_id)
        warnings.append(f"Decomposed ore '{identifier}' used unsupported or missing drop; normalized to '{feature['drop']}'.")

    worldgen = feature.get("worldgen")
    if isinstance(worldgen, dict):
        raw_dimension = str(worldgen.get("dimension", "")).strip().lower()
        if raw_dimension == "overworld":
            worldgen["dimension"] = "minecraft:overworld"
            warnings.append(f"Decomposed ore '{identifier}' worldgen dimension 'overworld' normalized to 'minecraft:overworld'.")


def _harden_decomposed_recipe_feature(
    feature: dict[str, Any],
    feature_plan: dict[str, Any],
    mod_id: str,
    known_ids: set[str],
    result_ids: set[str],
    warnings: list[str],
) -> None:
    identifier = str(feature.get("id", "generated_recipe"))
    raw_recipe_type = str(feature.get("recipe_type", "shaped")).strip().lower()
    recipe_type = DECOMPOSED_RECIPE_TYPE_ALIASES.get(raw_recipe_type, raw_recipe_type)
    if not isinstance(feature.get("keys"), dict) and isinstance(feature.get("key"), dict):
        feature["keys"] = dict(feature["key"])
        warnings.append(f"Decomposed recipe '{identifier}' used 'key'; normalized to 'keys'.")
    if recipe_type not in SUPPORTED_RECIPE_TYPES:
        warnings.append(f"Decomposed recipe '{identifier}' used unsupported recipe_type '{raw_recipe_type}'; normalized to 'shapeless'.")
        recipe_type = "shapeless"

    if recipe_type == "shaped":
        pattern = feature.get("pattern")
        keys = feature.get("keys")
        if not isinstance(pattern, list) or not pattern or not isinstance(keys, dict) or not keys:
            warnings.append(f"Decomposed recipe '{identifier}' lacked shaped pattern/keys; normalized to 'shapeless'.")
            recipe_type = "shapeless"
        else:
            normalized_keys = {
                str(key): str(DECOMPOSED_NORMALIZATION.recipe_result_reference(value))
                for key, value in keys.items()
            }
            if normalized_keys != keys:
                feature["keys"] = normalized_keys
                warnings.append(f"Decomposed recipe '{identifier}' key item objects normalized to resource ids.")

    if raw_recipe_type != recipe_type and raw_recipe_type in DECOMPOSED_RECIPE_TYPE_ALIASES:
        warnings.append(f"Decomposed recipe '{identifier}' recipe_type '{raw_recipe_type}' normalized to '{recipe_type}'.")
    feature["recipe_type"] = recipe_type

    raw_result = feature.get("result")
    if isinstance(raw_result, dict) and "count" in raw_result and feature.get("count") is None:
        feature["count"] = raw_result["count"]
    result = DECOMPOSED_NORMALIZATION.recipe_result_reference(raw_result)
    result_id = _local_reference_id(str(result)) if not DECOMPOSED_NORMALIZATION.is_blank_value(result) else ""
    if not result_id or result_id not in result_ids:
        inferred_result = _infer_decomposed_recipe_result_id(identifier, feature, feature_plan, result_ids)
        feature["result"] = _decomposed_resource_id(mod_id, inferred_result)
        result_id = inferred_result
        warnings.append(f"Decomposed recipe '{identifier}' used missing or unknown result; normalized to '{feature['result']}'.")
    else:
        feature["result"] = _decomposed_resource_id(mod_id, result_id)

    canonical_id = _canonical_decomposed_recipe_id(identifier, result_id, result_ids)
    if canonical_id != identifier:
        feature["id"] = canonical_id
        warnings.append(f"Decomposed recipe '{identifier}' id normalized to '{canonical_id}'.")
        identifier = canonical_id

    if recipe_type == "shapeless":
        ingredients = feature.get("ingredients")
        if not isinstance(ingredients, list) or not ingredients:
            ingredients = _infer_decomposed_recipe_ingredients(feature, feature_plan, mod_id, known_ids)
            feature["ingredients"] = ingredients
            warnings.append(f"Decomposed recipe '{identifier}' lacked shapeless ingredients; inferred deterministic ingredients.")
        else:
            normalized_ingredients = [str(DECOMPOSED_NORMALIZATION.recipe_result_reference(item)) for item in ingredients]
            if normalized_ingredients != ingredients:
                feature["ingredients"] = normalized_ingredients
                warnings.append(f"Decomposed recipe '{identifier}' ingredient objects normalized to resource ids.")
        feature.pop("pattern", None)
        feature.pop("keys", None)


def _canonical_decomposed_recipe_id(identifier: str, result_id: str, result_ids: set[str]) -> str:
    if result_id not in result_ids:
        return identifier
    for suffix in ("_crafting", "_craft", "_recipe"):
        if identifier.endswith(suffix):
            return result_id
    return identifier


def _harden_decomposed_progression_feature(
    feature: dict[str, Any],
    known_ids: set[str],
    warnings: list[str],
    *,
    extra_stage_ids: set[str] | None = None,
) -> None:
    identifier = str(feature.get("id", "progression"))
    extra_stage_ids = extra_stage_ids or set()
    raw_stages = feature.get("stages") if isinstance(feature.get("stages"), list) else []
    stages: list[dict[str, Any]] = []
    stage_ids: set[str] = set()
    for raw_stage in raw_stages:
        if not isinstance(raw_stage, dict):
            continue
        stage = dict(raw_stage)
        stage_id = slugify_mod_id(str(stage.get("id", stage.get("identifier", stage.get("title", "stage")))), fallback="stage")
        raw_stage_type = str(stage.get("stage_type", stage.get("type", "milestone"))).strip().lower()
        stage_type = DECOMPOSED_STAGE_TYPE_ALIASES.get(raw_stage_type, raw_stage_type)
        if stage_type not in SUPPORTED_PROGRESSION_STAGE_TYPES:
            warnings.append(f"Decomposed progression '{identifier}' stage '{stage_id}' used unsupported type '{raw_stage_type}'; normalized to 'milestone'.")
            stage_type = "milestone"
        elif stage_type != raw_stage_type:
            warnings.append(f"Decomposed progression '{identifier}' stage '{stage_id}' type '{raw_stage_type}' normalized to '{stage_type}'.")

        stage["id"] = stage_id
        stage["type"] = stage_type
        stage["title"] = str(stage.get("title") or derive_display_name(stage_id))
        for key in ("requires", "provides", "unlocks", "evidence"):
            values = _decomposed_reference_list(stage.get(key))
            stage[key] = [value for value in values if _decomposed_ref_known(value, known_ids)]
        stage_ids.add(stage_id)
        stages.append(stage)

    if not stages:
        fallback_stage = {
            "id": "start",
            "type": "milestone",
            "title": "Start",
            "evidence": [],
        }
        stages = [fallback_stage]
        stage_ids = {"start"}
        warnings.append(f"Decomposed progression '{identifier}' had no usable stages; inserted a milestone stage.")

    valid_stage_ids = stage_ids | extra_stage_ids
    feature["stages"] = stages
    entry_stage = str(feature.get("entry_stage", ""))
    end_stage = str(feature.get("end_stage", ""))
    feature["entry_stage"] = entry_stage if entry_stage in valid_stage_ids else str(stages[0]["id"])
    feature["end_stage"] = end_stage if end_stage in valid_stage_ids else str(stages[-1]["id"])

    links: list[dict[str, Any]] = []
    raw_links = feature.get("links") if isinstance(feature.get("links"), list) else []
    for raw_link in raw_links:
        if not isinstance(raw_link, dict):
            continue
        from_stage = str(raw_link.get("from", raw_link.get("from_stage", "")))
        to_stage = str(raw_link.get("to", raw_link.get("to_stage", "")))
        if from_stage in valid_stage_ids and to_stage in valid_stage_ids:
            links.append(
                {
                    "from": from_stage,
                    "to": to_stage,
                    "trigger": str(raw_link.get("trigger", "")),
                    "requirement": str(raw_link.get("requirement", "")),
                }
            )
    feature["links"] = links


def _local_reference_id(reference: str) -> str:
    value = reference.split(":", 1)[1] if ":" in reference else reference
    return slugify_mod_id(value, fallback="")


def _decomposed_material_id_for_ore(identifier: str, feature_plan: dict[str, Any], known_ids: set[str]) -> str:
    preferred = identifier.removesuffix("_ore") or identifier
    if preferred in known_ids:
        return preferred
    for feature in feature_plan.get("features", []):
        if not isinstance(feature, dict) or feature.get("type") != "item":
            continue
        item_id = str(feature.get("id", ""))
        if item_id in known_ids and (item_id == preferred or preferred in item_id or item_id in preferred):
            return item_id
    return _first_decomposed_item_id(feature_plan) or preferred


def _infer_decomposed_recipe_result_id(
    identifier: str,
    feature: dict[str, Any],
    feature_plan: dict[str, Any],
    result_ids: set[str],
) -> str:
    for suffix in ("_crafting", "_craft", "_recipe"):
        candidate = identifier.removesuffix(suffix)
        if candidate != identifier and candidate in result_ids:
            return candidate
        if candidate != identifier:
            suffixed_candidate = next((item for item in sorted(result_ids) if item.endswith(f"_{candidate}")), "")
            if suffixed_candidate:
                return suffixed_candidate
    if identifier in result_ids:
        return identifier
    item_id = _first_decomposed_item_id(feature_plan)
    if item_id:
        return item_id
    depends_on = feature.get("depends_on", [])
    if not isinstance(depends_on, list):
        depends_on = []
    for dependency in depends_on:
        dependency_id = slugify_mod_id(str(dependency), fallback="")
        if dependency_id in result_ids:
            return dependency_id
    return next(iter(sorted(result_ids)), identifier)


def _infer_decomposed_recipe_ingredients(
    feature: dict[str, Any],
    feature_plan: dict[str, Any],
    mod_id: str,
    known_ids: set[str],
) -> list[str]:
    ingredients: list[str] = []
    depends_on = feature.get("depends_on", [])
    if isinstance(depends_on, list):
        for dependency in depends_on:
            dependency_id = slugify_mod_id(str(dependency), fallback="")
            if dependency_id in known_ids:
                ingredients.append(_decomposed_resource_id(mod_id, dependency_id))
    if ingredients:
        return ingredients
    item_id = _first_decomposed_item_id(feature_plan)
    return [_decomposed_resource_id(mod_id, item_id)] if item_id else []


def _decomposed_reference_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if not DECOMPOSED_NORMALIZATION.is_blank_value(item)]
    if DECOMPOSED_NORMALIZATION.is_blank_value(value):
        return []
    return [str(value)]


def _first_decomposed_item_id(feature_plan: dict[str, Any]) -> str | None:
    for feature in feature_plan.get("features", []):
        if isinstance(feature, dict) and feature.get("type") == "item":
            return str(feature.get("id"))
    return None


def _merge_preview(existing: ModSpec, patch: ModSpec) -> ModSpec:
    merged = ModSpec.from_dict(existing.to_dict())
    for definition in iter_feature_kind_definitions():
        if definition.merge_policy == FeatureMergePolicy.REPLACE_RECIPE_BY_IDENTIFIER:
            continue
        existing_list = getattr(merged, definition.collection_name)
        patch_list = getattr(patch, definition.collection_name)
        for feature in patch_list:
            current = next((item for item in existing_list if item.identifier == feature.identifier), None)
            if current is None:
                existing_list.append(feature)
            elif definition.merge_policy == FeatureMergePolicy.MERGE_PROGRESSION and isinstance(current, ProgressionSpec) and isinstance(feature, ProgressionSpec):
                existing_list[existing_list.index(current)] = _merge_progression_patch(current, feature)
            else:
                existing_list[existing_list.index(current)] = feature

    recipe_map = {recipe.identifier: recipe for recipe in merged.recipes}
    for recipe in patch.recipes:
        recipe_map[recipe.identifier] = recipe
    merged.recipes = list(recipe_map.values())
    return merged


def _merge_progression_patch(existing: ProgressionSpec, patch: ProgressionSpec) -> ProgressionSpec:
    stage_map = {stage.identifier: stage for stage in existing.stages}
    stage_order = [stage.identifier for stage in existing.stages]
    for stage in patch.stages:
        if stage.identifier not in stage_map:
            stage_order.append(stage.identifier)
        stage_map[stage.identifier] = stage
    stages = [stage_map[identifier] for identifier in stage_order]
    stage_ids = set(stage_order)

    link_map = {(link.from_stage, link.to_stage): link for link in existing.links}
    link_order = [(link.from_stage, link.to_stage) for link in existing.links]
    for link in patch.links:
        if link.from_stage not in stage_ids or link.to_stage not in stage_ids:
            continue
        key = (link.from_stage, link.to_stage)
        if key not in link_map:
            link_order.append(key)
        link_map[key] = link
    links = [link_map[key] for key in link_order]

    entry_stage = existing.entry_stage
    if patch.entry_stage in stage_ids and len(patch.stages) > 1:
        entry_stage = patch.entry_stage
    end_stage = existing.end_stage
    if patch.end_stage in stage_ids:
        end_stage = patch.end_stage
    links = _ensure_progression_end_reachable(existing.entry_stage, existing.end_stage, end_stage, links, stage_ids)

    return ProgressionSpec(
        identifier=existing.identifier,
        title=patch.title or existing.title,
        summary=patch.summary or existing.summary,
        entry_stage=entry_stage,
        end_stage=end_stage,
        stages=stages,
        links=links,
        behavior=patch.behavior or existing.behavior,
    )


def _ensure_progression_end_reachable(
    entry_stage: str,
    previous_end_stage: str,
    end_stage: str,
    links: list[ProgressionLinkSpec],
    stage_ids: set[str],
) -> list[ProgressionLinkSpec]:
    if not entry_stage or not end_stage or end_stage in _reachable_stage_ids(entry_stage, links):
        return links
    if previous_end_stage not in stage_ids or previous_end_stage == end_stage:
        return links
    inferred = ProgressionLinkSpec(
        from_stage=previous_end_stage,
        to_stage=end_stage,
        trigger="progression_update",
        requirement="Inferred final milestone transition.",
    )
    return [*links, inferred]


def _reachable_stage_ids(entry_stage: str, links: list[ProgressionLinkSpec]) -> set[str]:
    reachable = {entry_stage}
    changed = True
    while changed:
        changed = False
        for link in links:
            if link.from_stage in reachable and link.to_stage not in reachable:
                reachable.add(link.to_stage)
                changed = True
    return reachable
