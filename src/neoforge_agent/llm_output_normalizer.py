from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .config import AppConfig
from .feature_catalog import iter_feature_kind_definitions
from .java_extension_generator import SUPPORTED_JAVA_EXTENSION_IMPORTS
from .models import ModSpec
from .tools import derive_display_name, derive_package_name, slugify_mod_id


@dataclass(frozen=True, slots=True)
class LLMNormalizationResult:
    normalized_json: dict[str, Any]
    warnings: list[str]


@dataclass(frozen=True, slots=True)
class DecomposedPlannerNormalization:
    @property
    def supported_machine_kinds(self) -> frozenset[str]:
        return frozenset(SUPPORTED_MACHINE_KINDS)

    @property
    def supported_tool_types(self) -> frozenset[str]:
        return frozenset(SUPPORTED_TOOL_TYPES)

    def expand_typed_feature_lists(self, raw: dict) -> list[dict]:
        return _expand_typed_feature_lists(raw)

    def feature_behavior_from_aliases(self, feature: dict) -> dict | None:
        return _feature_behavior_from_aliases(feature)

    def normalize_behavior_type_alias(self, value: str) -> str:
        return _normalize_behavior_type_alias(value)

    def recipe_result_reference(self, value: object) -> object:
        return _decomposed_recipe_result_reference(value)

    def is_blank_value(self, value: object) -> bool:
        return _blank_decomposed_value(value)


SUPPORTED_FEATURE_TYPES = {definition.kind for definition in iter_feature_kind_definitions()}
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
DECOMPOSED_PLANNER_NORMALIZATION = DecomposedPlannerNormalization()


def normalize_llm_modspec_output(raw: dict, prompt: str, config: AppConfig) -> LLMNormalizationResult:
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
    return LLMNormalizationResult(normalized_json=normalized, warnings=warnings)


def normalize_llm_patch_output(raw: dict, existing: ModSpec, prompt: str, config: AppConfig) -> LLMNormalizationResult:
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
    return LLMNormalizationResult(normalized_json=normalized, warnings=warnings)


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
        behavior = _feature_behavior_from_aliases(feature)
        if isinstance(behavior, dict):
            normalized["behavior"] = _normalize_behavior(behavior)
    return normalized


def _feature_behavior_from_aliases(feature: dict) -> dict | None:
    behavior = feature.get("behavior")
    if isinstance(behavior, dict):
        return dict(behavior)

    right_click_behavior = feature.get("right_click_behavior")
    if isinstance(right_click_behavior, dict):
        return dict(right_click_behavior)

    normalized: dict[str, Any] = {}
    if isinstance(behavior, str) and behavior.strip():
        normalized["type"] = behavior.strip()
    elif isinstance(right_click_behavior, str) and right_click_behavior.strip():
        normalized["type"] = right_click_behavior.strip()
    elif isinstance(feature.get("behavior_type"), str) and feature["behavior_type"].strip():
        normalized["type"] = feature["behavior_type"].strip()

    for key in (
        "amount",
        "heal_amount",
        "effect",
        "duration_ticks",
        "duration_seconds",
        "amplifier",
        "cooldown_ticks",
        "cooldown_seconds",
        "consume",
        "events",
    ):
        if feature.get(key) is not None:
            normalized[key] = feature[key]
    if feature.get("heal") is not None and normalized.get("amount") is None:
        normalized["amount"] = feature["heal"]
    if feature.get("apply_effect") is not None and normalized.get("effect") is None:
        normalized["effect"] = feature["apply_effect"]

    if not normalized.get("type"):
        if any(key in normalized for key in ("amount", "heal_amount")):
            normalized["type"] = "right_click_heal"
        elif normalized.get("effect") is not None:
            normalized["type"] = "right_click_effect"

    return normalized or None


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
    behavior = _normalize_right_click_behavior_alias(behavior)
    events = [
        _normalize_behavior_event(event)
        for event in behavior.get("events", [])
        if isinstance(event, dict)
    ]
    behavior_type = _normalize_behavior_type_alias(str(behavior.get("type", "event_action" if events else "")).strip().lower())
    amount = behavior.get("amount", behavior.get("heal_amount"))
    duration_ticks = behavior.get("duration_ticks")
    if duration_ticks is None and behavior.get("duration_seconds") is not None:
        duration_ticks = _seconds_to_ticks(behavior.get("duration_seconds"))
    cooldown_ticks = behavior.get("cooldown_ticks")
    if cooldown_ticks is None and behavior.get("cooldown_seconds") is not None:
        cooldown_ticks = _seconds_to_ticks(behavior.get("cooldown_seconds"))
    normalized = {
        "type": behavior_type,
        "amount": float(amount) if amount is not None else None,
        "effect": str(behavior["effect"]) if behavior.get("effect") is not None else None,
        "duration_ticks": int(duration_ticks) if duration_ticks is not None else None,
        "amplifier": int(behavior.get("amplifier", 0)),
        "cooldown_ticks": int(cooldown_ticks) if cooldown_ticks is not None else 0,
        "consume": bool(behavior.get("consume", False)),
    }
    if events:
        normalized["events"] = events
    return normalized


