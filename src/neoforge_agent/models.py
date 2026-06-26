from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from .feature_catalog import definition_for_kind, iter_feature_kind_definitions


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class StepStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class BuildErrorKind(str, Enum):
    JAVA_COMPILE = "java_compile"
    MISSING_SYMBOL = "missing_symbol"
    BAD_IMPORT = "bad_import"
    GRADLE_CONFIG = "gradle_config"
    RESOURCE_JSON = "resource_json"
    CONSTRUCTOR_MISMATCH = "constructor_mismatch"
    INCOMPATIBLE_TYPES = "incompatible_types"
    DEPENDENCY_RESOLUTION = "dependency_resolution"
    DUPLICATE_CLASS = "duplicate_class"
    ENCODING = "encoding"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class BehaviorConditionSpec:
    condition_type: str
    threshold: float | None = None
    chance: float | None = None
    target: str = "self"
    state_key: str | None = None
    state_value: Any | None = None
    resource: str | None = None
    resource_amount: float | None = None
    window_ticks: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.condition_type}
        if self.threshold is not None:
            data["threshold"] = self.threshold
        if self.chance is not None:
            data["chance"] = self.chance
        if self.target != "self":
            data["target"] = self.target
        if self.state_key is not None:
            data["state_key"] = self.state_key
        if self.state_value is not None:
            data["state_value"] = self.state_value
        if self.resource is not None:
            data["resource"] = self.resource
        if self.resource_amount is not None:
            data["resource_amount"] = self.resource_amount
        if self.window_ticks is not None:
            data["window_ticks"] = self.window_ticks
        return data


@dataclass(slots=True)
class BehaviorActionSpec:
    action_type: str
    target: str = "self"
    amount: float | None = None
    effect: str | None = None
    duration_ticks: int | None = None
    amplifier: int = 0
    seconds: int | None = None
    count: int | None = None
    cooldown_ticks: int | None = None
    particle: str | None = None
    sound: str | None = None
    volume: float | None = None
    pitch: float | None = None
    state_key: str | None = None
    state_value: Any | None = None
    state_delta: float | None = None
    resource: str | None = None
    resource_amount: float | None = None
    delay_ticks: int | None = None
    chain_trigger: str | None = None
    chain_target: str = "self"
    chain_window_ticks: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.action_type,
            "target": self.target,
        }
        for key in (
            "amount",
            "effect",
            "duration_ticks",
            "amplifier",
            "seconds",
            "count",
            "cooldown_ticks",
            "particle",
            "sound",
            "volume",
            "pitch",
            "state_key",
            "state_value",
            "state_delta",
            "resource",
            "resource_amount",
            "delay_ticks",
            "chain_trigger",
            "chain_target",
            "chain_window_ticks",
        ):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data


@dataclass(slots=True)
class BehaviorEventSpec:
    trigger: str
    triggers: list[str] = field(default_factory=list)
    trigger_mode: str = "any"
    actions: list[BehaviorActionSpec] = field(default_factory=list)
    conditions: list[BehaviorConditionSpec] = field(default_factory=list)
    cooldown_ticks: int = 0
    interval_ticks: int = 0
    window_ticks: int = 0
    state_key: str | None = None
    state_value: Any | None = None
    resource: str | None = None
    resource_amount: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "trigger": self.trigger,
            "actions": [_serialize(action) for action in self.actions],
        }
        if self.triggers:
            data["triggers"] = list(self.triggers)
        if self.trigger_mode != "any":
            data["trigger_mode"] = self.trigger_mode
        if self.conditions:
            data["conditions"] = [_serialize(condition) for condition in self.conditions]
        if self.cooldown_ticks:
            data["cooldown_ticks"] = self.cooldown_ticks
        if self.interval_ticks:
            data["interval_ticks"] = self.interval_ticks
        if self.window_ticks:
            data["window_ticks"] = self.window_ticks
        if self.state_key is not None:
            data["state_key"] = self.state_key
        if self.state_value is not None:
            data["state_value"] = self.state_value
        if self.resource is not None:
            data["resource"] = self.resource
        if self.resource_amount is not None:
            data["resource_amount"] = self.resource_amount
        return data


@dataclass(slots=True)
class BehaviorSpec:
    behavior_type: str
    amount: float | None = None
    effect: str | None = None
    duration_ticks: int | None = None
    amplifier: int = 0
    cooldown_ticks: int = 0
    consume: bool = False
    events: list[BehaviorEventSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "type": self.behavior_type,
            "cooldown_ticks": self.cooldown_ticks,
            "consume": self.consume,
        }
        if self.events:
            data["events"] = [_serialize(event) for event in self.events]
        if self.amount is not None:
            data["amount"] = self.amount
        if self.effect is not None:
            data["effect"] = self.effect
        if self.duration_ticks is not None:
            data["duration_ticks"] = self.duration_ticks
        if self.amplifier is not None:
            data["amplifier"] = self.amplifier
        return data


ItemBehaviorSpec = BehaviorSpec


@dataclass(slots=True)
class FoodEffectSpec:
    effect: str
    duration_ticks: int
    amplifier: int = 0
    probability: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect": self.effect,
            "duration_ticks": self.duration_ticks,
            "amplifier": self.amplifier,
            "probability": self.probability,
        }


@dataclass(slots=True)
class OnHitBehaviorSpec:
    behavior_type: str
    seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.behavior_type,
            "seconds": self.seconds,
        }


@dataclass(slots=True)
class WorldgenSpec:
    enabled: bool = False
    dimension: str = "minecraft:overworld"
    min_y: int = -64
    max_y: int = 32
    vein_size: int = 6
    veins_per_chunk: int = 4

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "dimension": self.dimension,
            "min_y": self.min_y,
            "max_y": self.max_y,
            "vein_size": self.vein_size,
            "veins_per_chunk": self.veins_per_chunk,
        }


@dataclass(slots=True)
class ContentSpec:
    identifier: str
    display_name: str
    display_name_zh_cn: str = ""
    description: str = ""

    @property
    def feature_type(self) -> str:
        return "content"

    @property
    def display_name_en_us(self) -> str:
        return self.display_name

    def localized_name(self, locale: str) -> str:
        if locale == "zh_cn" and self.display_name_zh_cn:
            return self.display_name_zh_cn
        return self.display_name_en_us

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.feature_type,
            "id": self.identifier,
            "identifier": self.identifier,
            "display_name": self.display_name,
            "display_name_en_us": self.display_name_en_us,
            "display_name_zh_cn": self.display_name_zh_cn,
            "description": self.description,
        }


@dataclass(slots=True)
class ItemSpec(ContentSpec):
    behavior: ItemBehaviorSpec | None = None

    @property
    def feature_type(self) -> str:
        return "item"

    def to_dict(self) -> dict[str, Any]:
        data = ContentSpec.to_dict(self)
        if self.behavior is not None:
            data["behavior"] = self.behavior.to_dict()
        return data


@dataclass(slots=True)
class FoodSpec(ItemSpec):
    nutrition: int = 4
    saturation: float = 0.3
    effects: list[FoodEffectSpec] = field(default_factory=list)

    @property
    def feature_type(self) -> str:
        return "food"

    def to_dict(self) -> dict[str, Any]:
        data = ItemSpec.to_dict(self)
        data["nutrition"] = self.nutrition
        data["saturation"] = self.saturation
        data["effects"] = [_serialize(effect) for effect in self.effects]
        return data


@dataclass(slots=True)
class SwordSpec(ItemSpec):
    attack_damage_bonus: float = 4.0
    attack_speed: float = -2.4
    tool_material: str = "iron"
    on_hit: OnHitBehaviorSpec | None = None

    @property
    def feature_type(self) -> str:
        return "sword"

    def to_dict(self) -> dict[str, Any]:
        data = ItemSpec.to_dict(self)
        data["attack_damage_bonus"] = self.attack_damage_bonus
        data["attack_speed"] = self.attack_speed
        data["tool_material"] = self.tool_material
        if self.on_hit is not None:
            data["on_hit"] = self.on_hit.to_dict()
        return data


