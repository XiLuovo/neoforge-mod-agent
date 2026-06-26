from __future__ import annotations

import json
import re
import struct
import zlib
from pathlib import Path

from .config import AppConfig
from .java_extension_generator import (
    JAVA_EXTENSION_CLASS_PATTERN,
    JAVA_EXTENSION_INPUT_FORBIDDEN_TOKENS,
    JAVA_EXTENSION_METHOD_PATTERN,
    JAVA_EXTENSION_SOURCE_FORBIDDEN_TOKENS,
    SUPPORTED_JAVA_EXTENSION_IMPORTS,
    SUPPORTED_JAVA_EXTENSION_RETURN_TYPES,
)
from .models import BalancePlanSpec, ModSpec, ProgressionSpec, QuestSpec, RecipeSpec, Severity, ValidationIssue, ValidationReport
from .tools import load_template_java_version


MOD_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
PACKAGE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+([-.][0-9A-Za-z.]+)*$")
CONTENT_ID_PATTERN = re.compile(r"^[a-z0-9_./-]+$")
SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
SUPPORTED_TOOL_MATERIALS = {"wood", "stone", "copper", "iron", "diamond", "gold", "golden", "netherite", "ruby"}
SUPPORTED_TOOL_TYPES = {"pickaxe", "axe", "shovel", "hoe"}
SUPPORTED_ARMOR_TYPES = {"helmet", "chestplate", "leggings", "boots"}
SUPPORTED_ARMOR_MATERIALS = {"leather", "chainmail", "chain", "copper", "iron", "diamond", "gold", "golden", "netherite", "ruby"}
RESOURCE_LOCATION_PATTERN = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")
SUPPORTED_ITEM_BEHAVIORS = {"right_click_heal", "right_click_effect", "event_action"}
SUPPORTED_ON_HIT_BEHAVIORS = {"ignite"}
SUPPORTED_BEHAVIOR_TRIGGER_MODES = {"any", "all", "sequence"}
SUPPORTED_BEHAVIOR_TRIGGERS = {
    "right_click",
    "hit_entity",
    "inventory_tick",
    "inventory_changed",
    "block_use",
    "block_tick",
    "server_tick",
    "machine_tick",
    "machine_complete",
    "energy_low",
    "entity_tick",
    "hurt",
    "attack",
    "death",
    "spawn",
    "target_acquired",
    "quest_start",
    "task_complete",
    "quest_complete",
    "guide_open",
    "stage_enter",
    "stage_complete",
    "link_unlock",
    "loop_complete",
}
SUPPORTED_RUNTIME_BEHAVIOR_TRIGGERS = {"right_click", "hit_entity", "inventory_tick", "block_use"}
SUPPORTED_BEHAVIOR_ACTIONS = {
    "heal",
    "apply_effect",
    "ignite",
    "consume_item",
    "cooldown",
    "spawn_particles",
    "play_sound",
    "set_state",
    "increment_state",
    "clear_state",
    "consume_resource",
    "restore_resource",
    "transfer_resource",
    "chain_event",
}
SUPPORTED_BEHAVIOR_CONDITIONS = {
    "sneaking",
    "not_sneaking",
    "health_below",
    "health_above",
    "random_chance",
    "state_equals",
    "state_not_equals",
    "state_above",
    "state_below",
    "resource_at_least",
    "resource_below",
    "cooldown_ready",
    "combo_ready",
}
SUPPORTED_ITEM_TRIGGERS = {"right_click", "inventory_tick"}
SUPPORTED_SWORD_TRIGGERS = {"right_click", "hit_entity", "inventory_tick"}
SUPPORTED_BLOCK_TRIGGERS = {"block_use"}
SUPPORTED_MACHINE_BEHAVIOR_TRIGGERS = {"server_tick", "machine_tick", "machine_complete", "energy_low", "inventory_changed"}
SUPPORTED_ENTITY_BEHAVIOR_TRIGGERS = {"spawn", "entity_tick", "hurt", "death", "attack", "target_acquired"}
SUPPORTED_QUEST_BEHAVIOR_TRIGGERS = {"quest_start", "task_complete", "quest_complete", "guide_open"}
SUPPORTED_PROGRESSION_BEHAVIOR_TRIGGERS = {"stage_enter", "stage_complete", "link_unlock", "loop_complete"}
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
SUPPORTED_ENTITY_ATTACKS = {"none", "melee"}
SUPPORTED_ENTITY_SPAWN_PLACEMENTS = {"on_ground"}
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
SUPPORTED_BALANCE_PROFILES = {"easy", "standard", "expert"}
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


def _issue(severity: Severity, message: str, field_name: str | None = None) -> ValidationIssue:
    return ValidationIssue(severity=severity, message=message, field_name=field_name)


