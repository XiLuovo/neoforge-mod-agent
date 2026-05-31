from __future__ import annotations


def get_modspec_schema() -> dict:
    block_kind_values = [
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
    ]
    behavior_trigger_values = [
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
    ]
    behavior_trigger_mode_values = ["any", "all", "sequence"]
    behavior_condition_types = [
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
    ]
    behavior_action_types = [
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
    ]
    feature_base = {
        "type": "object",
        "required": ["type", "id", "display_name_en_us"],
        "properties": {
            "type": {"type": "string"},
            "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "display_name_en_us": {"type": "string"},
            "display_name_zh_cn": {"type": "string"},
            "description": {"type": "string"},
        },
        "additionalProperties": False,
    }
    behavior_condition_schema = {
        "type": "object",
        "required": ["type"],
        "properties": {
            "type": {
                "type": "string",
                "enum": behavior_condition_types,
            },
            "threshold": {"type": "number"},
            "chance": {"type": "number", "minimum": 0, "maximum": 1},
            "target": {"type": "string", "enum": ["self", "target", "attacker", "owner", "machine", "quest", "progression", "stage", "inventory"]},
            "state_key": {"type": "string"},
            "state_value": {},
            "resource": {"type": "string"},
            "resource_amount": {"type": "number"},
            "window_ticks": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    }
    behavior_action_schema = {
        "type": "object",
        "required": ["type"],
        "properties": {
            "type": {
                "type": "string",
                "enum": behavior_action_types,
            },
            "target": {"type": "string", "enum": ["self", "target", "attacker", "owner", "machine", "quest", "progression", "stage", "inventory"]},
            "amount": {"type": "number"},
            "effect": {"type": "string"},
            "duration_ticks": {"type": "integer", "minimum": 1},
            "amplifier": {"type": "integer", "minimum": 0},
            "seconds": {"type": "integer", "minimum": 1},
            "count": {"type": "integer", "minimum": 1},
            "cooldown_ticks": {"type": "integer", "minimum": 0},
            "particle": {"type": "string"},
            "sound": {"type": "string"},
            "volume": {"type": "number", "minimum": 0},
            "pitch": {"type": "number", "minimum": 0},
            "state_key": {"type": "string"},
            "state_value": {},
            "state_delta": {"type": "number"},
            "resource": {"type": "string"},
            "resource_amount": {"type": "number"},
            "delay_ticks": {"type": "integer", "minimum": 0},
            "chain_trigger": {"type": "string", "enum": behavior_trigger_values},
            "chain_target": {"type": "string"},
            "chain_window_ticks": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    }
    behavior_event_schema = {
        "type": "object",
        "required": ["trigger", "actions"],
        "properties": {
            "trigger": {"type": "string", "enum": behavior_trigger_values},
            "triggers": {"type": "array", "items": {"type": "string", "enum": behavior_trigger_values}},
            "trigger_mode": {"type": "string", "enum": behavior_trigger_mode_values},
            "conditions": {"type": "array", "items": behavior_condition_schema},
            "actions": {"type": "array", "items": behavior_action_schema, "minItems": 1},
            "cooldown_ticks": {"type": "integer", "minimum": 0},
            "interval_ticks": {"type": "integer", "minimum": 0},
            "window_ticks": {"type": "integer", "minimum": 0},
            "state_key": {"type": "string"},
            "state_value": {},
            "resource": {"type": "string"},
            "resource_amount": {"type": "number"},
        },
        "additionalProperties": False,
    }
    behavior_schema = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["right_click_heal", "right_click_effect", "event_action"]},
            "amount": {"type": ["number", "null"]},
            "effect": {"type": ["string", "null"]},
            "duration_ticks": {"type": ["integer", "null"], "minimum": 1},
            "amplifier": {"type": "integer", "minimum": 0},
            "cooldown_ticks": {"type": "integer", "minimum": 0},
            "consume": {"type": "boolean"},
            "events": {"type": "array", "items": behavior_event_schema, "minItems": 1},
        },
        "required": ["type"],
        "additionalProperties": False,
    }

    item_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "item"},
            "behavior": behavior_schema,
        },
    }
    block_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "block"},
            "strength": {"type": "number"},
            "resistance": {"type": "number"},
            "sound": {"type": "string"},
            "requires_correct_tool": {"type": "boolean"},
            "tool_tier": {"type": "string", "enum": ["stone", "iron", "diamond", "netherite", "copper", "wood", "gold"]},
            "block_kind": {"type": "string", "enum": block_kind_values},
            "base_block": {"type": ["string", "null"]},
            "behavior": behavior_schema,
        },
    }
    machine_schema = {
        **block_schema,
        "properties": {
            **block_schema["properties"],
            "type": {"const": "machine"},
            "block_kind": {"const": "cube"},
            "machine_kind": {"type": "string", "enum": ["furnace", "compressor", "upgrade_table", "magic_altar", "storage"]},
            "inventory_slots": {"type": "integer", "minimum": 1, "maximum": 27},
            "input_slots": {"type": "integer", "minimum": 0, "maximum": 27},
            "output_slots": {"type": "integer", "minimum": 0, "maximum": 27},
            "energy_capacity": {"type": "integer", "minimum": 0},
            "energy_per_tick": {"type": "integer", "minimum": 0},
            "max_progress": {"type": "integer", "minimum": 1},
            "menu_title": {"type": "string"},
        },
    }
    entity_attribute_schema = {
        "type": "object",
        "properties": {
            "max_health": {"type": "number", "exclusiveMinimum": 0},
            "movement_speed": {"type": "number", "exclusiveMinimum": 0},
            "attack_damage": {"type": "number", "minimum": 0},
            "armor": {"type": "number", "minimum": 0},
            "follow_range": {"type": "number", "exclusiveMinimum": 0},
            "knockback_resistance": {"type": "number", "minimum": 0},
        },
        "additionalProperties": False,
    }
    entity_drop_schema = {
        "type": "object",
        "required": ["item"],
        "properties": {
            "item": {"type": "string"},
            "min_count": {"type": "integer", "minimum": 1},
            "max_count": {"type": "integer", "minimum": 1},
            "chance": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "additionalProperties": False,
    }
    entity_spawn_schema = {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean"},
            "biomes": {"type": "string"},
            "weight": {"type": "integer", "minimum": 1},
            "min_count": {"type": "integer", "minimum": 1},
            "max_count": {"type": "integer", "minimum": 1},
            "placement": {"type": "string", "enum": ["on_ground"]},
        },
        "additionalProperties": False,
    }
    entity_goal_schema = {
        "type": "object",
        "required": ["type"],
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "float",
                    "melee_attack",
                    "random_stroll",
                    "look_at_player",
                    "random_look_around",
                    "hurt_by_target",
                    "target_player",
                ],
            },
            "priority": {"type": "integer", "minimum": 0},
            "speed": {"type": "number", "exclusiveMinimum": 0},
            "target": {"type": "string"},
            "distance": {"type": "number", "exclusiveMinimum": 0},
        },
        "additionalProperties": False,
    }
    entity_attack_schema = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["none", "melee"]},
            "damage": {"type": ["number", "null"], "minimum": 0},
            "speed": {"type": "number", "exclusiveMinimum": 0},
        },
        "additionalProperties": False,
    }
    entity_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "entity"},
            "entity_kind": {"type": "string", "enum": ["monster", "creature", "pet", "boss", "npc", "ambient"]},
            "mob_kind": {"type": "string", "enum": ["monster", "creature", "pet", "boss", "npc", "ambient"]},
            "category": {"type": "string", "enum": ["monster", "creature", "pet", "boss", "npc", "ambient", "misc"]},
            "width": {"type": "number", "exclusiveMinimum": 0},
            "height": {"type": "number", "exclusiveMinimum": 0},
            "tracking_range": {"type": "integer", "minimum": 1},
            "update_interval": {"type": "integer", "minimum": 1},
            "xp_reward": {"type": "integer", "minimum": 0},
            "fire_immune": {"type": "boolean"},
            "attributes": entity_attribute_schema,
            "drops": {"type": "array", "items": entity_drop_schema},
            "spawn": entity_spawn_schema,
            "goals": {"type": "array", "items": entity_goal_schema},
            "attack": entity_attack_schema,
            "behavior": behavior_schema,
        },
    }
    dimension_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "dimension"},
            "dimension_type": {"type": "string", "enum": ["overworld_like", "nether_like", "end_like"]},
            "biome": {"type": "string"},
            "generator": {"type": "string", "enum": ["noise"]},
            "min_y": {"type": "integer", "minimum": -2032, "maximum": 2031},
            "height": {"type": "integer", "minimum": 16, "maximum": 4064},
            "logical_height": {"type": "integer", "minimum": 16, "maximum": 4064},
            "coordinate_scale": {"type": "number", "exclusiveMinimum": 0},
            "ambient_light": {"type": "number", "minimum": 0, "maximum": 1},
            "has_skylight": {"type": "boolean"},
            "has_ceiling": {"type": "boolean"},
            "ultrawarm": {"type": "boolean"},
            "natural": {"type": "boolean"},
            "bed_works": {"type": "boolean"},
            "respawn_anchor_works": {"type": "boolean"},
            "fixed_time": {"type": ["integer", "null"], "minimum": 0},
        },
    }
    biome_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "biome"},
            "temperature": {"type": "number"},
            "downfall": {"type": "number", "minimum": 0, "maximum": 1},
            "has_precipitation": {"type": "boolean"},
            "sky_color": {"type": "integer", "minimum": 0, "maximum": 16777215},
            "water_color": {"type": "integer", "minimum": 0, "maximum": 16777215},
            "water_fog_color": {"type": "integer", "minimum": 0, "maximum": 16777215},
            "fog_color": {"type": "integer", "minimum": 0, "maximum": 16777215},
            "grass_color": {"type": ["integer", "null"], "minimum": 0, "maximum": 16777215},
            "foliage_color": {"type": ["integer", "null"], "minimum": 0, "maximum": 16777215},
            "features": {"type": "array", "items": {"type": "string"}},
        },
    }
    world_feature_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "world_feature"},
            "feature_kind": {"type": "string", "enum": ["ore_vein"]},
            "target_block": {"type": "string"},
            "placed_block": {"type": "string"},
            "biomes": {"type": "string"},
            "step": {"type": "string", "enum": ["raw_generation", "lakes", "local_modifications", "underground_structures", "surface_structures", "strongholds", "underground_ores", "underground_decoration", "fluid_springs", "vegetal_decoration", "top_layer_modification"]},
            "vein_size": {"type": "integer", "minimum": 1},
            "veins_per_chunk": {"type": "integer", "minimum": 1},
            "min_y": {"type": "integer", "minimum": -2032, "maximum": 2031},
            "max_y": {"type": "integer", "minimum": -2032, "maximum": 2031},
            "discard_chance_on_air_exposure": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }
    structure_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "structure"},
            "structure_kind": {"type": "string", "enum": ["jigsaw"]},
            "biomes": {"type": "string"},
            "step": {"type": "string", "enum": ["surface_structures", "underground_structures"]},
            "terrain_adaptation": {"type": "string", "enum": ["none", "beard_thin", "beard_box", "bury", "encapsulate"]},
            "spacing": {"type": "integer", "minimum": 1},
            "separation": {"type": "integer", "minimum": 0},
            "salt": {"type": "integer", "minimum": 0},
            "size": {"type": "integer", "minimum": 1, "maximum": 7},
            "start_height": {"type": "integer", "minimum": -2032, "maximum": 2031},
            "loot_table": {"type": ["string", "null"]},
        },
    }
    loot_entry_schema = {
        "type": "object",
        "required": ["item"],
        "properties": {
            "item": {"type": "string"},
            "min_count": {"type": "integer", "minimum": 1},
            "max_count": {"type": "integer", "minimum": 1},
            "weight": {"type": "integer", "minimum": 1},
            "chance": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "additionalProperties": False,
    }
    loot_pool_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "loot_pool"},
            "table_kind": {"type": "string", "enum": ["chest"]},
            "rolls": {"type": "integer", "minimum": 1},
            "entries": {"type": "array", "items": loot_entry_schema, "minItems": 1},
        },
    }
    java_extension_method_schema = {
        "type": "object",
        "required": ["name", "return_type", "return_value", "explanation"],
        "properties": {
            "name": {"type": "string", "pattern": "^[a-z][A-Za-z0-9]*$"},
            "return_type": {"type": "string", "enum": ["String"]},
            "return_value": {"type": "string"},
            "explanation": {"type": "string"},
        },
        "additionalProperties": False,
    }
    java_extension_schema = {
        **feature_base,
        "required": ["type", "id", "display_name_en_us", "class_name", "purpose", "methods", "explanation"],
        "properties": {
            **feature_base["properties"],
            "type": {"const": "java_extension"},
            "class_name": {"type": "string", "pattern": "^[A-Z][A-Za-z0-9]*$"},
            "purpose": {"type": "string"},
            "methods": {"type": "array", "items": java_extension_method_schema, "minItems": 1},
            "allowed_imports": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "net.minecraft.core.BlockPos",
                        "net.minecraft.network.chat.Component",
                        "net.minecraft.resources.ResourceLocation",
                    ],
                },
            },
            "explanation": {"type": "string"},
        },
    }
    ore_schema = {
        **block_schema,
        "properties": {
            **block_schema["properties"],
            "type": {"const": "ore"},
            "block_kind": {"const": "cube"},
            "drop": {"type": "string"},
            "min_drop": {"type": "integer", "minimum": 1},
            "max_drop": {"type": "integer", "minimum": 1},
            "affected_by_fortune": {"type": "boolean"},
            "silk_touch_drops_self": {"type": "boolean"},
            "worldgen": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "dimension": {"type": "string", "enum": ["minecraft:overworld"]},
                    "min_y": {"type": "integer", "minimum": -64, "maximum": 320},
                    "max_y": {"type": "integer", "minimum": -64, "maximum": 320},
                    "vein_size": {"type": "integer", "minimum": 1},
                    "veins_per_chunk": {"type": "integer", "minimum": 1}
                },
                "required": ["enabled"],
                "additionalProperties": False
            },
        },
    }
    food_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "food"},
            "nutrition": {"type": "integer", "minimum": 0},
            "saturation": {"type": "number", "minimum": 0},
            "effects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["effect", "duration_ticks"],
                    "properties": {
                        "effect": {"type": "string"},
                        "duration_ticks": {"type": "integer", "minimum": 1},
                        "amplifier": {"type": "integer", "minimum": 0},
                        "probability": {"type": "number", "minimum": 0, "maximum": 1}
                    },
                    "additionalProperties": False
                }
            }
        },
    }
    sword_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "sword"},
            "attack_damage_bonus": {"type": "number"},
            "attack_speed": {"type": "number"},
            "tool_material": {"type": "string", "enum": ["wood", "stone", "copper", "iron", "diamond", "gold", "golden", "netherite", "ruby"]},
            "behavior": behavior_schema,
            "on_hit": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["ignite"]},
                    "seconds": {"type": "integer", "minimum": 1}
                },
                "required": ["type", "seconds"],
                "additionalProperties": False
            }
        },
    }
    tool_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "tool"},
            "tool_type": {"type": "string", "enum": ["pickaxe", "axe", "shovel", "hoe"]},
            "tool_material": {"type": "string", "enum": ["wood", "stone", "copper", "iron", "diamond", "gold", "golden", "netherite", "ruby"]},
            "attack_damage_bonus": {"type": "number"},
            "attack_speed": {"type": "number"},
        },
    }
    armor_schema = {
        **feature_base,
        "properties": {
            **feature_base["properties"],
            "type": {"const": "armor"},
            "armor_type": {"type": "string", "enum": ["helmet", "chestplate", "leggings", "boots"]},
            "armor_material": {"type": "string", "enum": ["leather", "chainmail", "chain", "copper", "iron", "diamond", "gold", "golden", "netherite", "ruby"]},
        },
    }
    recipe_schema = {
        "type": "object",
        "required": ["type", "id", "recipe_type", "result", "count"],
        "properties": {
            "type": {"const": "recipe"},
            "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "recipe_type": {"type": "string", "enum": ["shaped", "shapeless"]},
            "pattern": {
                "type": "array",
                "items": {"type": "string"},
            },
            "keys": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
            "ingredients": {
                "type": "array",
                "items": {"type": "string"},
            },
            "result": {"type": "string"},
            "count": {"type": "integer", "minimum": 1},
            "category": {"type": "string"},
            "group": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }
    progression_stage_schema = {
        "type": "object",
        "required": ["id", "type", "title"],
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "identifier": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "type": {
                "type": "string",
                "enum": [
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
            },
            "stage_type": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "requires": {"type": "array", "items": {"type": "string"}},
            "provides": {"type": "array", "items": {"type": "string"}},
            "unlocks": {"type": "array", "items": {"type": "string"}},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    }
    progression_link_schema = {
        "type": "object",
        "required": ["from", "to"],
        "properties": {
            "from": {"type": "string"},
            "from_stage": {"type": "string"},
            "to": {"type": "string"},
            "to_stage": {"type": "string"},
            "trigger": {"type": "string"},
            "requirement": {"type": "string"},
        },
        "additionalProperties": False,
    }
    progression_schema = {
        "type": "object",
        "required": ["type", "id", "title", "stages"],
        "properties": {
            "type": {"const": "progression"},
            "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "identifier": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "title": {"type": "string"},
            "display_name_en_us": {"type": "string"},
            "display_name": {"type": "string"},
            "summary": {"type": "string"},
            "description": {"type": "string"},
            "entry_stage": {"type": "string"},
            "end_stage": {"type": "string"},
            "stages": {"type": "array", "items": progression_stage_schema, "minItems": 1},
            "links": {"type": "array", "items": progression_link_schema},
            "behavior": behavior_schema,
        },
        "additionalProperties": False,
    }
    balance_plan_schema = {
        "type": "object",
        "required": ["type", "id", "title"],
        "properties": {
            "type": {"const": "balance_plan"},
            "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "identifier": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "title": {"type": "string"},
            "display_name_en_us": {"type": "string"},
            "display_name": {"type": "string"},
            "target_progression": {"type": "string"},
            "profile": {"type": "string", "enum": ["easy", "standard", "expert"]},
            "summary": {"type": "string"},
            "description": {"type": "string"},
        },
        "additionalProperties": False,
    }
    quest_task_schema = {
        "type": "object",
        "required": ["id", "title"],
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "identifier": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "title": {"type": "string"},
            "display_name_en_us": {"type": "string"},
            "display_name": {"type": "string"},
            "description": {"type": "string"},
            "task_type": {
                "type": "string",
                "enum": [
                    "obtain_item",
                    "craft_item",
                    "mine_block",
                    "use_machine",
                    "kill_entity",
                    "enter_dimension",
                    "visit_structure",
                    "milestone",
                ],
            },
            "type": {
                "type": "string",
                "enum": [
                    "obtain_item",
                    "craft_item",
                    "mine_block",
                    "use_machine",
                    "kill_entity",
                    "enter_dimension",
                    "visit_structure",
                    "milestone",
                ],
            },
            "target": {"type": "string"},
            "icon": {"type": "string"},
            "parent": {"type": "string"},
            "guide_text": {"type": "string"},
            "reward_xp": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    }
    quest_schema = {
        "type": "object",
        "required": ["type", "id", "title"],
        "properties": {
            "type": {"const": "quest"},
            "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "identifier": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "title": {"type": "string"},
            "display_name_en_us": {"type": "string"},
            "display_name": {"type": "string"},
            "summary": {"type": "string"},
            "description": {"type": "string"},
            "target_progression": {"type": "string"},
            "guidebook_id": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "category": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            "tasks": {"type": "array", "items": quest_task_schema},
            "behavior": behavior_schema,
        },
        "additionalProperties": False,
    }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "NeoForgeAgentModSpec",
        "type": "object",
        "required": ["mod_id", "mod_name", "package", "features"],
        "properties": {
            "domain": {"type": "string", "enum": ["minecraft.neoforge", "neoforge", "minecraft.modspec"]},
            "domain_spec_type": {"type": "string", "enum": ["ModSpec"]},
            "mod_id": {"type": "string", "pattern": "^[a-z][a-z0-9_]{1,63}$"},
            "mod_name": {"type": "string"},
            "display_name": {"type": "string"},
            "package": {"type": "string"},
            "package_name": {"type": "string"},
            "version": {"type": "string"},
            "description": {"type": "string"},
            "authors": {"type": "array", "items": {"type": "string"}},
            "license_name": {"type": "string"},
            "loader": {"type": "string"},
            "neo_version": {"type": "string"},
            "java_version": {"type": "integer"},
            "features": {
                "type": "array",
                "items": {
                    "oneOf": [item_schema, block_schema, machine_schema, entity_schema, dimension_schema, biome_schema, world_feature_schema, structure_schema, loot_pool_schema, java_extension_schema, ore_schema, food_schema, sword_schema, tool_schema, armor_schema, recipe_schema, progression_schema, balance_plan_schema, quest_schema]
                },
            },
            "items": {"type": "array", "items": item_schema},
            "blocks": {"type": "array", "items": block_schema},
            "machines": {"type": "array", "items": machine_schema},
            "entities": {"type": "array", "items": entity_schema},
            "dimensions": {"type": "array", "items": dimension_schema},
            "biomes": {"type": "array", "items": biome_schema},
            "world_features": {"type": "array", "items": world_feature_schema},
            "structures": {"type": "array", "items": structure_schema},
            "loot_pools": {"type": "array", "items": loot_pool_schema},
            "java_extensions": {"type": "array", "items": java_extension_schema},
            "ores": {"type": "array", "items": ore_schema},
            "foods": {"type": "array", "items": food_schema},
            "swords": {"type": "array", "items": sword_schema},
            "tools": {"type": "array", "items": tool_schema},
            "armors": {"type": "array", "items": armor_schema},
            "recipes": {"type": "array", "items": recipe_schema},
            "progressions": {"type": "array", "items": progression_schema},
            "balance_plans": {"type": "array", "items": balance_plan_schema},
            "quests": {"type": "array", "items": quest_schema},
        },
        "additionalProperties": False,
    }