@dataclass(slots=True)
class ToolSpec(ItemSpec):
    tool_type: str = "pickaxe"
    tool_material: str = "iron"
    attack_damage_bonus: float = 1.0
    attack_speed: float = -2.8

    @property
    def feature_type(self) -> str:
        return "tool"

    def to_dict(self) -> dict[str, Any]:
        data = ItemSpec.to_dict(self)
        data["tool_type"] = self.tool_type
        data["tool_material"] = self.tool_material
        data["attack_damage_bonus"] = self.attack_damage_bonus
        data["attack_speed"] = self.attack_speed
        return data


@dataclass(slots=True)
class ArmorSpec(ItemSpec):
    armor_type: str = "helmet"
    armor_material: str = "iron"

    @property
    def feature_type(self) -> str:
        return "armor"

    def to_dict(self) -> dict[str, Any]:
        data = ItemSpec.to_dict(self)
        data["armor_type"] = self.armor_type
        data["armor_material"] = self.armor_material
        return data


@dataclass(slots=True)
class BlockSpec(ContentSpec):
    strength: float = 1.5
    resistance: float = 1.5
    sound: str = "stone"
    requires_correct_tool: bool = False
    tool_tier: str = "iron"
    block_kind: str = "cube"
    base_block: str | None = None
    behavior: ItemBehaviorSpec | None = None

    @property
    def feature_type(self) -> str:
        return "block"

    def to_dict(self) -> dict[str, Any]:
        data = ContentSpec.to_dict(self)
        data["strength"] = self.strength
        data["resistance"] = self.resistance
        data["sound"] = self.sound
        data["requires_correct_tool"] = self.requires_correct_tool
        data["tool_tier"] = self.tool_tier
        data["block_kind"] = self.block_kind
        if self.base_block is not None:
            data["base_block"] = self.base_block
        if self.behavior is not None:
            data["behavior"] = self.behavior.to_dict()
        return data


@dataclass(slots=True)
class MachineSpec(BlockSpec):
    machine_kind: str = "compressor"
    inventory_slots: int = 2
    input_slots: int = 1
    output_slots: int = 1
    energy_capacity: int = 10000
    energy_per_tick: int = 20
    max_progress: int = 100
    menu_title: str = ""

    @property
    def feature_type(self) -> str:
        return "machine"

    def to_dict(self) -> dict[str, Any]:
        data = BlockSpec.to_dict(self)
        data["machine_kind"] = self.machine_kind
        data["inventory_slots"] = self.inventory_slots
        data["input_slots"] = self.input_slots
        data["output_slots"] = self.output_slots
        data["energy_capacity"] = self.energy_capacity
        data["energy_per_tick"] = self.energy_per_tick
        data["max_progress"] = self.max_progress
        if self.menu_title:
            data["menu_title"] = self.menu_title
        return data


@dataclass(slots=True)
class EntityAttributeSpec:
    max_health: float = 20.0
    movement_speed: float = 0.25
    attack_damage: float = 3.0
    armor: float = 0.0
    follow_range: float = 24.0
    knockback_resistance: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_health": self.max_health,
            "movement_speed": self.movement_speed,
            "attack_damage": self.attack_damage,
            "armor": self.armor,
            "follow_range": self.follow_range,
            "knockback_resistance": self.knockback_resistance,
        }


@dataclass(slots=True)
class EntityDropSpec:
    item: str
    min_count: int = 1
    max_count: int = 1
    chance: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "item": self.item,
            "min_count": self.min_count,
            "max_count": self.max_count,
            "chance": self.chance,
        }


@dataclass(slots=True)
class EntitySpawnSpec:
    enabled: bool = True
    biomes: str = "#minecraft:is_overworld"
    weight: int = 80
    min_count: int = 1
    max_count: int = 3
    placement: str = "on_ground"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "biomes": self.biomes,
            "weight": self.weight,
            "min_count": self.min_count,
            "max_count": self.max_count,
            "placement": self.placement,
        }


@dataclass(slots=True)
class EntityGoalSpec:
    goal_type: str
    priority: int = 0
    speed: float | None = None
    target: str = "minecraft:player"
    distance: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.goal_type,
            "priority": self.priority,
            "target": self.target,
        }
        if self.speed is not None:
            data["speed"] = self.speed
        if self.distance is not None:
            data["distance"] = self.distance
        return data


@dataclass(slots=True)
class EntityAttackSpec:
    attack_type: str = "melee"
    damage: float | None = None
    speed: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.attack_type,
            "speed": self.speed,
        }
        if self.damage is not None:
            data["damage"] = self.damage
        return data


@dataclass(slots=True)
class EntitySpec(ContentSpec):
    entity_kind: str = "monster"
    category: str = "monster"
    width: float = 0.6
    height: float = 1.95
    tracking_range: int = 8
    update_interval: int = 3
    xp_reward: int = 5
    fire_immune: bool = False
    attributes: EntityAttributeSpec = field(default_factory=EntityAttributeSpec)
    drops: list[EntityDropSpec] = field(default_factory=list)
    spawn: EntitySpawnSpec | None = None
    goals: list[EntityGoalSpec] = field(default_factory=list)
    attack: EntityAttackSpec | None = None
    behavior: BehaviorSpec | None = None

    @property
    def feature_type(self) -> str:
        return "entity"

    def to_dict(self) -> dict[str, Any]:
        data = ContentSpec.to_dict(self)
        data["entity_kind"] = self.entity_kind
        data["category"] = self.category
        data["width"] = self.width
        data["height"] = self.height
        data["tracking_range"] = self.tracking_range
        data["update_interval"] = self.update_interval
        data["xp_reward"] = self.xp_reward
        data["fire_immune"] = self.fire_immune
        data["attributes"] = self.attributes.to_dict()
        data["drops"] = [_serialize(drop) for drop in self.drops]
        data["goals"] = [_serialize(goal) for goal in self.goals]
        if self.spawn is not None:
            data["spawn"] = self.spawn.to_dict()
        if self.attack is not None:
            data["attack"] = self.attack.to_dict()
        if self.behavior is not None:
            data["behavior"] = self.behavior.to_dict()
        return data


@dataclass(slots=True)
class WorldDimensionSpec(ContentSpec):
    dimension_type: str = "overworld_like"
    biome: str = "minecraft:plains"
    generator: str = "noise"
    min_y: int = -64
    height: int = 384
    logical_height: int = 384
    coordinate_scale: float = 1.0
    ambient_light: float = 0.0
    has_skylight: bool = True
    has_ceiling: bool = False
    ultrawarm: bool = False
    natural: bool = True
    bed_works: bool = True
    respawn_anchor_works: bool = False
    fixed_time: int | None = None

    @property
    def feature_type(self) -> str:
        return "dimension"

    def to_dict(self) -> dict[str, Any]:
        data = ContentSpec.to_dict(self)
        data.update(
            {
                "dimension_type": self.dimension_type,
                "biome": self.biome,
                "generator": self.generator,
                "min_y": self.min_y,
                "height": self.height,
                "logical_height": self.logical_height,
                "coordinate_scale": self.coordinate_scale,
                "ambient_light": self.ambient_light,
                "has_skylight": self.has_skylight,
                "has_ceiling": self.has_ceiling,
                "ultrawarm": self.ultrawarm,
                "natural": self.natural,
                "bed_works": self.bed_works,
                "respawn_anchor_works": self.respawn_anchor_works,
            }
        )
        if self.fixed_time is not None:
            data["fixed_time"] = self.fixed_time
        return data