def validate_mod_spec(spec: ModSpec, config: AppConfig) -> ValidationReport:
    issues: list[ValidationIssue] = []

    if not MOD_ID_PATTERN.fullmatch(spec.mod_id):
        issues.append(_issue(Severity.ERROR, "mod_id must match [a-z][a-z0-9_]{1,63}.", "mod_id"))

    if not spec.display_name.strip():
        issues.append(_issue(Severity.ERROR, "display_name must not be empty.", "display_name"))

    if not PACKAGE_PATTERN.fullmatch(spec.package_name):
        issues.append(
            _issue(
                Severity.ERROR,
                "package_name must look like a Java package, for example com.example.mymod.",
                "package_name",
            )
        )

    if not VERSION_PATTERN.fullmatch(spec.version):
        issues.append(
            _issue(
                Severity.ERROR,
                "version should follow a simple semantic version such as 1.0.0.",
                "version",
            )
        )

    if spec.loader != config.loader:
        issues.append(_issue(Severity.ERROR, f"loader is fixed to {config.loader} for this project.", "loader"))

    if spec.neo_version != config.neo_version:
        issues.append(
            _issue(Severity.ERROR, f"neo_version is fixed to {config.neo_version} for this project.", "neo_version")
        )

    if spec.java_version != config.java_version:
        issues.append(
            _issue(
                Severity.WARNING,
                f"Task target is Java {config.java_version}, but spec currently says Java {spec.java_version}.",
                "java_version",
            )
        )

    seen_ids: set[str] = set()
    for feature in [*spec.all_content(), *spec.entities, *spec.all_world_like(), *spec.java_extensions]:
        if not CONTENT_ID_PATTERN.fullmatch(feature.identifier):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Feature identifier '{feature.identifier}' contains unsupported characters.",
                    feature.feature_type,
                )
            )
        if feature.identifier in seen_ids:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Duplicate generated content identifier '{feature.identifier}'.",
                    feature.feature_type,
                )
            )
        seen_ids.add(feature.identifier)
        if not SNAKE_CASE_PATTERN.fullmatch(feature.identifier):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Feature identifier '{feature.identifier}' must use snake_case.",
                    feature.feature_type,
                )
            )

    known_local_ids = {feature.identifier for feature in spec.all_content()}
    known_world_ids = {feature.identifier for feature in spec.all_world_like()}

    for block in spec.blocks:
        if block.block_kind not in SUPPORTED_BLOCK_KINDS:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Block '{block.identifier}' uses unsupported block_kind '{block.block_kind}'.",
                    "blocks",
                )
            )
        if block.behavior is not None:
            if block.block_kind != "cube":
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Block '{block.identifier}' Behavior DSL currently supports block_kind 'cube' only.",
                        "blocks",
                    )
                )
            _validate_behavior(
                block.behavior,
                issues,
                owner=f"Block '{block.identifier}'",
                field_name="blocks",
                allowed_triggers=SUPPORTED_BLOCK_TRIGGERS,
                host_kind="block",
            )
        if block.base_block and not _reference_exists(block.base_block, spec.mod_id, known_local_ids):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Block '{block.identifier}' references unknown base_block '{block.base_block}'.",
                    "blocks",
                )
            )

    for machine in spec.machines:
        if machine.machine_kind not in SUPPORTED_MACHINE_KINDS:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Machine '{machine.identifier}' uses unsupported machine_kind '{machine.machine_kind}'.",
                    "machines",
                )
            )
        if machine.block_kind != "cube":
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Machine '{machine.identifier}' must use block_kind 'cube'.",
                    "machines",
                )
            )
        if machine.inventory_slots <= 0:
            issues.append(_issue(Severity.ERROR, f"Machine '{machine.identifier}' inventory_slots must be > 0.", "machines"))
        if machine.input_slots < 0:
            issues.append(_issue(Severity.ERROR, f"Machine '{machine.identifier}' input_slots must be >= 0.", "machines"))
        if machine.output_slots < 0:
            issues.append(_issue(Severity.ERROR, f"Machine '{machine.identifier}' output_slots must be >= 0.", "machines"))
        if machine.input_slots + machine.output_slots > machine.inventory_slots:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Machine '{machine.identifier}' input_slots + output_slots must not exceed inventory_slots.",
                    "machines",
                )
            )
        if machine.energy_capacity < 0:
            issues.append(_issue(Severity.ERROR, f"Machine '{machine.identifier}' energy_capacity must be >= 0.", "machines"))
        if machine.energy_per_tick < 0:
            issues.append(_issue(Severity.ERROR, f"Machine '{machine.identifier}' energy_per_tick must be >= 0.", "machines"))
        if machine.max_progress <= 0:
            issues.append(_issue(Severity.ERROR, f"Machine '{machine.identifier}' max_progress must be > 0.", "machines"))
        if machine.base_block and not _reference_exists(machine.base_block, spec.mod_id, known_local_ids):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Machine '{machine.identifier}' references unknown base_block '{machine.base_block}'.",
                    "machines",
                )
            )
        if machine.behavior is not None:
            _validate_behavior(
                machine.behavior,
                issues,
                owner=f"Machine '{machine.identifier}'",
                field_name="machines",
                allowed_triggers=SUPPORTED_MACHINE_BEHAVIOR_TRIGGERS,
                host_kind="machine",
            )

    for entity in spec.entities:
        if entity.entity_kind not in SUPPORTED_ENTITY_KINDS:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Entity '{entity.identifier}' uses unsupported entity_kind '{entity.entity_kind}'.",
                    "entities",
                )
            )
        if entity.category not in SUPPORTED_ENTITY_CATEGORIES:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Entity '{entity.identifier}' uses unsupported category '{entity.category}'.",
                    "entities",
                )
            )
        if entity.width <= 0 or entity.height <= 0:
            issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' width and height must be > 0.", "entities"))
        if entity.tracking_range <= 0:
            issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' tracking_range must be > 0.", "entities"))
        if entity.update_interval <= 0:
            issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' update_interval must be > 0.", "entities"))
        if entity.xp_reward < 0:
            issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' xp_reward must be >= 0.", "entities"))
        attributes = entity.attributes
        if attributes.max_health <= 0:
            issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' max_health must be > 0.", "entities"))
        if attributes.movement_speed <= 0:
            issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' movement_speed must be > 0.", "entities"))
        if attributes.attack_damage < 0:
            issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' attack_damage must be >= 0.", "entities"))
        if attributes.armor < 0:
            issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' armor must be >= 0.", "entities"))
        if attributes.follow_range <= 0:
            issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' follow_range must be > 0.", "entities"))
        if attributes.knockback_resistance < 0:
            issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' knockback_resistance must be >= 0.", "entities"))
        for drop in entity.drops:
            if not RESOURCE_LOCATION_PATTERN.fullmatch(drop.item):
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' drop item '{drop.item}' must be a resource location.", "entities"))
            if drop.min_count <= 0 or drop.max_count <= 0:
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' drop counts must be > 0.", "entities"))
            if drop.min_count > drop.max_count:
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' drop min_count must be <= max_count.", "entities"))
            if not (0.0 <= drop.chance <= 1.0):
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' drop chance must be between 0 and 1.", "entities"))
        if entity.spawn is not None:
            spawn = entity.spawn
            if spawn.enabled:
                if not spawn.biomes:
                    issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' spawn.biomes must not be empty.", "entities"))
                if spawn.weight <= 0:
                    issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' spawn weight must be > 0.", "entities"))
                if spawn.min_count <= 0 or spawn.max_count <= 0:
                    issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' spawn counts must be > 0.", "entities"))
                if spawn.min_count > spawn.max_count:
                    issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' spawn min_count must be <= max_count.", "entities"))
                if spawn.placement not in SUPPORTED_ENTITY_SPAWN_PLACEMENTS:
                    issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' spawn placement '{spawn.placement}' is unsupported.", "entities"))
        for goal in entity.goals:
            if goal.goal_type not in SUPPORTED_ENTITY_GOALS:
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' AI goal '{goal.goal_type}' is unsupported.", "entities"))
            if goal.priority < 0:
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' AI goal priority must be >= 0.", "entities"))
            if goal.speed is not None and goal.speed <= 0:
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' AI goal speed must be > 0.", "entities"))
            if goal.distance is not None and goal.distance <= 0:
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' AI goal distance must be > 0.", "entities"))
        if entity.attack is not None:
            if entity.attack.attack_type not in SUPPORTED_ENTITY_ATTACKS:
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' attack type '{entity.attack.attack_type}' is unsupported.", "entities"))
            if entity.attack.damage is not None and entity.attack.damage < 0:
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' attack damage must be >= 0.", "entities"))
            if entity.attack.speed <= 0:
                issues.append(_issue(Severity.ERROR, f"Entity '{entity.identifier}' attack speed must be > 0.", "entities"))
        if entity.behavior is not None:
            _validate_behavior(
                entity.behavior,
                issues,
                owner=f"Entity '{entity.identifier}'",
                field_name="entities",
                allowed_triggers=SUPPORTED_ENTITY_BEHAVIOR_TRIGGERS,
                host_kind="entity",
            )

    for dimension in spec.dimensions:
        if dimension.dimension_type not in SUPPORTED_DIMENSION_TYPES:
            issues.append(_issue(Severity.ERROR, f"Dimension '{dimension.identifier}' uses unsupported dimension_type '{dimension.dimension_type}'.", "dimensions"))
        if dimension.generator not in SUPPORTED_DIMENSION_GENERATORS:
            issues.append(_issue(Severity.ERROR, f"Dimension '{dimension.identifier}' uses unsupported generator '{dimension.generator}'.", "dimensions"))
        if not _reference_exists(dimension.biome, spec.mod_id, known_world_ids):
            issues.append(_issue(Severity.ERROR, f"Dimension '{dimension.identifier}' references unknown biome '{dimension.biome}'.", "dimensions"))
        if dimension.height <= 0 or dimension.logical_height <= 0:
            issues.append(_issue(Severity.ERROR, f"Dimension '{dimension.identifier}' height values must be > 0.", "dimensions"))
        if dimension.height % 16 != 0:
            issues.append(_issue(Severity.ERROR, f"Dimension '{dimension.identifier}' height must be a multiple of 16.", "dimensions"))
        if dimension.min_y % 16 != 0:
            issues.append(_issue(Severity.ERROR, f"Dimension '{dimension.identifier}' min_y must be a multiple of 16.", "dimensions"))
        if dimension.logical_height > dimension.height:
            issues.append(_issue(Severity.ERROR, f"Dimension '{dimension.identifier}' logical_height must be <= height.", "dimensions"))
        if dimension.coordinate_scale <= 0:
            issues.append(_issue(Severity.ERROR, f"Dimension '{dimension.identifier}' coordinate_scale must be > 0.", "dimensions"))
        if not (0.0 <= dimension.ambient_light <= 1.0):
            issues.append(_issue(Severity.ERROR, f"Dimension '{dimension.identifier}' ambient_light must be between 0 and 1.", "dimensions"))

    for biome in spec.biomes:
        if not (0.0 <= biome.downfall <= 1.0):
            issues.append(_issue(Severity.ERROR, f"Biome '{biome.identifier}' downfall must be between 0 and 1.", "biomes"))
        for color_name in ("sky_color", "water_color", "water_fog_color", "fog_color", "grass_color", "foliage_color"):
            color = getattr(biome, color_name)
            if color is not None and not (0 <= color <= 0xFFFFFF):
                issues.append(_issue(Severity.ERROR, f"Biome '{biome.identifier}' {color_name} must be an RGB integer.", "biomes"))
        for feature_ref in biome.features:
            if not _reference_exists(feature_ref, spec.mod_id, known_world_ids):
                issues.append(_issue(Severity.ERROR, f"Biome '{biome.identifier}' references unknown placed feature '{feature_ref}'.", "biomes"))

    for feature in spec.world_features:
        if feature.feature_kind not in SUPPORTED_WORLD_FEATURE_KINDS:
            issues.append(_issue(Severity.ERROR, f"World feature '{feature.identifier}' uses unsupported feature_kind '{feature.feature_kind}'.", "world_features"))
        if feature.step not in SUPPORTED_WORLDGEN_STEPS:
            issues.append(_issue(Severity.ERROR, f"World feature '{feature.identifier}' uses unsupported step '{feature.step}'.", "world_features"))
        if not _resource_or_tag(feature.target_block):
            issues.append(_issue(Severity.ERROR, f"World feature '{feature.identifier}' target_block must be a resource location or tag.", "world_features"))
        if not (_reference_exists(feature.placed_block, spec.mod_id, known_local_ids) or _resource_or_tag(feature.placed_block)):
            issues.append(_issue(Severity.ERROR, f"World feature '{feature.identifier}' placed_block must reference a generated block or resource location.", "world_features"))
        if not feature.biomes:
            issues.append(_issue(Severity.ERROR, f"World feature '{feature.identifier}' biomes must not be empty.", "world_features"))
        if feature.min_y >= feature.max_y:
            issues.append(_issue(Severity.ERROR, f"World feature '{feature.identifier}' min_y must be < max_y.", "world_features"))
        if feature.vein_size <= 0 or feature.veins_per_chunk <= 0:
            issues.append(_issue(Severity.ERROR, f"World feature '{feature.identifier}' vein_size and veins_per_chunk must be > 0.", "world_features"))
        if not (0.0 <= feature.discard_chance_on_air_exposure <= 1.0):
            issues.append(_issue(Severity.ERROR, f"World feature '{feature.identifier}' discard_chance_on_air_exposure must be between 0 and 1.", "world_features"))

    for structure in spec.structures:
        if structure.structure_kind not in SUPPORTED_STRUCTURE_KINDS:
            issues.append(_issue(Severity.ERROR, f"Structure '{structure.identifier}' uses unsupported structure_kind '{structure.structure_kind}'.", "structures"))
        if structure.step not in SUPPORTED_STRUCTURE_STEPS:
            issues.append(_issue(Severity.ERROR, f"Structure '{structure.identifier}' uses unsupported step '{structure.step}'.", "structures"))
        if structure.terrain_adaptation not in SUPPORTED_TERRAIN_ADAPTATION:
            issues.append(_issue(Severity.ERROR, f"Structure '{structure.identifier}' uses unsupported terrain_adaptation '{structure.terrain_adaptation}'.", "structures"))
        if not structure.biomes:
            issues.append(_issue(Severity.ERROR, f"Structure '{structure.identifier}' biomes must not be empty.", "structures"))
        if structure.spacing <= 0:
            issues.append(_issue(Severity.ERROR, f"Structure '{structure.identifier}' spacing must be > 0.", "structures"))
        if structure.separation < 0 or structure.separation >= structure.spacing:
            issues.append(_issue(Severity.ERROR, f"Structure '{structure.identifier}' separation must be >= 0 and < spacing.", "structures"))
        if structure.size <= 0:
            issues.append(_issue(Severity.ERROR, f"Structure '{structure.identifier}' size must be > 0.", "structures"))
        if structure.loot_table and not _reference_exists(structure.loot_table.replace("chests/", ""), spec.mod_id, known_world_ids):
            issues.append(_issue(Severity.ERROR, f"Structure '{structure.identifier}' references unknown loot_table '{structure.loot_table}'.", "structures"))

    for pool in spec.loot_pools:
        if pool.table_kind not in SUPPORTED_LOOT_TABLE_KINDS:
            issues.append(_issue(Severity.ERROR, f"Loot pool '{pool.identifier}' uses unsupported table_kind '{pool.table_kind}'.", "loot_pools"))
        if pool.rolls <= 0:
            issues.append(_issue(Severity.ERROR, f"Loot pool '{pool.identifier}' rolls must be > 0.", "loot_pools"))
        if not pool.entries:
            issues.append(_issue(Severity.ERROR, f"Loot pool '{pool.identifier}' must declare at least one entry.", "loot_pools"))
        for entry in pool.entries:
            if not _resource_or_tag(entry.item) or entry.item.startswith("#"):
                issues.append(_issue(Severity.ERROR, f"Loot pool '{pool.identifier}' entry item '{entry.item}' must be a resource location.", "loot_pools"))
            if entry.min_count <= 0 or entry.max_count <= 0:
                issues.append(_issue(Severity.ERROR, f"Loot pool '{pool.identifier}' entry counts must be > 0.", "loot_pools"))
            if entry.min_count > entry.max_count:
                issues.append(_issue(Severity.ERROR, f"Loot pool '{pool.identifier}' entry min_count must be <= max_count.", "loot_pools"))
            if entry.weight <= 0:
                issues.append(_issue(Severity.ERROR, f"Loot pool '{pool.identifier}' entry weight must be > 0.", "loot_pools"))
            if not (0.0 <= entry.chance <= 1.0):
                issues.append(_issue(Severity.ERROR, f"Loot pool '{pool.identifier}' entry chance must be between 0 and 1.", "loot_pools"))

    for ore in spec.ores:
        if ore.block_kind != "cube":
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Ore '{ore.identifier}' must use block_kind 'cube'.",
                    "ores",
                )
            )
        if ore.base_block and not _reference_exists(ore.base_block, spec.mod_id, known_local_ids):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Ore '{ore.identifier}' references unknown base_block '{ore.base_block}'.",
                    "ores",
                )
            )
        if ore.drop and not _reference_exists(ore.drop, spec.mod_id, known_local_ids):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Ore '{ore.identifier}' references unknown drop '{ore.drop}'.",
                    "ores",
                )
            )
        if ore.worldgen is not None:
            if not isinstance(ore.worldgen.enabled, bool):
                issues.append(_issue(Severity.ERROR, f"Ore '{ore.identifier}' worldgen.enabled must be a boolean.", "ores"))
            if ore.worldgen.dimension != "minecraft:overworld":
                issues.append(
                    _issue(
                        Severity.WARNING,
                        f"Ore '{ore.identifier}' worldgen dimension '{ore.worldgen.dimension}' is not supported yet; only minecraft:overworld is supported.",
                        "ores",
                    )
                )
            if ore.worldgen.min_y >= ore.worldgen.max_y:
                issues.append(_issue(Severity.ERROR, f"Ore '{ore.identifier}' worldgen min_y must be < max_y.", "ores"))
            if ore.worldgen.min_y < -64:
                issues.append(_issue(Severity.ERROR, f"Ore '{ore.identifier}' worldgen min_y must be >= -64.", "ores"))
            if ore.worldgen.max_y > 320:
                issues.append(_issue(Severity.ERROR, f"Ore '{ore.identifier}' worldgen max_y must be <= 320.", "ores"))
            if ore.worldgen.vein_size <= 0:
                issues.append(_issue(Severity.ERROR, f"Ore '{ore.identifier}' worldgen vein_size must be > 0.", "ores"))
            if ore.worldgen.veins_per_chunk <= 0:
                issues.append(_issue(Severity.ERROR, f"Ore '{ore.identifier}' worldgen veins_per_chunk must be > 0.", "ores"))
        if ore.behavior is not None:
            _validate_behavior(
                ore.behavior,
                issues,
                owner=f"Ore '{ore.identifier}'",
                field_name="ores",
                allowed_triggers=SUPPORTED_BLOCK_TRIGGERS,
                host_kind="block",
            )

    for sword in spec.swords:
        if sword.tool_material.lower() not in SUPPORTED_TOOL_MATERIALS:
            issues.append(
                _issue(
                    Severity.WARNING,
                    f"Sword '{sword.identifier}' uses unsupported tool_material '{sword.tool_material}', generator may fallback.",
                    "swords",
                )
            )
        if sword.on_hit is not None:
            if sword.on_hit.behavior_type not in SUPPORTED_ON_HIT_BEHAVIORS:
                issues.append(_issue(Severity.ERROR, f"Sword '{sword.identifier}' uses unsupported on_hit type '{sword.on_hit.behavior_type}'.", "swords"))
            if sword.on_hit.behavior_type == "ignite" and sword.on_hit.seconds <= 0:
                issues.append(_issue(Severity.ERROR, f"Sword '{sword.identifier}' ignite seconds must be > 0.", "swords"))
        if sword.behavior is not None:
            _validate_behavior(
                sword.behavior,
                issues,
                owner=f"Sword '{sword.identifier}'",
                field_name="swords",
                allowed_triggers=SUPPORTED_SWORD_TRIGGERS,
                host_kind="sword",
            )

    for tool in spec.tools:
        if tool.tool_type.lower() not in SUPPORTED_TOOL_TYPES:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Tool '{tool.identifier}' uses unsupported tool_type '{tool.tool_type}'.",
                    "tools",
                )
            )
        if tool.tool_material.lower() not in SUPPORTED_TOOL_MATERIALS:
            issues.append(
                _issue(
                    Severity.WARNING,
                    f"Tool '{tool.identifier}' uses unsupported tool_material '{tool.tool_material}', generator may fallback.",
                    "tools",
                )
            )

    for armor in spec.armors:
        if armor.armor_type.lower() not in SUPPORTED_ARMOR_TYPES:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Armor '{armor.identifier}' uses unsupported armor_type '{armor.armor_type}'.",
                    "armors",
                )
            )
        if armor.armor_material.lower() not in SUPPORTED_ARMOR_MATERIALS:
            issues.append(
                _issue(
                    Severity.WARNING,
                    f"Armor '{armor.identifier}' uses unsupported armor_material '{armor.armor_material}', generator may fallback.",
                    "armors",
                )
            )

    for item in spec.items:
        if item.behavior is not None:
            _validate_behavior(
                item.behavior,
                issues,
                owner=f"Item '{item.identifier}'",
                field_name="items",
                allowed_triggers=SUPPORTED_ITEM_TRIGGERS,
                host_kind="item",
            )

    for progression in spec.progressions:
        if progression.behavior is not None:
            _validate_behavior(
                progression.behavior,
                issues,
                owner=f"Progression '{progression.identifier}'",
                field_name="progressions",
                allowed_triggers=SUPPORTED_PROGRESSION_BEHAVIOR_TRIGGERS,
                host_kind="progression",
            )

    for quest in spec.quests:
        if quest.behavior is not None:
            _validate_behavior(
                quest.behavior,
                issues,
                owner=f"Quest '{quest.identifier}'",
                field_name="quests",
                allowed_triggers=SUPPORTED_QUEST_BEHAVIOR_TRIGGERS,
                host_kind="quest",
            )

    for food in spec.foods:
        for effect in food.effects:
            if not RESOURCE_LOCATION_PATTERN.fullmatch(effect.effect):
                issues.append(_issue(Severity.ERROR, f"Food '{food.identifier}' has invalid effect resource location '{effect.effect}'.", "foods"))
            if effect.duration_ticks <= 0:
                issues.append(_issue(Severity.ERROR, f"Food '{food.identifier}' effect duration_ticks must be > 0.", "foods"))
            if effect.amplifier < 0:
                issues.append(_issue(Severity.ERROR, f"Food '{food.identifier}' effect amplifier must be >= 0.", "foods"))
            if not (0.0 <= effect.probability <= 1.0):
                issues.append(_issue(Severity.ERROR, f"Food '{food.identifier}' effect probability must be between 0 and 1.", "foods"))

    for extension in spec.java_extensions:
        if not JAVA_EXTENSION_CLASS_PATTERN.fullmatch(extension.class_name):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Java extension '{extension.identifier}' class_name must be PascalCase.",
                    "java_extensions",
                )
            )
        if not extension.purpose.strip():
            issues.append(_issue(Severity.WARNING, f"Java extension '{extension.identifier}' should explain its purpose.", "java_extensions"))
        if not extension.explanation.strip():
            issues.append(_issue(Severity.WARNING, f"Java extension '{extension.identifier}' should include an explanation.", "java_extensions"))
        if not extension.methods:
            issues.append(_issue(Severity.ERROR, f"Java extension '{extension.identifier}' must declare at least one method.", "java_extensions"))
        for import_line in extension.allowed_imports:
            if import_line not in SUPPORTED_JAVA_EXTENSION_IMPORTS:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Java extension '{extension.identifier}' import '{import_line}' is outside the sandbox allowlist.",
                        "java_extensions",
                    )
                )
        for method in extension.methods:
            if not JAVA_EXTENSION_METHOD_PATTERN.fullmatch(method.name):
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Java extension '{extension.identifier}' method name '{method.name}' must be lowerCamelCase.",
                        "java_extensions",
                    )
                )
            if method.return_type not in SUPPORTED_JAVA_EXTENSION_RETURN_TYPES:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Java extension '{extension.identifier}' return_type '{method.return_type}' is unsupported.",
                        "java_extensions",
                    )
                )
            _validate_java_extension_text(method.return_value, extension.identifier, "return_value", issues)
            _validate_java_extension_text(method.explanation, extension.identifier, "method explanation", issues)
        _validate_java_extension_text(extension.purpose, extension.identifier, "purpose", issues)
        _validate_java_extension_text(extension.explanation, extension.identifier, "explanation", issues)

    recipe_ids: set[str] = set()
    for recipe in spec.recipes:
        _validate_recipe(recipe, issues)
        if recipe.identifier in recipe_ids:
            issues.append(_issue(Severity.ERROR, f"Duplicate recipe identifier '{recipe.identifier}'.", "recipes"))
        recipe_ids.add(recipe.identifier)
        if not _reference_exists(recipe.result, spec.mod_id, known_local_ids):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Recipe '{recipe.identifier}' references unknown result '{recipe.result}'.",
                    "recipes",
                )
            )
        for item_id in recipe.ingredients:
            if not _reference_exists(item_id, spec.mod_id, known_local_ids):
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Recipe '{recipe.identifier}' references unknown ingredient '{item_id}'.",
                        "recipes",
                    )
                )
        for item_id in recipe.keys.values():
            if not _reference_exists(item_id, spec.mod_id, known_local_ids):
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Recipe '{recipe.identifier}' references unknown key item '{item_id}'.",
                        "recipes",
                    )
                )

    _validate_progressions(spec.progressions, spec, issues)
    if "Progression" in spec.requested_features and not spec.progressions:
        issues.append(
            _issue(
                Severity.WARNING,
                "Requested Progression DSL, but no progression loop is declared.",
                "progressions",
            )
        )
    _validate_balance_plans(spec.balance_plans, spec, issues)
    if "Balance Planner" in spec.requested_features and not spec.balance_plans:
        issues.append(
            _issue(
                Severity.WARNING,
                "Requested Balance Planner, but no balance plan is declared.",
                "balance_plans",
            )
        )
    _validate_quests(spec.quests, spec, issues)
    if any(label in spec.requested_features for label in ("Quests", "Advancements", "Guidebook")) and not spec.quests:
        issues.append(
            _issue(
                Severity.WARNING,
                "Requested Quest / Advancement / Guide DSL, but no quest chain is declared.",
                "quests",
            )
        )

    if not config.template_dir.exists():
        issues.append(
            _issue(
                Severity.ERROR,
                f"Template directory does not exist: {config.template_dir}",
                "template_dir",
            )
        )

    build_file = config.template_dir / "build.gradle"
    if not build_file.exists():
        issues.append(
            _issue(
                Severity.WARNING,
                f"Expected template build file was not found: {build_file}",
                "template_dir",
            )
        )

    template_java_version = load_template_java_version(config.template_dir)
    if template_java_version and template_java_version != config.java_version:
        issues.append(
            _issue(
                Severity.WARNING,
                f"Bundled template currently targets Java {template_java_version}, while config expects Java {config.java_version}.",
                "template_dir",
            )
        )

    workspace_parent = Path(config.workspace_root)
    if workspace_parent.exists() and not workspace_parent.is_dir():
        issues.append(
            _issue(Severity.ERROR, f"Workspace root is not a directory: {workspace_parent}", "workspace_root")
        )

    return ValidationReport(issues=issues)