def _normalize_right_click_behavior_alias(behavior: dict) -> dict:
    right_click = behavior.get("right_click")
    if not isinstance(right_click, dict):
        return behavior
    normalized = {key: value for key, value in behavior.items() if key != "right_click"}
    applied_effect = right_click.get("apply_effect")
    if isinstance(applied_effect, dict):
        applied_effect_fields = applied_effect
        applied_effect_value = _first_alias_value(applied_effect_fields, "effect", "id", "name")
    else:
        applied_effect_fields = {}
        applied_effect_value = applied_effect
    if not normalized.get("type"):
        if any(key in right_click for key in ("heal", "heal_amount", "amount")):
            normalized["type"] = "heal"
        elif any(key in right_click for key in ("effect", "apply_effect")):
            normalized["type"] = "apply_effect"
    if "amount" not in normalized:
        amount = _first_alias_value(right_click, "amount", "heal_amount", "heal")
        if amount is not None:
            normalized["amount"] = amount
    if "effect" not in normalized:
        effect = _first_alias_value(right_click, "effect")
        if effect is None:
            effect = applied_effect_value
        if effect is not None:
            normalized["effect"] = effect
    if "duration_ticks" not in normalized:
        duration_ticks = _first_alias_value(right_click, "duration_ticks")
        if duration_ticks is None:
            duration_ticks = _first_alias_value(applied_effect_fields, "duration_ticks")
        if duration_ticks is not None:
            normalized["duration_ticks"] = duration_ticks
    if "duration_seconds" not in normalized:
        duration_seconds = _first_alias_value(right_click, "duration_seconds", "duration")
        if duration_seconds is None:
            duration_seconds = _first_alias_value(applied_effect_fields, "duration_seconds", "duration")
        if duration_seconds is not None:
            normalized["duration_seconds"] = duration_seconds
    if "cooldown_ticks" not in normalized:
        cooldown_ticks = _first_alias_value(right_click, "cooldown_ticks")
        if cooldown_ticks is not None:
            normalized["cooldown_ticks"] = cooldown_ticks
    if "cooldown_seconds" not in normalized:
        cooldown_seconds = _first_alias_value(right_click, "cooldown_seconds", "cooldown")
        if cooldown_seconds is not None:
            normalized["cooldown_seconds"] = cooldown_seconds
    if "consume" not in normalized and right_click.get("consume") is not None:
        normalized["consume"] = right_click.get("consume")
    return normalized


def _first_alias_value(mapping: dict, *keys: str) -> object | None:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _normalize_behavior_type_alias(value: str) -> str:
    if value == "heal":
        return "right_click_heal"
    if value in {"effect", "apply_effect"}:
        return "right_click_effect"
    return value


def _seconds_to_ticks(value: object) -> int:
    return int(round(float(value) * 20))


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
        "result": _normalize_recipe_reference_value(result, mod_id, referenceable_ids),
        "count": int(feature.get("count", 1)),
        "category": str(feature.get("category", "misc")),
        "group": feature.get("group"),
    }

    if recipe_type == "shapeless":
        ingredients = list(feature.get("ingredients", []))
        normalized["ingredients"] = [_normalize_recipe_reference_value(item, mod_id, referenceable_ids) for item in ingredients]
        normalized["pattern"] = []
        normalized["keys"] = {}
    else:
        keys = {str(key): _normalize_recipe_reference_value(value, mod_id, referenceable_ids) for key, value in feature.get("keys", {}).items()}
        normalized["pattern"] = [str(row) for row in feature.get("pattern", [])]
        normalized["keys"] = keys
        normalized["ingredients"] = []
    return normalized


def _decomposed_recipe_result_reference(value: object) -> object:
    if isinstance(value, dict):
        for key in ("item", "id", "result"):
            candidate = value.get(key)
            if not _blank_decomposed_value(candidate):
                return candidate
    return value


def _normalize_recipe_reference_value(value: object, mod_id: str, referenceable_ids: set[str]) -> str:
    reference = _decomposed_recipe_result_reference(value)
    return _normalize_reference(str(reference), mod_id, referenceable_ids)


def _normalize_reference(reference: str, mod_id: str, referenceable_ids: set[str]) -> str:
    if ":" in reference:
        namespace, value = reference.split(":", 1)
        return f"{namespace}:{slugify_mod_id(value, fallback='generated_ref')}"
    normalized_id = slugify_mod_id(reference, fallback="generated_ref")
    if normalized_id in referenceable_ids:
        return f"{mod_id}:{normalized_id}"
    return f"{mod_id}:{normalized_id}"


def _blank_decomposed_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "none", "null", "nil", "n/a", "undefined"}
    if isinstance(value, (list, tuple, set, dict)):
        return not value
    return False


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
    if isinstance(value, dict):
        for key in ("tool_material", "material", "id", "name"):
            candidate = value.get(key)
            if not _blank_decomposed_value(candidate):
                return _normalize_tool_material(candidate, warnings, identifier)
        inferred = _infer_equipment_material_from_identifier(identifier)
        if inferred in SUPPORTED_TOOL_MATERIALS:
            warnings.append(f"Feature '{identifier}' supplied object tool_material; inferred '{inferred}' from id.")
            return inferred
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
    if isinstance(value, dict):
        for key in ("armor_material", "material", "id", "name"):
            candidate = value.get(key)
            if not _blank_decomposed_value(candidate):
                return _normalize_armor_material(candidate, warnings, identifier)
        inferred = _infer_equipment_material_from_identifier(identifier)
        if inferred in SUPPORTED_ARMOR_MATERIALS:
            warnings.append(f"Armor '{identifier}' supplied object armor_material; inferred '{inferred}' from id.")
            return inferred
    normalized = str(value or "iron").lower()
    aliases = {"golden": "gold", "chain": "chainmail"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_ARMOR_MATERIALS:
        warnings.append(f"Armor '{identifier}' requested unsupported armor_material '{normalized}', normalized to 'iron'.")
        return "iron"
    return normalized


def _infer_equipment_material_from_identifier(identifier: str) -> str:
    for suffix in (
        "sword",
        "pickaxe",
        "axe",
        "shovel",
        "hoe",
        "helmet",
        "chestplate",
        "leggings",
        "boots",
    ):
        marker = f"_{suffix}"
        if identifier.endswith(marker):
            return identifier.removesuffix(marker)
    return ""


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