@dataclass(slots=True)
class WorldBiomeSpec(ContentSpec):
    temperature: float = 0.8
    downfall: float = 0.4
    has_precipitation: bool = True
    sky_color: int = 7907327
    water_color: int = 4159204
    water_fog_color: int = 329011
    fog_color: int = 12638463
    grass_color: int | None = None
    foliage_color: int | None = None
    features: list[str] = field(default_factory=list)

    @property
    def feature_type(self) -> str:
        return "biome"

    def to_dict(self) -> dict[str, Any]:
        data = ContentSpec.to_dict(self)
        data.update(
            {
                "temperature": self.temperature,
                "downfall": self.downfall,
                "has_precipitation": self.has_precipitation,
                "sky_color": self.sky_color,
                "water_color": self.water_color,
                "water_fog_color": self.water_fog_color,
                "fog_color": self.fog_color,
                "features": list(self.features),
            }
        )
        if self.grass_color is not None:
            data["grass_color"] = self.grass_color
        if self.foliage_color is not None:
            data["foliage_color"] = self.foliage_color
        return data


@dataclass(slots=True)
class WorldFeatureSpec(ContentSpec):
    feature_kind: str = "ore_vein"
    target_block: str = "minecraft:stone_ore_replaceables"
    placed_block: str = "minecraft:diamond_ore"
    biomes: str = "#minecraft:is_overworld"
    step: str = "underground_ores"
    vein_size: int = 6
    veins_per_chunk: int = 4
    min_y: int = -64
    max_y: int = 32
    discard_chance_on_air_exposure: float = 0.0

    @property
    def feature_type(self) -> str:
        return "world_feature"

    def to_dict(self) -> dict[str, Any]:
        data = ContentSpec.to_dict(self)
        data.update(
            {
                "feature_kind": self.feature_kind,
                "target_block": self.target_block,
                "placed_block": self.placed_block,
                "biomes": self.biomes,
                "step": self.step,
                "vein_size": self.vein_size,
                "veins_per_chunk": self.veins_per_chunk,
                "min_y": self.min_y,
                "max_y": self.max_y,
                "discard_chance_on_air_exposure": self.discard_chance_on_air_exposure,
            }
        )
        return data


@dataclass(slots=True)
class WorldStructureSpec(ContentSpec):
    structure_kind: str = "jigsaw"
    biomes: str = "#minecraft:is_overworld"
    step: str = "surface_structures"
    terrain_adaptation: str = "beard_thin"
    spacing: int = 32
    separation: int = 8
    salt: int = 14357617
    size: int = 1
    start_height: int = 0
    loot_table: str | None = None

    @property
    def feature_type(self) -> str:
        return "structure"

    def to_dict(self) -> dict[str, Any]:
        data = ContentSpec.to_dict(self)
        data.update(
            {
                "structure_kind": self.structure_kind,
                "biomes": self.biomes,
                "step": self.step,
                "terrain_adaptation": self.terrain_adaptation,
                "spacing": self.spacing,
                "separation": self.separation,
                "salt": self.salt,
                "size": self.size,
                "start_height": self.start_height,
            }
        )
        if self.loot_table is not None:
            data["loot_table"] = self.loot_table
        return data


@dataclass(slots=True)
class LootEntrySpec:
    item: str
    min_count: int = 1
    max_count: int = 1
    weight: int = 1
    chance: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "item": self.item,
            "min_count": self.min_count,
            "max_count": self.max_count,
            "weight": self.weight,
            "chance": self.chance,
        }


@dataclass(slots=True)
class LootPoolSpec(ContentSpec):
    table_kind: str = "chest"
    rolls: int = 1
    entries: list[LootEntrySpec] = field(default_factory=list)

    @property
    def feature_type(self) -> str:
        return "loot_pool"

    def to_dict(self) -> dict[str, Any]:
        data = ContentSpec.to_dict(self)
        data.update(
            {
                "table_kind": self.table_kind,
                "rolls": self.rolls,
                "entries": [_serialize(entry) for entry in self.entries],
            }
        )
        return data


@dataclass(slots=True)
class JavaExtensionMethodSpec:
    name: str
    return_value: str
    return_type: str = "String"
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "return_type": self.return_type,
            "return_value": self.return_value,
            "explanation": self.explanation,
        }


@dataclass(slots=True)
class JavaExtensionSpec(ContentSpec):
    class_name: str = ""
    purpose: str = ""
    methods: list[JavaExtensionMethodSpec] = field(default_factory=list)
    allowed_imports: list[str] = field(default_factory=list)
    explanation: str = ""

    @property
    def feature_type(self) -> str:
        return "java_extension"

    def to_dict(self) -> dict[str, Any]:
        data = ContentSpec.to_dict(self)
        data.update(
            {
                "class_name": self.class_name,
                "purpose": self.purpose,
                "methods": [_serialize(method) for method in self.methods],
                "allowed_imports": list(self.allowed_imports),
                "explanation": self.explanation,
            }
        )
        return data


@dataclass(slots=True)
class OreSpec(BlockSpec):
    drop: str | None = None
    min_drop: int = 1
    max_drop: int = 1
    affected_by_fortune: bool = False
    silk_touch_drops_self: bool = False
    worldgen: WorldgenSpec | None = None

    @property
    def feature_type(self) -> str:
        return "ore"

    def to_dict(self) -> dict[str, Any]:
        data = BlockSpec.to_dict(self)
        data["drop"] = self.drop
        data["min_drop"] = self.min_drop
        data["max_drop"] = self.max_drop
        data["affected_by_fortune"] = self.affected_by_fortune
        data["silk_touch_drops_self"] = self.silk_touch_drops_self
        if self.worldgen is not None:
            data["worldgen"] = self.worldgen.to_dict()
        return data


@dataclass(slots=True)
class RecipeSpec:
    identifier: str
    recipe_type: str
    result: str
    count: int = 1
    pattern: list[str] = field(default_factory=list)
    keys: dict[str, str] = field(default_factory=dict)
    ingredients: list[str] = field(default_factory=list)
    category: str = "misc"
    group: str | None = None

    @property
    def feature_type(self) -> str:
        return "recipe"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.feature_type,
            "id": self.identifier,
            "identifier": self.identifier,
            "recipe_type": self.recipe_type,
            "pattern": list(self.pattern),
            "keys": dict(self.keys),
            "ingredients": list(self.ingredients),
            "result": self.result,
            "count": self.count,
            "category": self.category,
            "group": self.group,
        }


@dataclass(slots=True)
class ProgressionStageSpec:
    identifier: str
    stage_type: str
    title: str
    description: str = ""
    requires: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    unlocks: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "identifier": self.identifier,
            "type": self.stage_type,
            "stage_type": self.stage_type,
            "title": self.title,
            "description": self.description,
            "requires": list(self.requires),
            "provides": list(self.provides),
            "unlocks": list(self.unlocks),
            "evidence": list(self.evidence),
        }


@dataclass(slots=True)
class ProgressionLinkSpec:
    from_stage: str
    to_stage: str
    trigger: str = ""
    requirement: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_stage,
            "from_stage": self.from_stage,
            "to": self.to_stage,
            "to_stage": self.to_stage,
            "trigger": self.trigger,
            "requirement": self.requirement,
        }


@dataclass(slots=True)
class ProgressionSpec:
    identifier: str
    title: str
    summary: str = ""
    entry_stage: str = ""
    end_stage: str = ""
    stages: list[ProgressionStageSpec] = field(default_factory=list)
    links: list[ProgressionLinkSpec] = field(default_factory=list)
    behavior: BehaviorSpec | None = None

    @property
    def feature_type(self) -> str:
        return "progression"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.feature_type,
            "id": self.identifier,
            "identifier": self.identifier,
            "title": self.title,
            "summary": self.summary,
            "entry_stage": self.entry_stage,
            "end_stage": self.end_stage,
            "stages": [_serialize(stage) for stage in self.stages],
            "links": [_serialize(link) for link in self.links],
            **({"behavior": self.behavior.to_dict()} if self.behavior is not None else {}),
        }