def _validate_progressions(
    progressions: list[ProgressionSpec],
    spec: ModSpec,
    issues: list[ValidationIssue],
) -> None:
    target_lookup = _progression_target_lookup(spec)
    progression_ids: set[str] = set()
    for progression in progressions:
        if not progression.identifier.strip():
            issues.append(_issue(Severity.ERROR, "Progression id must not be empty.", "progressions"))
        elif not SNAKE_CASE_PATTERN.fullmatch(progression.identifier):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Progression '{progression.identifier}' id must use snake_case.",
                    "progressions",
                )
            )
        if progression.identifier in progression_ids:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Duplicate progression identifier '{progression.identifier}'.",
                    "progressions",
                )
            )
        progression_ids.add(progression.identifier)

        if not progression.title.strip():
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Progression '{progression.identifier}' title must not be empty.",
                    "progressions",
                )
            )
        if not progression.stages:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Progression '{progression.identifier}' must declare at least one stage.",
                    "progressions",
                )
            )
            continue

        stage_ids: set[str] = set()
        for stage in progression.stages:
            if not stage.identifier.strip():
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Progression '{progression.identifier}' has a stage with empty id.",
                        "progressions",
                    )
                )
                continue
            if not SNAKE_CASE_PATTERN.fullmatch(stage.identifier):
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Progression stage '{stage.identifier}' must use snake_case.",
                        "progressions",
                    )
                )
            if stage.identifier in stage_ids:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Progression '{progression.identifier}' has duplicate stage '{stage.identifier}'.",
                        "progressions",
                    )
                )
            stage_ids.add(stage.identifier)
            if stage.stage_type not in SUPPORTED_PROGRESSION_STAGE_TYPES:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Progression stage '{stage.identifier}' uses unsupported type '{stage.stage_type}'.",
                        "progressions",
                    )
                )
            if not stage.title.strip():
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Progression stage '{stage.identifier}' title must not be empty.",
                        "progressions",
                    )
                )
            for label, refs in (
                ("requires", stage.requires),
                ("provides", stage.provides),
                ("unlocks", stage.unlocks),
                ("evidence", stage.evidence),
            ):
                for reference in refs:
                    if not _progression_reference_exists(reference, spec.mod_id, target_lookup):
                        issues.append(
                            _issue(
                                Severity.WARNING,
                                f"Progression stage '{stage.identifier}' {label} references unknown target '{reference}'.",
                                "progressions",
                            )
                        )

        if progression.entry_stage and progression.entry_stage not in stage_ids:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Progression '{progression.identifier}' entry_stage references unknown stage '{progression.entry_stage}'.",
                    "progressions",
                )
            )
        if progression.end_stage and progression.end_stage not in stage_ids:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Progression '{progression.identifier}' end_stage references unknown stage '{progression.end_stage}'.",
                    "progressions",
                )
            )

        for link in progression.links:
            if link.from_stage not in stage_ids:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Progression '{progression.identifier}' link references unknown from stage '{link.from_stage}'.",
                        "progressions",
                    )
                )
            if link.to_stage not in stage_ids:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Progression '{progression.identifier}' link references unknown to stage '{link.to_stage}'.",
                        "progressions",
                    )
                )
            if link.from_stage and link.from_stage == link.to_stage:
                issues.append(
                    _issue(
                        Severity.WARNING,
                        f"Progression '{progression.identifier}' has a self-link on stage '{link.from_stage}'.",
                        "progressions",
                    )
                )

        if len(progression.stages) > 1 and not progression.links:
            issues.append(
                _issue(
                    Severity.WARNING,
                    f"Progression '{progression.identifier}' has multiple stages but no links.",
                    "progressions",
                )
            )

        cycle_paths = _progression_cycle_paths(stage_ids, progression.links)
        for cycle in cycle_paths[:3]:
            issues.append(
                _issue(
                    Severity.WARNING,
                    f"Progression '{progression.identifier}' contains a cycle: {' -> '.join(cycle)}.",
                    "progressions",
                )
            )

        entry_stage = progression.entry_stage or progression.stages[0].identifier
        end_stage = progression.end_stage or progression.stages[-1].identifier
        if entry_stage in stage_ids and end_stage in stage_ids:
            reachable = _progression_reachable_stages(entry_stage, progression.links)
            if end_stage not in reachable:
                issues.append(
                    _issue(
                        Severity.WARNING,
                        f"Progression '{progression.identifier}' entry stage '{entry_stage}' cannot reach end stage '{end_stage}'.",
                        "progressions",
                    )
                )


def _validate_balance_plans(
    balance_plans: list[BalancePlanSpec],
    spec: ModSpec,
    issues: list[ValidationIssue],
) -> None:
    progression_ids = {progression.identifier for progression in spec.progressions}
    plan_ids: set[str] = set()
    for plan in balance_plans:
        if not plan.identifier.strip():
            issues.append(_issue(Severity.ERROR, "Balance plan id must not be empty.", "balance_plans"))
        elif not SNAKE_CASE_PATTERN.fullmatch(plan.identifier):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Balance plan '{plan.identifier}' id must use snake_case.",
                    "balance_plans",
                )
            )
        if plan.identifier in plan_ids:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Duplicate balance plan identifier '{plan.identifier}'.",
                    "balance_plans",
                )
            )
        plan_ids.add(plan.identifier)

        if not plan.title.strip():
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Balance plan '{plan.identifier}' title must not be empty.",
                    "balance_plans",
                )
            )
        if plan.profile not in SUPPORTED_BALANCE_PROFILES:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Balance plan '{plan.identifier}' uses unsupported profile '{plan.profile}'.",
                    "balance_plans",
                )
            )
        if plan.target_progression and plan.target_progression not in progression_ids:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Balance plan '{plan.identifier}' target_progression references unknown progression '{plan.target_progression}'.",
                    "balance_plans",
                )
            )
        if not any([spec.recipes, spec.loot_pools, spec.entities, spec.machines]):
            issues.append(
                _issue(
                    Severity.WARNING,
                    f"Balance plan '{plan.identifier}' has no recipes, loot pools, entity drops, or machines to analyze.",
                    "balance_plans",
                )
            )