@dataclass(slots=True)
class BalancePlanSpec:
    identifier: str
    title: str
    target_progression: str = ""
    profile: str = "standard"
    summary: str = ""

    @property
    def feature_type(self) -> str:
        return "balance_plan"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.feature_type,
            "id": self.identifier,
            "identifier": self.identifier,
            "title": self.title,
            "target_progression": self.target_progression,
            "profile": self.profile,
            "summary": self.summary,
        }


@dataclass(slots=True)
class QuestTaskSpec:
    identifier: str
    title: str
    description: str = ""
    task_type: str = "milestone"
    target: str = ""
    icon: str = ""
    parent: str = ""
    guide_text: str = ""
    reward_xp: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "identifier": self.identifier,
            "type": self.task_type,
            "task_type": self.task_type,
            "title": self.title,
            "description": self.description,
            "target": self.target,
            "icon": self.icon,
            "parent": self.parent,
            "guide_text": self.guide_text,
            "reward_xp": self.reward_xp,
        }


@dataclass(slots=True)
class QuestSpec:
    identifier: str
    title: str
    summary: str = ""
    target_progression: str = ""
    guidebook_id: str = "guidebook"
    category: str = "getting_started"
    tasks: list[QuestTaskSpec] = field(default_factory=list)
    behavior: BehaviorSpec | None = None

    @property
    def feature_type(self) -> str:
        return "quest"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.feature_type,
            "id": self.identifier,
            "identifier": self.identifier,
            "title": self.title,
            "summary": self.summary,
            "target_progression": self.target_progression,
            "guidebook_id": self.guidebook_id,
            "category": self.category,
            "tasks": [_serialize(task) for task in self.tasks],
            **({"behavior": self.behavior.to_dict()} if self.behavior is not None else {}),
        }


@dataclass(slots=True)
class ModSpec:
    raw_request: str
    mod_id: str
    display_name: str
    package_name: str
    version: str = "0.1.0"
    description: str = ""
    authors: list[str] = field(default_factory=list)
    license_name: str = "All Rights Reserved"
    loader: str = "neoforge"
    neo_version: str = "26.1"
    java_version: int = 25
    items: list[ItemSpec] = field(default_factory=list)
    blocks: list[BlockSpec] = field(default_factory=list)
    machines: list[MachineSpec] = field(default_factory=list)
    entities: list[EntitySpec] = field(default_factory=list)
    dimensions: list[WorldDimensionSpec] = field(default_factory=list)
    biomes: list[WorldBiomeSpec] = field(default_factory=list)
    world_features: list[WorldFeatureSpec] = field(default_factory=list)
    structures: list[WorldStructureSpec] = field(default_factory=list)
    loot_pools: list[LootPoolSpec] = field(default_factory=list)
    java_extensions: list[JavaExtensionSpec] = field(default_factory=list)
    ores: list[OreSpec] = field(default_factory=list)
    foods: list[FoodSpec] = field(default_factory=list)
    swords: list[SwordSpec] = field(default_factory=list)
    tools: list[ToolSpec] = field(default_factory=list)
    armors: list[ArmorSpec] = field(default_factory=list)
    recipes: list[RecipeSpec] = field(default_factory=list)
    progressions: list[ProgressionSpec] = field(default_factory=list)
    balance_plans: list[BalancePlanSpec] = field(default_factory=list)
    quests: list[QuestSpec] = field(default_factory=list)
    requested_features: list[str] = field(default_factory=list)
    extra_notes: list[str] = field(default_factory=list)

    @property
    def domain_id(self) -> str:
        return "minecraft.neoforge"

    @property
    def domain_spec_type(self) -> str:
        return "ModSpec"

    def all_item_like(self) -> list[ContentSpec]:
        return [*self.items, *self.foods, *self.swords, *self.tools, *self.armors]

    def all_block_like(self) -> list[BlockSpec]:
        return [*self.blocks, *self.machines, *self.ores]

    def all_content(self) -> list[ContentSpec]:
        return [*self.all_item_like(), *self.all_block_like()]

    def all_world_like(self) -> list[ContentSpec]:
        return [*self.dimensions, *self.biomes, *self.world_features, *self.structures, *self.loot_pools]

    def to_dict(self) -> dict[str, Any]:
        data = {
            "domain": self.domain_id,
            "domain_spec_type": self.domain_spec_type,
            "raw_request": self.raw_request,
            "mod_id": self.mod_id,
            "mod_name": self.display_name,
            "display_name": self.display_name,
            "package": self.package_name,
            "package_name": self.package_name,
            "version": self.version,
            "description": self.description,
            "authors": list(self.authors),
            "license_name": self.license_name,
            "loader": self.loader,
            "neo_version": self.neo_version,
            "java_version": self.java_version,
        }
        for definition in iter_feature_kind_definitions():
            data[definition.collection_name] = [
                _serialize(feature)
                for feature in getattr(self, definition.collection_name)
            ]
        data["features"] = [_serialize(feature) for feature in self.iter_features()]
        data["requested_features"] = list(self.requested_features)
        data["extra_notes"] = list(self.extra_notes)
        return data

    def iter_features(self) -> Iterable[object]:
        features: list[object] = []
        for definition in iter_feature_kind_definitions():
            features.extend(getattr(self, definition.collection_name))
        return features

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModSpec":
        definitions = iter_feature_kind_definitions()
        typed_by_collection: dict[str, list[dict[str, Any]]] = {
            definition.collection_name: []
            for definition in definitions
        }
        features = data.get("features", [])
        if features:
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                feature_type = str(feature.get("type", "")).lower()
                try:
                    definition = definition_for_kind(feature_type)
                except KeyError:
                    continue
                typed_by_collection[definition.collection_name].append(feature)
            for collection_name in ("progressions", "balance_plans", "quests"):
                _append_legacy_collection_entries(typed_by_collection[collection_name], data.get(collection_name, []))
        else:
            for definition in definitions:
                typed_by_collection[definition.collection_name] = [
                    entry
                    for entry in data.get(definition.collection_name, [])
                    if isinstance(entry, dict)
                ]

        parsed_collections = {
            definition.collection_name: [
                _parse_feature_by_key(definition.parser_key, entry)
                for entry in typed_by_collection[definition.collection_name]
            ]
            for definition in definitions
        }

        return cls(
            raw_request=str(data.get("raw_request", data.get("description", ""))),
            mod_id=str(data.get("mod_id", data.get("id", "generated_mod"))),
            display_name=str(data.get("display_name", data.get("mod_name", "Generated Mod"))),
            package_name=str(
                data.get("package_name", data.get("package", data.get("mod_group_id", "com.generated.generated_mod")))
            ),
            version=str(data.get("version", data.get("mod_version", "0.1.0"))),
            description=str(data.get("description", "")),
            authors=[str(author) for author in data.get("authors", [])],
            license_name=str(data.get("license_name", data.get("mod_license", "All Rights Reserved"))),
            loader=str(data.get("loader", "neoforge")),
            neo_version=str(data.get("neo_version", "26.1")),
            java_version=int(data.get("java_version", 25)),
            **parsed_collections,
            requested_features=[str(item) for item in data.get("requested_features", [])],
            extra_notes=[str(item) for item in data.get("extra_notes", [])],
        )


def _append_legacy_collection_entries(target: list[dict[str, Any]], legacy_entries: Any) -> None:
    seen_ids = {
        str(entry.get("id", entry.get("identifier", "")))
        for entry in target
        if isinstance(entry, dict)
    }
    entries = legacy_entries if isinstance(legacy_entries, list) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        identifier = str(entry.get("id", entry.get("identifier", "")))
        if identifier in seen_ids:
            continue
        target.append(entry)
        seen_ids.add(identifier)


def _content_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "identifier": str(data.get("id", data.get("identifier", ""))),
        "display_name": str(data.get("display_name_en_us", data.get("display_name", ""))),
        "display_name_zh_cn": str(data.get("display_name_zh_cn", "")),
        "description": str(data.get("description", "")),
    }


def _item_from_dict(data: dict[str, Any]) -> ItemSpec:
    fields = _content_fields(data)
    behavior = data.get("behavior")
    if isinstance(behavior, dict):
        fields["behavior"] = _item_behavior_from_dict(behavior)
    return ItemSpec(**fields)


def _food_from_dict(data: dict[str, Any]) -> FoodSpec:
    fields = _content_fields(data)
    fields["nutrition"] = int(data.get("nutrition", 4))
    fields["saturation"] = float(data.get("saturation", 0.3))
    fields["effects"] = [_food_effect_from_dict(effect) for effect in data.get("effects", []) if isinstance(effect, dict)]
    return FoodSpec(**fields)


def _sword_from_dict(data: dict[str, Any]) -> SwordSpec:
    fields = _content_fields(data)
    fields["attack_damage_bonus"] = float(data.get("attack_damage_bonus", 4))
    fields["attack_speed"] = float(data.get("attack_speed", -2.4))
    fields["tool_material"] = str(data.get("tool_material", "iron"))
    if isinstance(data.get("behavior"), dict):
        fields["behavior"] = _item_behavior_from_dict(data["behavior"])
    if isinstance(data.get("on_hit"), dict):
        fields["on_hit"] = _on_hit_behavior_from_dict(data["on_hit"])
    return SwordSpec(**fields)


def _tool_from_dict(data: dict[str, Any]) -> ToolSpec:
    fields = _content_fields(data)
    fields["tool_type"] = str(data.get("tool_type", "pickaxe"))
    fields["tool_material"] = str(data.get("tool_material", "iron"))
    fields["attack_damage_bonus"] = float(data.get("attack_damage_bonus", 1.0))
    fields["attack_speed"] = float(data.get("attack_speed", -2.8))
    return ToolSpec(**fields)


def _armor_from_dict(data: dict[str, Any]) -> ArmorSpec:
    fields = _content_fields(data)
    fields["armor_type"] = str(data.get("armor_type", "helmet"))
    fields["armor_material"] = str(data.get("armor_material", "iron"))
    return ArmorSpec(**fields)


def _block_from_dict(data: dict[str, Any]) -> BlockSpec:
    fields = _content_fields(data)
    fields["strength"] = float(data.get("strength", 1.5))
    fields["resistance"] = float(data.get("resistance", 1.5))
    fields["sound"] = str(data.get("sound", "stone"))
    fields["requires_correct_tool"] = bool(data.get("requires_correct_tool", False))
    fields["tool_tier"] = str(data.get("tool_tier", "iron"))
    fields["block_kind"] = str(data.get("block_kind", "cube"))
    fields["base_block"] = str(data["base_block"]) if data.get("base_block") is not None else None
    if isinstance(data.get("behavior"), dict):
        fields["behavior"] = _item_behavior_from_dict(data["behavior"])
    return BlockSpec(**fields)


def _machine_from_dict(data: dict[str, Any]) -> MachineSpec:
    fields = _content_fields(data)
    fields["strength"] = float(data.get("strength", 4.0))
    fields["resistance"] = float(data.get("resistance", 6.0))
    fields["sound"] = str(data.get("sound", "metal"))
    fields["requires_correct_tool"] = bool(data.get("requires_correct_tool", True))
    fields["tool_tier"] = str(data.get("tool_tier", "iron"))
    fields["block_kind"] = str(data.get("block_kind", "cube"))
    fields["base_block"] = str(data["base_block"]) if data.get("base_block") is not None else None
    fields["machine_kind"] = str(data.get("machine_kind", "compressor"))
    fields["inventory_slots"] = int(data.get("inventory_slots", 2))
    fields["input_slots"] = int(data.get("input_slots", 1))
    fields["output_slots"] = int(data.get("output_slots", 1))
    fields["energy_capacity"] = int(data.get("energy_capacity", 10000))
    fields["energy_per_tick"] = int(data.get("energy_per_tick", 20))
    fields["max_progress"] = int(data.get("max_progress", 100))
    fields["menu_title"] = str(data.get("menu_title", ""))
    if isinstance(data.get("behavior"), dict):
        fields["behavior"] = _item_behavior_from_dict(data["behavior"])
    return MachineSpec(**fields)


def _entity_from_dict(data: dict[str, Any]) -> EntitySpec:
    fields = _content_fields(data)
    fields["entity_kind"] = str(data.get("entity_kind", data.get("mob_kind", "monster")))
    fields["category"] = str(data.get("category", "monster"))
    fields["width"] = float(data.get("width", 0.6))
    fields["height"] = float(data.get("height", 1.95))
    fields["tracking_range"] = int(data.get("tracking_range", 8))
    fields["update_interval"] = int(data.get("update_interval", 3))
    fields["xp_reward"] = int(data.get("xp_reward", 5))
    fields["fire_immune"] = bool(data.get("fire_immune", False))
    fields["attributes"] = (
        _entity_attributes_from_dict(data["attributes"])
        if isinstance(data.get("attributes"), dict)
        else EntityAttributeSpec()
    )
    fields["drops"] = [
        _entity_drop_from_dict(drop)
        for drop in data.get("drops", [])
        if isinstance(drop, dict)
    ]
    fields["spawn"] = (
        _entity_spawn_from_dict(data["spawn"])
        if isinstance(data.get("spawn"), dict)
        else None
    )
    fields["goals"] = [
        _entity_goal_from_dict(goal)
        for goal in data.get("goals", [])
        if isinstance(goal, dict)
    ]
    fields["attack"] = (
        _entity_attack_from_dict(data["attack"])
        if isinstance(data.get("attack"), dict)
        else None
    )
    fields["behavior"] = _item_behavior_from_dict(data["behavior"]) if isinstance(data.get("behavior"), dict) else None
    return EntitySpec(**fields)


def _dimension_from_dict(data: dict[str, Any]) -> WorldDimensionSpec:
    fields = _content_fields(data)
    fields["dimension_type"] = str(data.get("dimension_type", "overworld_like"))
    fields["biome"] = str(data.get("biome", "minecraft:plains"))
    fields["generator"] = str(data.get("generator", "noise"))
    fields["min_y"] = int(data.get("min_y", -64))
    fields["height"] = int(data.get("height", 384))
    fields["logical_height"] = int(data.get("logical_height", fields["height"]))
    fields["coordinate_scale"] = float(data.get("coordinate_scale", 1.0))
    fields["ambient_light"] = float(data.get("ambient_light", 0.0))
    fields["has_skylight"] = bool(data.get("has_skylight", True))
    fields["has_ceiling"] = bool(data.get("has_ceiling", False))
    fields["ultrawarm"] = bool(data.get("ultrawarm", False))
    fields["natural"] = bool(data.get("natural", True))
    fields["bed_works"] = bool(data.get("bed_works", True))
    fields["respawn_anchor_works"] = bool(data.get("respawn_anchor_works", False))
    fields["fixed_time"] = int(data["fixed_time"]) if data.get("fixed_time") is not None else None
    return WorldDimensionSpec(**fields)