def _validate_quests(
    quests: list[QuestSpec],
    spec: ModSpec,
    issues: list[ValidationIssue],
) -> None:
    target_lookup = _progression_target_lookup(spec)
    progression_ids = {progression.identifier for progression in spec.progressions}
    quest_ids: set[str] = set()
    for quest in quests:
        if not quest.identifier.strip():
            issues.append(_issue(Severity.ERROR, "Quest id must not be empty.", "quests"))
        elif not SNAKE_CASE_PATTERN.fullmatch(quest.identifier):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Quest '{quest.identifier}' id must use snake_case.",
                    "quests",
                )
            )
        if quest.identifier in quest_ids:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Duplicate quest identifier '{quest.identifier}'.",
                    "quests",
                )
            )
        quest_ids.add(quest.identifier)

        if not quest.title.strip():
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Quest '{quest.identifier}' title must not be empty.",
                    "quests",
                )
            )
        if quest.guidebook_id and not SNAKE_CASE_PATTERN.fullmatch(quest.guidebook_id):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Quest '{quest.identifier}' guidebook_id must use snake_case.",
                    "quests",
                )
            )
        if quest.category and not SNAKE_CASE_PATTERN.fullmatch(quest.category):
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Quest '{quest.identifier}' category must use snake_case.",
                    "quests",
                )
            )
        if quest.target_progression and quest.target_progression not in progression_ids:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Quest '{quest.identifier}' target_progression references unknown progression '{quest.target_progression}'.",
                    "quests",
                )
            )
        if not quest.tasks and not quest.target_progression:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Quest '{quest.identifier}' must declare tasks or target_progression.",
                    "quests",
                )
            )

        task_ids: set[str] = set()
        for task in quest.tasks:
            if not task.identifier.strip():
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Quest '{quest.identifier}' has a task with empty id.",
                        "quests",
                    )
                )
                continue
            if not SNAKE_CASE_PATTERN.fullmatch(task.identifier):
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Quest task '{task.identifier}' must use snake_case.",
                        "quests",
                    )
                )
            if task.identifier in task_ids:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Quest '{quest.identifier}' has duplicate task '{task.identifier}'.",
                        "quests",
                    )
                )
            task_ids.add(task.identifier)
            if not task.title.strip():
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Quest task '{task.identifier}' title must not be empty.",
                        "quests",
                    )
                )
            if task.task_type not in SUPPORTED_QUEST_TASK_TYPES:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Quest task '{task.identifier}' uses unsupported type '{task.task_type}'.",
                        "quests",
                    )
                )
            if task.reward_xp < 0:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        f"Quest task '{task.identifier}' reward_xp must be >= 0.",
                        "quests",
                    )
                )
            if task.parent:
                if task.parent == task.identifier:
                    issues.append(
                        _issue(
                            Severity.ERROR,
                            f"Quest task '{task.identifier}' cannot be its own parent.",
                            "quests",
                        )
                    )
                elif task.parent not in task_ids:
                    issues.append(
                        _issue(
                            Severity.ERROR,
                            f"Quest task '{task.identifier}' parent references unknown earlier task '{task.parent}'.",
                            "quests",
                        )
                    )
            for label, reference in (("target", task.target), ("icon", task.icon)):
                if reference and not _progression_reference_exists(reference, spec.mod_id, target_lookup):
                    issues.append(
                        _issue(
                            Severity.WARNING,
                            f"Quest task '{task.identifier}' {label} references unknown target '{reference}'.",
                            "quests",
                        )
                    )


def _progression_target_lookup(spec: ModSpec) -> dict[str, str]:
    lookup: dict[str, str] = {}

    def add(identifier: str, target_type: str) -> None:
        if not identifier:
            return
        lookup[identifier] = target_type
        lookup[f"{spec.mod_id}:{identifier}"] = target_type

    for item in spec.items:
        add(item.identifier, "item")
    for food in spec.foods:
        add(food.identifier, "food")
    for sword in spec.swords:
        add(sword.identifier, "sword")
    for tool in spec.tools:
        add(tool.identifier, "tool")
    for armor in spec.armors:
        add(armor.identifier, "armor")
    for block in spec.blocks:
        add(block.identifier, "block")
    for machine in spec.machines:
        add(machine.identifier, "machine")
    for ore in spec.ores:
        add(ore.identifier, "ore")
    for entity in spec.entities:
        add(entity.identifier, "entity")
    for dimension in spec.dimensions:
        add(dimension.identifier, "dimension")
    for biome in spec.biomes:
        add(biome.identifier, "biome")
    for feature in spec.world_features:
        add(feature.identifier, "world_feature")
    for structure in spec.structures:
        add(structure.identifier, "structure")
    for pool in spec.loot_pools:
        add(pool.identifier, "loot_pool")
        lookup[f"chests/{pool.identifier}"] = "loot_pool"
        lookup[f"{spec.mod_id}:chests/{pool.identifier}"] = "loot_pool"
    for extension in spec.java_extensions:
        add(extension.identifier, "java_extension")
    for recipe in spec.recipes:
        add(recipe.identifier, "recipe")
        lookup[f"recipe:{recipe.identifier}"] = "recipe"
    return lookup


def _progression_reference_exists(reference: str, mod_id: str, lookup: dict[str, str]) -> bool:
    value = reference.strip()
    if not value:
        return False
    if value in lookup:
        return True
    if value.startswith("#"):
        return bool(RESOURCE_LOCATION_PATTERN.fullmatch(value[1:]))
    if RESOURCE_LOCATION_PATTERN.fullmatch(value):
        namespace, path = value.split(":", 1)
        if namespace != mod_id:
            return True
        return path in lookup or value in lookup
    if value.startswith("recipe:"):
        return value in lookup
    return False


def _progression_reachable_stages(entry_stage: str, links) -> set[str]:
    adjacency: dict[str, list[str]] = {}
    for link in links:
        adjacency.setdefault(link.from_stage, []).append(link.to_stage)
    seen = {entry_stage}
    stack = [entry_stage]
    while stack:
        current = stack.pop()
        for child in adjacency.get(current, []):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return seen


def _progression_cycle_paths(stage_ids: set[str], links) -> list[list[str]]:
    adjacency: dict[str, list[str]] = {stage_id: [] for stage_id in stage_ids}
    for link in links:
        if link.from_stage in adjacency and link.to_stage in stage_ids:
            adjacency[link.from_stage].append(link.to_stage)

    cycles: list[list[str]] = []
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(stage_id: str) -> None:
        if stage_id in visiting:
            start = visiting.index(stage_id)
            cycles.append([*visiting[start:], stage_id])
            return
        if stage_id in visited:
            return
        visiting.append(stage_id)
        for child in adjacency.get(stage_id, []):
            visit(child)
        visiting.pop()
        visited.add(stage_id)

    for stage_id in stage_ids:
        visit(stage_id)
    return cycles


def validate_generated_project(project: Path, spec: ModSpec) -> list[str]:
    warnings: list[str] = []
    project = project.resolve()
    asset_root = project / "src" / "main" / "resources" / "assets" / spec.mod_id
    data_root = project / "src" / "main" / "resources" / "data" / spec.mod_id

    en_us_path = asset_root / "lang" / "en_us.json"
    zh_cn_path = asset_root / "lang" / "zh_cn.json"
    en_us = _load_json_dict(en_us_path, warnings)
    zh_cn = _load_json_dict(zh_cn_path, warnings)

    for feature in spec.all_item_like():
        item_model = asset_root / "models" / "item" / f"{feature.identifier}.json"
        item_texture = asset_root / "textures" / "item" / f"{feature.identifier}.png"
        _require_file(item_model, warnings, f"Missing item model for {feature.identifier}")
        _require_file(item_texture, warnings, f"Missing item texture for {feature.identifier}")
        _validate_png(item_texture, warnings)
        _require_lang_key(en_us, f"item.{spec.mod_id}.{feature.identifier}", warnings, en_us_path)
        _require_lang_key(zh_cn, f"item.{spec.mod_id}.{feature.identifier}", warnings, zh_cn_path)

    for sword in spec.swords:
        sword_model_path = asset_root / "models" / "item" / f"{sword.identifier}.json"
        model_data = _load_json_dict_generic(sword_model_path, warnings)
        parent = str(model_data.get("parent", ""))
        if parent != "minecraft:item/handheld":
            warnings.append(f"Sword model for '{sword.identifier}' should use minecraft:item/handheld: {sword_model_path}")

    for tool in spec.tools:
        tool_model_path = asset_root / "models" / "item" / f"{tool.identifier}.json"
        model_data = _load_json_dict_generic(tool_model_path, warnings)
        parent = str(model_data.get("parent", ""))
        if parent != "minecraft:item/handheld":
            warnings.append(f"Tool model for '{tool.identifier}' should use minecraft:item/handheld: {tool_model_path}")

    for feature in spec.all_block_like():
        blockstate_path = asset_root / "blockstates" / f"{feature.identifier}.json"
        block_model_path = asset_root / "models" / "block" / f"{feature.identifier}.json"
        item_model_path = asset_root / "models" / "item" / f"{feature.identifier}.json"
        block_texture_path = asset_root / "textures" / "block" / f"{feature.identifier}.png"
        loot_table_path = data_root / "loot_table" / "blocks" / f"{feature.identifier}.json"
        mineable_tag_path = project / "src" / "main" / "resources" / "data" / "minecraft" / "tags" / "block" / "mineable" / "pickaxe.json"
        tool_tag_path = _tool_tag_path(project, feature.tool_tier)
        _require_file(blockstate_path, warnings, f"Missing blockstate for {feature.identifier}")
        _require_file(block_model_path, warnings, f"Missing block model for {feature.identifier}")
        _require_file(item_model_path, warnings, f"Missing block item model for {feature.identifier}")
        _require_file(block_texture_path, warnings, f"Missing block texture for {feature.identifier}")
        _validate_png(block_texture_path, warnings)
        _require_file(loot_table_path, warnings, f"Missing loot table for {feature.identifier}")
        if feature.requires_correct_tool:
            _require_file(mineable_tag_path, warnings, f"Missing mineable/pickaxe tag for {feature.identifier}")
            if tool_tag_path is not None:
                _require_file(tool_tag_path, warnings, f"Missing needs_*_tool tag for {feature.identifier}")
        _require_lang_key(en_us, f"block.{spec.mod_id}.{feature.identifier}", warnings, en_us_path)
        _require_lang_key(zh_cn, f"block.{spec.mod_id}.{feature.identifier}", warnings, zh_cn_path)

    for entity in spec.entities:
        entity_class = _entity_class_name(entity.identifier)
        renderer_class = _entity_renderer_class_name(entity.identifier)
        main_class = _main_class_name(spec)
        package_root = project / "src" / "main" / "java" / Path(*spec.package_name.split("."))
        entity_java = package_root / "entity" / f"{entity_class}.java"
        renderer_java = package_root / "client" / f"{renderer_class}.java"
        client_java = package_root / "client" / f"{main_class}EntityClient.java"
        texture_path = asset_root / "textures" / "entity" / f"{entity.identifier}.png"
        loot_table_path = data_root / "loot_table" / "entities" / f"{entity.identifier}.json"
        _require_file(entity_java, warnings, f"Missing entity class for {entity.identifier}")
        _require_file(renderer_java, warnings, f"Missing entity renderer for {entity.identifier}")
        _require_file(client_java, warnings, f"Missing entity client registration for {entity.identifier}")
        _require_file(texture_path, warnings, f"Missing entity texture for {entity.identifier}")
        _validate_png(texture_path, warnings)
        _require_file(loot_table_path, warnings, f"Missing entity loot table for {entity.identifier}")
        if entity.spawn is not None and entity.spawn.enabled:
            spawn_modifier = data_root / "neoforge" / "biome_modifier" / f"add_{entity.identifier}.json"
            _require_file(spawn_modifier, warnings, f"Missing spawn biome_modifier for {entity.identifier}")
        _require_lang_key(en_us, f"entity.{spec.mod_id}.{entity.identifier}", warnings, en_us_path)
        _require_lang_key(zh_cn, f"entity.{spec.mod_id}.{entity.identifier}", warnings, zh_cn_path)

    for recipe in spec.recipes:
        recipe_path = data_root / "recipe" / f"{recipe.identifier}.json"
        _require_file(recipe_path, warnings, f"Missing recipe json for {recipe.identifier}")
        if recipe.recipe_type == "shapeless":
            recipe_data = _load_json_dict_generic(recipe_path, warnings)
            if not recipe_data.get("ingredients"):
                warnings.append(f"Shapeless recipe '{recipe.identifier}' is missing ingredients in {recipe_path}")

    for ore in spec.ores:
        if ore.worldgen is None or not ore.worldgen.enabled:
            continue
        configured = project / "src" / "main" / "resources" / "data" / spec.mod_id / "worldgen" / "configured_feature" / f"{ore.identifier}.json"
        placed = project / "src" / "main" / "resources" / "data" / spec.mod_id / "worldgen" / "placed_feature" / f"{ore.identifier}.json"
        biome_modifier = project / "src" / "main" / "resources" / "data" / spec.mod_id / "neoforge" / "biome_modifier" / f"add_{ore.identifier}.json"
        _require_file(configured, warnings, f"Missing configured_feature for {ore.identifier}")
        _require_file(placed, warnings, f"Missing placed_feature for {ore.identifier}")
        _require_file(biome_modifier, warnings, f"Missing biome_modifier for {ore.identifier}")

    for dimension in spec.dimensions:
        dimension_type = data_root / "dimension_type" / f"{dimension.identifier}.json"
        dimension_path = data_root / "dimension" / f"{dimension.identifier}.json"
        _require_file(dimension_type, warnings, f"Missing dimension_type for {dimension.identifier}")
        _require_file(dimension_path, warnings, f"Missing dimension json for {dimension.identifier}")

    for biome in spec.biomes:
        biome_path = data_root / "worldgen" / "biome" / f"{biome.identifier}.json"
        _require_file(biome_path, warnings, f"Missing biome json for {biome.identifier}")

    for feature in spec.world_features:
        configured = data_root / "worldgen" / "configured_feature" / f"{feature.identifier}.json"
        placed = data_root / "worldgen" / "placed_feature" / f"{feature.identifier}.json"
        biome_modifier = data_root / "neoforge" / "biome_modifier" / f"add_{feature.identifier}.json"
        _require_file(configured, warnings, f"Missing configured_feature for {feature.identifier}")
        _require_file(placed, warnings, f"Missing placed_feature for {feature.identifier}")
        _require_file(biome_modifier, warnings, f"Missing biome_modifier for {feature.identifier}")

    for structure in spec.structures:
        structure_path = data_root / "worldgen" / "structure" / f"{structure.identifier}.json"
        structure_set = data_root / "worldgen" / "structure_set" / f"{structure.identifier}.json"
        start_pool = data_root / "worldgen" / "template_pool" / structure.identifier / "start_pool.json"
        _require_file(structure_path, warnings, f"Missing structure json for {structure.identifier}")
        _require_file(structure_set, warnings, f"Missing structure_set json for {structure.identifier}")
        _require_file(start_pool, warnings, f"Missing template_pool start_pool for {structure.identifier}")

    for pool in spec.loot_pools:
        loot_path = data_root / "loot_table" / "chests" / f"{pool.identifier}.json"
        _require_file(loot_path, warnings, f"Missing chest loot table for {pool.identifier}")

    if spec.java_extensions:
        package_root = project / "src" / "main" / "java" / Path(*spec.package_name.split("."))
        report_json = project / ".agent" / "java-extension-report.json"
        report_md = project / ".agent" / "java-extension-report.md"
        diff_md = project / ".agent" / "java-extension-diff.md"
        rollback_json = project / ".agent" / "java-extension-rollback-report.json"
        rollback_md = project / ".agent" / "java-extension-rollback-report.md"
        _require_file(report_json, warnings, "Missing Java extension report JSON")
        _require_file(report_md, warnings, "Missing Java extension report Markdown")
        _require_file(diff_md, warnings, "Missing Java extension diff report")
        _require_file(rollback_json, warnings, "Missing Java extension rollback report JSON")
        _require_file(rollback_md, warnings, "Missing Java extension rollback report Markdown")
        report_data = _load_json_dict_generic(report_json, warnings) if report_json.exists() else {}
        rollback_data = _load_json_dict_generic(rollback_json, warnings) if rollback_json.exists() else {}
        if isinstance(report_data, dict) and "build_gate" not in report_data:
            warnings.append(f"Java extension report is missing build_gate: {report_json}")
        if isinstance(report_data, dict) and "proof_artifacts" not in report_data:
            warnings.append(f"Java extension report is missing proof artifacts: {report_json}")
        if isinstance(rollback_data, dict) and "rollback_steps" not in rollback_data:
            warnings.append(f"Java extension rollback report is missing rollback_steps: {rollback_json}")
        report_classes = {
            str(entry.get("class_name", ""))
            for entry in report_data.get("extensions", [])
            if isinstance(entry, dict)
        } if isinstance(report_data, dict) else set()
        for extension in spec.java_extensions:
            extension_path = package_root / "extension" / f"{extension.class_name}.java"
            _require_file(extension_path, warnings, f"Missing Java extension class for {extension.identifier}")
            if extension.class_name not in report_classes:
                warnings.append(f"Java extension report is missing class '{extension.class_name}': {report_json}")
            if extension_path.exists():
                text = extension_path.read_text(encoding="utf-8", errors="replace")
                expected_package = f"package {spec.package_name}.extension;"
                if expected_package not in text:
                    warnings.append(f"Java extension '{extension.class_name}' has wrong package declaration: {extension_path}")
                if f"public final class {extension.class_name}" not in text:
                    warnings.append(f"Java extension '{extension.class_name}' is missing final class declaration: {extension_path}")
                for method in extension.methods:
                    if f"public static {method.return_type} {method.name}()" not in text:
                        warnings.append(f"Java extension '{extension.class_name}' is missing method '{method.name}': {extension_path}")
                for token in JAVA_EXTENSION_SOURCE_FORBIDDEN_TOKENS:
                    if token in text:
                        warnings.append(f"Java extension '{extension.class_name}' contains forbidden token '{token}': {extension_path}")

    if spec.progressions:
        report_json = project / ".agent" / "progression-report.json"
        report_md = project / ".agent" / "progression-report.md"
        _require_file(report_json, warnings, "Missing progression report JSON")
        _require_file(report_md, warnings, "Missing progression report Markdown")
        report_data = _load_json_dict_generic(report_json, warnings) if report_json.exists() else {}
        if isinstance(report_data, dict):
            totals = report_data.get("totals", {})
            if not isinstance(totals, dict):
                warnings.append(f"Progression report is missing totals: {report_json}")
            elif int(totals.get("loop_count", -1)) != len(spec.progressions):
                warnings.append(f"Progression report loop_count does not match ModSpec: {report_json}")
            if "progressions" not in report_data:
                warnings.append(f"Progression report is missing progressions list: {report_json}")

    if spec.balance_plans:
        report_json = project / ".agent" / "balance-report.json"
        report_md = project / ".agent" / "balance-report.md"
        _require_file(report_json, warnings, "Missing balance report JSON")
        _require_file(report_md, warnings, "Missing balance report Markdown")
        report_data = _load_json_dict_generic(report_json, warnings) if report_json.exists() else {}
        if isinstance(report_data, dict):
            totals = report_data.get("totals", {})
            if not isinstance(totals, dict):
                warnings.append(f"Balance report is missing totals: {report_json}")
            elif int(totals.get("plan_count", -1)) != len(spec.balance_plans):
                warnings.append(f"Balance report plan_count does not match ModSpec: {report_json}")
            if "plans" not in report_data:
                warnings.append(f"Balance report is missing plans list: {report_json}")

    if spec.quests:
        report_json = project / ".agent" / "quest-report.json"
        report_md = project / ".agent" / "quest-report.md"
        guide_md = project / ".agent" / "guidebook.md"
        _require_file(report_json, warnings, "Missing quest report JSON")
        _require_file(report_md, warnings, "Missing quest report Markdown")
        _require_file(guide_md, warnings, "Missing generated guidebook Markdown")
        report_data = _load_json_dict_generic(report_json, warnings) if report_json.exists() else {}
        if isinstance(report_data, dict):
            totals = report_data.get("totals", {})
            if str(report_data.get("version", "")) != "7.2":
                warnings.append(f"Quest report is missing V7.2 version: {report_json}")
            if not isinstance(totals, dict):
                warnings.append(f"Quest report is missing totals: {report_json}")
            elif int(totals.get("quest_count", -1)) != len(spec.quests):
                warnings.append(f"Quest report quest_count does not match ModSpec: {report_json}")
            if "quests" not in report_data:
                warnings.append(f"Quest report is missing quests list: {report_json}")
        for quest in spec.quests:
            task_ids = _quest_task_ids(quest, spec)
            for task_id in task_ids:
                advancement_path = data_root / "advancement" / quest.identifier / f"{task_id}.json"
                _require_file(advancement_path, warnings, f"Missing advancement json for {quest.identifier}/{task_id}")
            book_root = data_root / "patchouli_books" / quest.guidebook_id
            _require_file(book_root / "book.json", warnings, f"Missing Patchouli book json for {quest.identifier}")
            _require_file(book_root / "en_us" / "categories" / f"{quest.category}.json", warnings, f"Missing Patchouli category json for {quest.identifier}")
            _require_file(book_root / "en_us" / "entries" / f"{quest.identifier}.json", warnings, f"Missing Patchouli entry json for {quest.identifier}")

    metadata_path = project / ".agent" / "modspec.json"
    summary_path = project / ".agent" / "generation-summary.json"
    checklist_path = project / ".agent" / "manual-test-checklist.md"
    _require_file(metadata_path, warnings, "Missing .agent/modspec.json")
    _require_file(summary_path, warnings, "Missing .agent/generation-summary.json")
    _require_file(checklist_path, warnings, "Missing .agent/manual-test-checklist.md")
    _validate_generation_summary(summary_path, warnings)

    return warnings