def _biome_from_dict(data: dict[str, Any]) -> WorldBiomeSpec:
    fields = _content_fields(data)
    fields["temperature"] = float(data.get("temperature", 0.8))
    fields["downfall"] = float(data.get("downfall", 0.4))
    fields["has_precipitation"] = bool(data.get("has_precipitation", True))
    fields["sky_color"] = int(data.get("sky_color", 7907327))
    fields["water_color"] = int(data.get("water_color", 4159204))
    fields["water_fog_color"] = int(data.get("water_fog_color", 329011))
    fields["fog_color"] = int(data.get("fog_color", 12638463))
    fields["grass_color"] = int(data["grass_color"]) if data.get("grass_color") is not None else None
    fields["foliage_color"] = int(data["foliage_color"]) if data.get("foliage_color") is not None else None
    fields["features"] = [str(feature) for feature in data.get("features", [])]
    return WorldBiomeSpec(**fields)


def _world_feature_from_dict(data: dict[str, Any]) -> WorldFeatureSpec:
    fields = _content_fields(data)
    fields["feature_kind"] = str(data.get("feature_kind", "ore_vein"))
    fields["target_block"] = str(data.get("target_block", "minecraft:stone_ore_replaceables"))
    fields["placed_block"] = str(data.get("placed_block", data.get("block", "minecraft:diamond_ore")))
    fields["biomes"] = str(data.get("biomes", "#minecraft:is_overworld"))
    fields["step"] = str(data.get("step", "underground_ores"))
    fields["vein_size"] = int(data.get("vein_size", 6))
    fields["veins_per_chunk"] = int(data.get("veins_per_chunk", data.get("count", 4)))
    fields["min_y"] = int(data.get("min_y", -64))
    fields["max_y"] = int(data.get("max_y", 32))
    fields["discard_chance_on_air_exposure"] = float(data.get("discard_chance_on_air_exposure", 0.0))
    return WorldFeatureSpec(**fields)


def _structure_from_dict(data: dict[str, Any]) -> WorldStructureSpec:
    fields = _content_fields(data)
    fields["structure_kind"] = str(data.get("structure_kind", "jigsaw"))
    fields["biomes"] = str(data.get("biomes", "#minecraft:is_overworld"))
    fields["step"] = str(data.get("step", "surface_structures"))
    fields["terrain_adaptation"] = str(data.get("terrain_adaptation", "beard_thin"))
    fields["spacing"] = int(data.get("spacing", 32))
    fields["separation"] = int(data.get("separation", 8))
    fields["salt"] = int(data.get("salt", 14357617))
    fields["size"] = int(data.get("size", 1))
    fields["start_height"] = int(data.get("start_height", 0))
    fields["loot_table"] = str(data["loot_table"]) if data.get("loot_table") is not None else None
    return WorldStructureSpec(**fields)


def _loot_pool_from_dict(data: dict[str, Any]) -> LootPoolSpec:
    fields = _content_fields(data)
    fields["table_kind"] = str(data.get("table_kind", "chest"))
    fields["rolls"] = int(data.get("rolls", 1))
    fields["entries"] = [
        _loot_entry_from_dict(entry)
        for entry in data.get("entries", [])
        if isinstance(entry, dict)
    ]
    return LootPoolSpec(**fields)


def _java_extension_from_dict(data: dict[str, Any]) -> JavaExtensionSpec:
    class_name = str(data.get("class_name", "")).strip()
    identifier = str(data.get("id", data.get("identifier", ""))).strip()
    display_name = str(data.get("display_name_en_us", data.get("display_name", ""))).strip()
    if not identifier and class_name:
        identifier = _class_name_to_identifier(class_name)
    if not display_name:
        display_name = class_name or "Java Extension"
    return JavaExtensionSpec(
        identifier=identifier,
        display_name=display_name,
        display_name_zh_cn=str(data.get("display_name_zh_cn", "")),
        description=str(data.get("description", "")),
        class_name=class_name,
        purpose=str(data.get("purpose", "")),
        methods=[
            _java_extension_method_from_dict(method)
            for method in data.get("methods", [])
            if isinstance(method, dict)
        ],
        allowed_imports=[str(import_line) for import_line in data.get("allowed_imports", [])],
        explanation=str(data.get("explanation", "")),
    )


def _java_extension_method_from_dict(data: dict[str, Any]) -> JavaExtensionMethodSpec:
    return JavaExtensionMethodSpec(
        name=str(data.get("name", "")),
        return_type=str(data.get("return_type", "String")),
        return_value=str(data.get("return_value", "")),
        explanation=str(data.get("explanation", "")),
    )


def _class_name_to_identifier(class_name: str) -> str:
    value = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value).strip("_")
    return value or "java_extension"


def _loot_entry_from_dict(data: dict[str, Any]) -> LootEntrySpec:
    return LootEntrySpec(
        item=str(data.get("item", "minecraft:air")),
        min_count=int(data.get("min_count", 1)),
        max_count=int(data.get("max_count", 1)),
        weight=int(data.get("weight", 1)),
        chance=float(data.get("chance", 1.0)),
    )


def _ore_from_dict(data: dict[str, Any]) -> OreSpec:
    return OreSpec(
        identifier=str(data.get("id", data.get("identifier", ""))),
        display_name=str(data.get("display_name_en_us", data.get("display_name", ""))),
        display_name_zh_cn=str(data.get("display_name_zh_cn", "")),
        description=str(data.get("description", "")),
        strength=float(data.get("strength", 3.0)),
        resistance=float(data.get("resistance", 3.0)),
        sound=str(data.get("sound", "stone")),
        requires_correct_tool=bool(data.get("requires_correct_tool", False)),
        tool_tier=str(data.get("tool_tier", "iron")),
        block_kind=str(data.get("block_kind", "cube")),
        base_block=str(data["base_block"]) if data.get("base_block") is not None else None,
        drop=str(data.get("drop", "")) or None,
        min_drop=int(data.get("min_drop", 1)),
        max_drop=int(data.get("max_drop", 1)),
        affected_by_fortune=bool(data.get("affected_by_fortune", False)),
        silk_touch_drops_self=bool(data.get("silk_touch_drops_self", False)),
        worldgen=_worldgen_from_dict(data["worldgen"]) if isinstance(data.get("worldgen"), dict) else None,
        behavior=_item_behavior_from_dict(data["behavior"]) if isinstance(data.get("behavior"), dict) else None,
    )


def _recipe_from_dict(data: dict[str, Any]) -> RecipeSpec:
    return RecipeSpec(
        identifier=str(data.get("id", data.get("identifier", ""))),
        recipe_type=str(data.get("recipe_type", "shaped")),
        pattern=[str(row) for row in data.get("pattern", [])],
        keys={str(key): _resource_reference_from_value(value) for key, value in data.get("keys", {}).items()},
        ingredients=[_resource_reference_from_value(item) for item in data.get("ingredients", [])],
        result=_resource_reference_from_value(data.get("result", "")),
        count=int(data.get("count", 1)),
        category=str(data.get("category", "misc")),
        group=str(data["group"]) if data.get("group") is not None else None,
    )


def _resource_reference_from_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("item", "id", "result"):
            candidate = value.get(key)
            if candidate is not None and str(candidate).strip():
                return str(candidate)
    return str(value)


def _progression_from_dict(data: dict[str, Any]) -> ProgressionSpec:
    return ProgressionSpec(
        identifier=str(data.get("id", data.get("identifier", ""))),
        title=str(data.get("title", data.get("display_name_en_us", data.get("display_name", "")))),
        summary=str(data.get("summary", data.get("description", ""))),
        entry_stage=str(data.get("entry_stage", "")),
        end_stage=str(data.get("end_stage", "")),
        stages=[
            _progression_stage_from_dict(stage)
            for stage in data.get("stages", [])
            if isinstance(stage, dict)
        ],
        links=[
            _progression_link_from_dict(link)
            for link in data.get("links", [])
            if isinstance(link, dict)
        ],
        behavior=_item_behavior_from_dict(data["behavior"]) if isinstance(data.get("behavior"), dict) else None,
    )