def _validate_java_extension_text(
    value: str,
    identifier: str,
    label: str,
    issues: list[ValidationIssue],
) -> None:
    for token in JAVA_EXTENSION_INPUT_FORBIDDEN_TOKENS:
        if token in value:
            issues.append(
                _issue(
                    Severity.ERROR,
                    f"Java extension '{identifier}' {label} contains forbidden token '{token}'.",
                    "java_extensions",
                )
            )


def _validate_behavior(
    behavior,
    issues: list[ValidationIssue],
    *,
    owner: str,
    field_name: str,
    allowed_triggers: set[str],
    host_kind: str,
) -> None:
    if behavior.behavior_type not in SUPPORTED_ITEM_BEHAVIORS:
        issues.append(_issue(Severity.ERROR, f"{owner} uses unsupported behavior type '{behavior.behavior_type}'.", field_name))

    if behavior.cooldown_ticks < 0:
        issues.append(_issue(Severity.ERROR, f"{owner} cooldown_ticks must be >= 0.", field_name))

    if behavior.behavior_type == "right_click_heal":
        if behavior.amount is None or behavior.amount <= 0:
            issues.append(_issue(Severity.ERROR, f"{owner} right_click_heal amount must be > 0.", field_name))
    if behavior.behavior_type == "right_click_effect":
        if not behavior.effect or not RESOURCE_LOCATION_PATTERN.fullmatch(behavior.effect):
            issues.append(_issue(Severity.ERROR, f"{owner} right_click_effect must use a valid resource location.", field_name))
        if behavior.duration_ticks is None or behavior.duration_ticks <= 0:
            issues.append(_issue(Severity.ERROR, f"{owner} right_click_effect duration_ticks must be > 0.", field_name))
        if behavior.amplifier < 0:
            issues.append(_issue(Severity.ERROR, f"{owner} right_click_effect amplifier must be >= 0.", field_name))

    for event in behavior.events:
        event_triggers = [trigger for trigger in [event.trigger, *getattr(event, "triggers", [])] if trigger]
        if not event_triggers:
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event must declare at least one trigger.", field_name))
            continue
        if event.trigger_mode not in SUPPORTED_BEHAVIOR_TRIGGER_MODES:
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event '{event.trigger}' uses unsupported trigger_mode '{event.trigger_mode}'.", field_name))
        if event.trigger_mode in {"all", "sequence"} and len(event_triggers) < 2:
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event '{event.trigger}' trigger_mode '{event.trigger_mode}' requires at least two triggers.", field_name))
        if event.window_ticks < 0:
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event '{event.trigger}' window_ticks must be >= 0.", field_name))
        if event.trigger_mode == "sequence" and event.window_ticks == 0:
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event '{event.trigger}' sequence combos require window_ticks > 0.", field_name))
        for trigger in event_triggers:
            if trigger not in SUPPORTED_BEHAVIOR_TRIGGERS:
                issues.append(_issue(Severity.ERROR, f"{owner} behavior trigger '{trigger}' is unsupported.", field_name))
            elif trigger not in allowed_triggers:
                allowed = ", ".join(sorted(allowed_triggers))
                issues.append(_issue(Severity.ERROR, f"{owner} behavior trigger '{trigger}' is not valid here; allowed: {allowed}.", field_name))
        if not event.actions:
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event '{event.trigger}' must declare at least one action.", field_name))
        if event.cooldown_ticks < 0:
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event '{event.trigger}' cooldown_ticks must be >= 0.", field_name))
        if event.interval_ticks < 0:
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event '{event.trigger}' interval_ticks must be >= 0.", field_name))
        if event.resource_amount is not None and event.resource_amount < 0:
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event '{event.trigger}' resource_amount must be >= 0.", field_name))
        if event.resource is not None and not event.resource.strip():
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event '{event.trigger}' resource must not be empty.", field_name))
        if event.state_key is not None and not event.state_key.strip():
            issues.append(_issue(Severity.ERROR, f"{owner} behavior event '{event.trigger}' state_key must not be empty.", field_name))
        if event.trigger_mode != "any" and host_kind in {"item", "block", "sword", "ore"}:
            issues.append(
                _issue(
                    Severity.WARNING,
                    f"{owner} behavior event '{event.trigger}' uses trigger_mode '{event.trigger_mode}', which is captured in the shared behavior report but not compiled into legacy runtime hooks yet.",
                    field_name,
                )
            )

        for condition in event.conditions:
            if condition.condition_type not in SUPPORTED_BEHAVIOR_CONDITIONS:
                issues.append(_issue(Severity.ERROR, f"{owner} condition '{condition.condition_type}' is unsupported.", field_name))
            if condition.condition_type in {"health_below", "health_above"} and condition.threshold is None:
                issues.append(_issue(Severity.ERROR, f"{owner} condition '{condition.condition_type}' requires threshold.", field_name))
            if condition.condition_type == "random_chance":
                if condition.chance is None or not (0.0 <= condition.chance <= 1.0):
                    issues.append(_issue(Severity.ERROR, f"{owner} random_chance requires chance between 0 and 1.", field_name))
            if condition.condition_type in {"state_equals", "state_not_equals", "state_above", "state_below"}:
                if not condition.state_key:
                    issues.append(_issue(Severity.ERROR, f"{owner} condition '{condition.condition_type}' requires state_key.", field_name))
                if condition.state_value is None:
                    issues.append(_issue(Severity.ERROR, f"{owner} condition '{condition.condition_type}' requires state_value.", field_name))
            if condition.condition_type in {"resource_at_least", "resource_below"}:
                if not condition.resource:
                    issues.append(_issue(Severity.ERROR, f"{owner} condition '{condition.condition_type}' requires resource.", field_name))
                if condition.resource_amount is None:
                    issues.append(_issue(Severity.ERROR, f"{owner} condition '{condition.condition_type}' requires resource_amount.", field_name))
            if condition.condition_type == "cooldown_ready" and not condition.resource:
                issues.append(_issue(Severity.ERROR, f"{owner} condition 'cooldown_ready' requires resource.", field_name))
            if condition.window_ticks is not None and condition.window_ticks < 0:
                issues.append(_issue(Severity.ERROR, f"{owner} condition '{condition.condition_type}' window_ticks must be >= 0.", field_name))

        for action in event.actions:
            if action.action_type not in SUPPORTED_BEHAVIOR_ACTIONS:
                issues.append(_issue(Severity.ERROR, f"{owner} action '{action.action_type}' is unsupported.", field_name))
                continue
            if action.target not in {"self", "target", "attacker", "owner", "machine", "quest", "progression", "stage", "inventory"}:
                issues.append(_issue(Severity.ERROR, f"{owner} action '{action.action_type}' has unsupported target '{action.target}'.", field_name))
            if action.target == "target" and not any(trigger in {"hit_entity", "hurt", "attack"} for trigger in event_triggers):
                issues.append(_issue(Severity.ERROR, f"{owner} action target 'target' is only valid for combat events.", field_name))
            if action.action_type == "heal" and (action.amount is None or action.amount <= 0):
                issues.append(_issue(Severity.ERROR, f"{owner} heal action amount must be > 0.", field_name))
            if action.action_type == "apply_effect":
                if not action.effect or not RESOURCE_LOCATION_PATTERN.fullmatch(action.effect):
                    issues.append(_issue(Severity.ERROR, f"{owner} apply_effect action requires a valid effect resource location.", field_name))
                if action.duration_ticks is None or action.duration_ticks <= 0:
                    issues.append(_issue(Severity.ERROR, f"{owner} apply_effect action duration_ticks must be > 0.", field_name))
                if action.amplifier < 0:
                    issues.append(_issue(Severity.ERROR, f"{owner} apply_effect action amplifier must be >= 0.", field_name))
            if action.action_type == "ignite" and (action.seconds is None or action.seconds <= 0):
                issues.append(_issue(Severity.ERROR, f"{owner} ignite action seconds must be > 0.", field_name))
            if action.action_type == "consume_item":
                if action.count is not None and action.count <= 0:
                    issues.append(_issue(Severity.ERROR, f"{owner} consume_item action count must be > 0.", field_name))
                if host_kind in {"block", "ore"} and any(trigger == "block_use" for trigger in event_triggers):
                    issues.append(_issue(Severity.ERROR, f"{owner} block_use cannot consume the held item yet.", field_name))
            if action.action_type == "cooldown":
                if action.cooldown_ticks is None or action.cooldown_ticks < 0:
                    issues.append(_issue(Severity.ERROR, f"{owner} cooldown action cooldown_ticks must be >= 0.", field_name))
                if host_kind in {"block", "ore"} and any(trigger == "block_use" for trigger in event_triggers):
                    issues.append(_issue(Severity.ERROR, f"{owner} block_use cannot apply item cooldown yet.", field_name))
            if action.action_type == "spawn_particles" and action.count is not None and action.count <= 0:
                issues.append(_issue(Severity.ERROR, f"{owner} spawn_particles action count must be > 0.", field_name))
            if action.action_type == "play_sound":
                if action.volume is not None and action.volume < 0:
                    issues.append(_issue(Severity.ERROR, f"{owner} play_sound volume must be >= 0.", field_name))
                if action.pitch is not None and action.pitch < 0:
                    issues.append(_issue(Severity.ERROR, f"{owner} play_sound pitch must be >= 0.", field_name))
            if action.action_type in {"set_state", "increment_state", "clear_state"}:
                if not action.state_key:
                    issues.append(_issue(Severity.ERROR, f"{owner} {action.action_type} action requires state_key.", field_name))
                if action.action_type == "set_state" and action.state_value is None:
                    issues.append(_issue(Severity.ERROR, f"{owner} set_state action requires state_value.", field_name))
                if action.action_type == "increment_state" and action.state_delta is None and action.amount is None:
                    issues.append(_issue(Severity.ERROR, f"{owner} increment_state action requires state_delta or amount.", field_name))
            if action.action_type in {"consume_resource", "restore_resource", "transfer_resource"}:
                if not action.resource:
                    issues.append(_issue(Severity.ERROR, f"{owner} {action.action_type} action requires resource.", field_name))
                if action.resource_amount is None or action.resource_amount <= 0:
                    issues.append(_issue(Severity.ERROR, f"{owner} {action.action_type} action resource_amount must be > 0.", field_name))
            if action.action_type == "chain_event":
                if not action.chain_trigger:
                    issues.append(_issue(Severity.ERROR, f"{owner} chain_event action requires chain_trigger.", field_name))
                elif action.chain_trigger not in SUPPORTED_BEHAVIOR_TRIGGERS:
                    issues.append(_issue(Severity.ERROR, f"{owner} chain_event action uses unsupported chain_trigger '{action.chain_trigger}'.", field_name))
                if action.delay_ticks is not None and action.delay_ticks < 0:
                    issues.append(_issue(Severity.ERROR, f"{owner} chain_event delay_ticks must be >= 0.", field_name))
                if action.chain_window_ticks is not None and action.chain_window_ticks < 0:
                    issues.append(_issue(Severity.ERROR, f"{owner} chain_event chain_window_ticks must be >= 0.", field_name))
            if host_kind in {"item", "block", "sword", "ore"} and action.action_type not in {"heal", "apply_effect", "ignite", "consume_item", "cooldown", "spawn_particles", "play_sound"}:
                issues.append(
                    _issue(
                        Severity.WARNING,
                        f"{owner} action '{action.action_type}' is captured in the shared behavior report but not compiled into legacy runtime hooks yet.",
                        field_name,
                    )
                )