def _balance_plan_from_dict(data: dict[str, Any]) -> BalancePlanSpec:
    return BalancePlanSpec(
        identifier=str(data.get("id", data.get("identifier", ""))),
        title=str(data.get("title", data.get("display_name_en_us", data.get("display_name", "")))),
        target_progression=str(data.get("target_progression", "")),
        profile=str(data.get("profile", "standard")),
        summary=str(data.get("summary", data.get("description", ""))),
    )


def _quest_from_dict(data: dict[str, Any]) -> QuestSpec:
    return QuestSpec(
        identifier=str(data.get("id", data.get("identifier", ""))),
        title=str(data.get("title", data.get("display_name_en_us", data.get("display_name", "")))),
        summary=str(data.get("summary", data.get("description", ""))),
        target_progression=str(data.get("target_progression", "")),
        guidebook_id=str(data.get("guidebook_id", "guidebook")),
        category=str(data.get("category", "getting_started")),
        tasks=[
            _quest_task_from_dict(task)
            for task in data.get("tasks", [])
            if isinstance(task, dict)
        ],
        behavior=_item_behavior_from_dict(data["behavior"]) if isinstance(data.get("behavior"), dict) else None,
    )


def _quest_task_from_dict(data: dict[str, Any]) -> QuestTaskSpec:
    return QuestTaskSpec(
        identifier=str(data.get("id", data.get("identifier", ""))),
        title=str(data.get("title", data.get("display_name_en_us", data.get("display_name", "")))),
        description=str(data.get("description", "")),
        task_type=str(data.get("task_type", data.get("type", "milestone"))),
        target=str(data.get("target", "")),
        icon=str(data.get("icon", "")),
        parent=str(data.get("parent", "")),
        guide_text=str(data.get("guide_text", "")),
        reward_xp=int(data.get("reward_xp", 0)),
    )


def _progression_stage_from_dict(data: dict[str, Any]) -> ProgressionStageSpec:
    return ProgressionStageSpec(
        identifier=str(data.get("id", data.get("identifier", ""))),
        stage_type=str(data.get("stage_type", data.get("type", ""))),
        title=str(data.get("title", data.get("display_name_en_us", data.get("display_name", "")))),
        description=str(data.get("description", "")),
        requires=[str(item) for item in data.get("requires", [])],
        provides=[str(item) for item in data.get("provides", [])],
        unlocks=[str(item) for item in data.get("unlocks", [])],
        evidence=[str(item) for item in data.get("evidence", [])],
    )


def _progression_link_from_dict(data: dict[str, Any]) -> ProgressionLinkSpec:
    return ProgressionLinkSpec(
        from_stage=str(data.get("from_stage", data.get("from", ""))),
        to_stage=str(data.get("to_stage", data.get("to", ""))),
        trigger=str(data.get("trigger", "")),
        requirement=str(data.get("requirement", "")),
    )


def _item_behavior_from_dict(data: dict[str, Any]) -> BehaviorSpec:
    events = [
        _behavior_event_from_dict(event)
        for event in data.get("events", [])
        if isinstance(event, dict)
    ]
    return BehaviorSpec(
        behavior_type=str(data.get("type", "event_action" if events else "")),
        amount=float(data["amount"]) if data.get("amount") is not None else None,
        effect=str(data["effect"]) if data.get("effect") is not None else None,
        duration_ticks=int(data["duration_ticks"]) if data.get("duration_ticks") is not None else None,
        amplifier=int(data.get("amplifier", 0)),
        cooldown_ticks=int(data.get("cooldown_ticks", 0)),
        consume=bool(data.get("consume", False)),
        events=events,
    )


def _behavior_event_from_dict(data: dict[str, Any]) -> BehaviorEventSpec:
    trigger = str(data.get("trigger", data.get("event", "")))
    triggers = [str(trigger_value) for trigger_value in data.get("triggers", []) if str(trigger_value).strip()]
    return BehaviorEventSpec(
        trigger=trigger or (triggers[0] if triggers else ""),
        triggers=triggers,
        trigger_mode=str(data.get("trigger_mode", "any")),
        actions=[
            _behavior_action_from_dict(action)
            for action in data.get("actions", [])
            if isinstance(action, dict)
        ],
        conditions=[
            _behavior_condition_from_dict(condition)
            for condition in data.get("conditions", [])
            if isinstance(condition, dict)
        ],
        cooldown_ticks=int(data.get("cooldown_ticks", 0)),
        interval_ticks=int(data.get("interval_ticks", 0)),
        window_ticks=int(data.get("window_ticks", 0)),
        state_key=str(data.get("state_key")) if data.get("state_key") is not None else None,
        state_value=data.get("state_value"),
        resource=str(data.get("resource")) if data.get("resource") is not None else None,
        resource_amount=float(data["resource_amount"]) if data.get("resource_amount") is not None else None,
    )


def _behavior_action_from_dict(data: dict[str, Any]) -> BehaviorActionSpec:
    return BehaviorActionSpec(
        action_type=str(data.get("type", data.get("action", ""))),
        target=str(data.get("target", "self")),
        amount=float(data["amount"]) if data.get("amount") is not None else None,
        effect=str(data["effect"]) if data.get("effect") is not None else None,
        duration_ticks=int(data["duration_ticks"]) if data.get("duration_ticks") is not None else None,
        amplifier=int(data.get("amplifier", 0)),
        seconds=int(data["seconds"]) if data.get("seconds") is not None else None,
        count=int(data["count"]) if data.get("count") is not None else None,
        cooldown_ticks=int(data["cooldown_ticks"]) if data.get("cooldown_ticks") is not None else None,
        particle=str(data["particle"]) if data.get("particle") is not None else None,
        sound=str(data["sound"]) if data.get("sound") is not None else None,
        volume=float(data["volume"]) if data.get("volume") is not None else None,
        pitch=float(data["pitch"]) if data.get("pitch") is not None else None,
        state_key=str(data.get("state_key")) if data.get("state_key") is not None else None,
        state_value=data.get("state_value"),
        state_delta=float(data["state_delta"]) if data.get("state_delta") is not None else None,
        resource=str(data.get("resource")) if data.get("resource") is not None else None,
        resource_amount=float(data["resource_amount"]) if data.get("resource_amount") is not None else None,
        delay_ticks=int(data["delay_ticks"]) if data.get("delay_ticks") is not None else None,
        chain_trigger=str(data.get("chain_trigger")) if data.get("chain_trigger") is not None else None,
        chain_target=str(data.get("chain_target", "self")),
        chain_window_ticks=int(data["chain_window_ticks"]) if data.get("chain_window_ticks") is not None else None,
    )


def _behavior_condition_from_dict(data: dict[str, Any]) -> BehaviorConditionSpec:
    return BehaviorConditionSpec(
        condition_type=str(data.get("type", data.get("condition", ""))),
        threshold=float(data["threshold"]) if data.get("threshold") is not None else None,
        chance=float(data["chance"]) if data.get("chance") is not None else None,
        target=str(data.get("target", "self")),
        state_key=str(data.get("state_key")) if data.get("state_key") is not None else None,
        state_value=data.get("state_value"),
        resource=str(data.get("resource")) if data.get("resource") is not None else None,
        resource_amount=float(data["resource_amount"]) if data.get("resource_amount") is not None else None,
        window_ticks=int(data["window_ticks"]) if data.get("window_ticks") is not None else None,
    )


def _entity_attributes_from_dict(data: dict[str, Any]) -> EntityAttributeSpec:
    return EntityAttributeSpec(
        max_health=float(data.get("max_health", 20.0)),
        movement_speed=float(data.get("movement_speed", 0.25)),
        attack_damage=float(data.get("attack_damage", 3.0)),
        armor=float(data.get("armor", 0.0)),
        follow_range=float(data.get("follow_range", 24.0)),
        knockback_resistance=float(data.get("knockback_resistance", 0.0)),
    )


def _entity_drop_from_dict(data: dict[str, Any]) -> EntityDropSpec:
    return EntityDropSpec(
        item=str(data.get("item", "minecraft:emerald")),
        min_count=int(data.get("min_count", 1)),
        max_count=int(data.get("max_count", 1)),
        chance=float(data.get("chance", 1.0)),
    )


def _entity_spawn_from_dict(data: dict[str, Any]) -> EntitySpawnSpec:
    return EntitySpawnSpec(
        enabled=bool(data.get("enabled", True)),
        biomes=str(data.get("biomes", "#minecraft:is_overworld")),
        weight=int(data.get("weight", 80)),
        min_count=int(data.get("min_count", 1)),
        max_count=int(data.get("max_count", 3)),
        placement=str(data.get("placement", "on_ground")),
    )


def _entity_goal_from_dict(data: dict[str, Any]) -> EntityGoalSpec:
    return EntityGoalSpec(
        goal_type=str(data.get("type", data.get("goal", ""))),
        priority=int(data.get("priority", 0)),
        speed=float(data["speed"]) if data.get("speed") is not None else None,
        target=str(data.get("target", "minecraft:player")),
        distance=float(data["distance"]) if data.get("distance") is not None else None,
    )


def _entity_attack_from_dict(data: dict[str, Any]) -> EntityAttackSpec:
    return EntityAttackSpec(
        attack_type=str(data.get("type", data.get("attack_type", "melee"))),
        damage=float(data["damage"]) if data.get("damage") is not None else None,
        speed=float(data.get("speed", 1.0)),
    )


def _food_effect_from_dict(data: dict[str, Any]) -> FoodEffectSpec:
    return FoodEffectSpec(
        effect=str(data.get("effect", "")),
        duration_ticks=int(data.get("duration_ticks", 0)),
        amplifier=int(data.get("amplifier", 0)),
        probability=float(data.get("probability", 1.0)),
    )


def _on_hit_behavior_from_dict(data: dict[str, Any]) -> OnHitBehaviorSpec:
    return OnHitBehaviorSpec(
        behavior_type=str(data.get("type", "")),
        seconds=int(data.get("seconds", 0)),
    )


def _worldgen_from_dict(data: dict[str, Any]) -> WorldgenSpec:
    return WorldgenSpec(
        enabled=bool(data.get("enabled", False)),
        dimension=str(data.get("dimension", "minecraft:overworld")),
        min_y=int(data.get("min_y", -64)),
        max_y=int(data.get("max_y", 32)),
        vein_size=int(data.get("vein_size", 6)),
        veins_per_chunk=int(data.get("veins_per_chunk", 4)),
    )


_FEATURE_PARSERS = {
    "item": _item_from_dict,
    "block": _block_from_dict,
    "machine": _machine_from_dict,
    "entity": _entity_from_dict,
    "dimension": _dimension_from_dict,
    "biome": _biome_from_dict,
    "world_feature": _world_feature_from_dict,
    "structure": _structure_from_dict,
    "loot_pool": _loot_pool_from_dict,
    "java_extension": _java_extension_from_dict,
    "ore": _ore_from_dict,
    "food": _food_from_dict,
    "sword": _sword_from_dict,
    "tool": _tool_from_dict,
    "armor": _armor_from_dict,
    "recipe": _recipe_from_dict,
    "progression": _progression_from_dict,
    "balance_plan": _balance_plan_from_dict,
    "quest": _quest_from_dict,
}


def _parse_feature_by_key(parser_key: str, data: dict[str, Any]) -> object:
    try:
        parser = _FEATURE_PARSERS[parser_key]
    except KeyError as exc:
        raise KeyError(f"Unknown Feature Kind parser key: {parser_key}") from exc
    return parser(data)


@dataclass(slots=True)
class RequestOverrides:
    mod_id: str | None = None
    display_name: str | None = None
    package_name: str | None = None
    version: str | None = None
    authors: list[str] = field(default_factory=list)
    license_name: str | None = None
    description: str | None = None


@dataclass(slots=True)
class ValidationIssue:
    severity: Severity
    message: str
    field_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "message": self.message,
            "field_name": self.field_name,
        }


@dataclass(slots=True)
class BuildIssue:
    kind: BuildErrorKind
    message: str
    file: str | None = None
    line: int | None = None
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "suggestion": self.suggestion,
        }


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == Severity.WARNING]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == Severity.INFO]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": [_serialize(issue) for issue in self.issues],
        }


@dataclass(slots=True)
class PlanStep:
    name: str
    status: StepStatus = StepStatus.PENDING
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass(slots=True)
class BuildResult:
    attempted: bool = False
    success: bool | None = None
    command: list[str] = field(default_factory=list)
    return_code: int | None = None
    jar_path: Path | None = None
    log_path: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    debug_context_path: Path | None = None
    fix_request_path: Path | None = None
    suspected_errors_path: Path | None = None
    issues: list[BuildIssue] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "success": self.success,
            "command": list(self.command),
            "return_code": self.return_code,
            "exit_code": self.return_code,
            "jar_path": _serialize(self.jar_path),
            "log_path": _serialize(self.log_path),
            "stdout_path": _serialize(self.stdout_path),
            "stderr_path": _serialize(self.stderr_path),
            "debug_context_path": _serialize(self.debug_context_path),
            "fix_request_path": _serialize(self.fix_request_path),
            "suspected_errors_path": _serialize(self.suspected_errors_path),
            "issues": [_serialize(issue) for issue in self.issues],
            "summary": self.summary,
        }


@dataclass(slots=True)
class GenerationResult:
    spec: ModSpec
    workspace_dir: Path
    steps: list[PlanStep]
    validation: ValidationReport
    build: BuildResult = field(default_factory=BuildResult)
    metadata_path: Path | None = None
    placeholder_note_path: Path | None = None
    manual_test_checklist_path: Path | None = None
    pending_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fallbacks: list[str] = field(default_factory=list)
    generated_files: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        if not self.validation.is_valid:
            return False
        if self.build.attempted and self.build.success is False:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "succeeded": self.succeeded,
            "spec": _serialize(self.spec),
            "workspace_dir": _serialize(self.workspace_dir),
            "steps": [_serialize(step) for step in self.steps],
            "validation": _serialize(self.validation),
            "build": _serialize(self.build),
            "metadata_path": _serialize(self.metadata_path),
            "placeholder_note_path": _serialize(self.placeholder_note_path),
            "manual_test_checklist_path": _serialize(self.manual_test_checklist_path),
            "features_count": {
                "items": len(self.spec.items),
                "blocks": len(self.spec.blocks),
                "machines": len(self.spec.machines),
                "entities": len(self.spec.entities),
                "dimensions": len(self.spec.dimensions),
                "biomes": len(self.spec.biomes),
                "world_features": len(self.spec.world_features),
                "structures": len(self.spec.structures),
                "loot_pools": len(self.spec.loot_pools),
                "java_extensions": len(self.spec.java_extensions),
                "ores": len(self.spec.ores),
                "foods": len(self.spec.foods),
                "swords": len(self.spec.swords),
                "tools": len(self.spec.tools),
                "armors": len(self.spec.armors),
                "recipes": len(self.spec.recipes),
                "progressions": len(self.spec.progressions),
                "balance_plans": len(self.spec.balance_plans),
                "quests": len(self.spec.quests),
            },
            "pending_actions": list(self.pending_actions),
            "warnings": list(self.warnings),
            "fallbacks": list(self.fallbacks),
            "generated_files": list(self.generated_files),
        }