def _validate_recipe(recipe: RecipeSpec, issues: list[ValidationIssue]) -> None:
    if recipe.recipe_type not in {"shaped", "shapeless"}:
        issues.append(
            _issue(
                Severity.ERROR,
                f"Recipe '{recipe.identifier}' has unsupported recipe_type '{recipe.recipe_type}'.",
                "recipes",
            )
        )

    if not recipe.result:
        issues.append(_issue(Severity.ERROR, f"Recipe '{recipe.identifier}' is missing result.", "recipes"))

    if recipe.recipe_type == "shaped":
        if not recipe.pattern:
            issues.append(_issue(Severity.ERROR, f"Shaped recipe '{recipe.identifier}' is missing pattern.", "recipes"))
        if not recipe.keys:
            issues.append(_issue(Severity.ERROR, f"Shaped recipe '{recipe.identifier}' is missing keys.", "recipes"))

    if recipe.recipe_type == "shapeless" and not recipe.ingredients:
        issues.append(
            _issue(Severity.ERROR, f"Shapeless recipe '{recipe.identifier}' is missing ingredients.", "recipes")
        )


def _require_file(path: Path, warnings: list[str], message: str) -> None:
    if not path.exists():
        warnings.append(f"{message}: {path}")


def _load_json_dict(path: Path, warnings: list[str]) -> dict[str, str]:
    if not path.exists():
        warnings.append(f"Missing language file: {path}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"Invalid JSON in {path}: {exc}")
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _load_json_dict_generic(path: Path, warnings: list[str]) -> dict:
    if not path.exists():
        warnings.append(f"Missing JSON file: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"Invalid JSON in {path}: {exc}")
        return {}


def _require_lang_key(
    lang_data: dict[str, str],
    key: str,
    warnings: list[str],
    path: Path,
) -> None:
    if key not in lang_data:
        warnings.append(f"Missing lang key '{key}' in {path}")


def _entity_class_name(identifier: str) -> str:
    return "".join(part.capitalize() for part in identifier.split("_") if part) + "Entity"


def _entity_renderer_class_name(identifier: str) -> str:
    return "".join(part.capitalize() for part in identifier.split("_") if part) + "Renderer"


def _main_class_name(spec: ModSpec) -> str:
    class_name = "".join(part.capitalize() for part in spec.mod_id.split("_") if part)
    return class_name if class_name.endswith("Mod") else f"{class_name}Mod"


def _tool_tag_path(project: Path, tool_tier: str) -> Path | None:
    normalized = tool_tier.lower()
    if normalized in {"gold", "golden", "wood", "wooden"}:
        return None
    if normalized in {"diamond", "netherite"}:
        suffix = "diamond"
    elif normalized in {"iron", "copper"}:
        suffix = "iron"
    else:
        suffix = "stone"
    return project / "src" / "main" / "resources" / "data" / "minecraft" / "tags" / "block" / f"needs_{suffix}_tool.json"


def _validate_generation_summary(summary_path: Path, warnings: list[str]) -> None:
    if not summary_path.exists():
        return
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"Invalid JSON in {summary_path}: {exc}")
        return

    required_keys = {"features_count", "generated_files", "warnings", "fallbacks"}
    missing = sorted(required_keys - set(data.keys()))
    if missing:
        warnings.append(f"generation-summary.json is missing keys {missing}: {summary_path}")


def _quest_task_ids(quest: QuestSpec, spec: ModSpec) -> list[str]:
    if quest.tasks:
        return [task.identifier for task in quest.tasks]
    progression = next(
        (candidate for candidate in spec.progressions if candidate.identifier == quest.target_progression),
        None,
    )
    if progression is None:
        return []
    return [stage.identifier for stage in progression.stages]


def _reference_exists(reference: str, mod_id: str, known_local_ids: set[str]) -> bool:
    if ":" in reference:
        namespace, value = reference.split(":", 1)
        if namespace == mod_id:
            return value in known_local_ids
        return True
    return reference in known_local_ids


def _resource_or_tag(reference: str) -> bool:
    value = reference[1:] if reference.startswith("#") else reference
    return bool(RESOURCE_LOCATION_PATTERN.fullmatch(value))


def _validate_png(path: Path, warnings: list[str]) -> None:
    if not path.exists():
        return
    try:
        data = path.read_bytes()
    except OSError as exc:
        warnings.append(f"Failed to read texture {path}: {exc}")
        return
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        warnings.append(f"Texture is not a valid PNG: {path}")
        return
    try:
        width, height = struct.unpack(">II", data[16:24])
    except struct.error:
        warnings.append(f"Texture has invalid PNG header: {path}")
        return
    if (width, height) != (16, 16):
        warnings.append(f"Texture should be 16x16 but is {width}x{height}: {path}")
    try:
        alpha_nonzero = _count_nontransparent_pixels(data)
        if alpha_nonzero < 24:
            warnings.append(f"Texture may be too sparse and appear missing in-game ({alpha_nonzero} opaque pixels): {path}")
    except Exception:
        warnings.append(f"Texture PNG could not be fully decoded for validation: {path}")


def _count_nontransparent_pixels(data: bytes) -> int:
    cursor = 8
    compressed = bytearray()
    while cursor < len(data):
        length = struct.unpack(">I", data[cursor:cursor + 4])[0]
        cursor += 4
        chunk_type = data[cursor:cursor + 4]
        cursor += 4
        chunk_data = data[cursor:cursor + length]
        cursor += length + 4
        if chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        if chunk_type == b"IEND":
            break
    raw = zlib.decompress(bytes(compressed))
    opaque = 0
    row_length = 1 + 16 * 4
    for y in range(16):
        row = raw[y * row_length:(y + 1) * row_length]
        for x in range(16):
            alpha = row[1 + x * 4 + 3]
            if alpha:
                opaque += 1
    return opaque
