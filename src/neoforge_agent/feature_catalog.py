from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FeatureMergePolicy(str, Enum):
    REPLACE_BY_IDENTIFIER = "replace_by_identifier"
    MERGE_PROGRESSION = "merge_progression"
    REPLACE_RECIPE_BY_IDENTIFIER = "replace_recipe_by_identifier"


@dataclass(frozen=True, slots=True)
class FeatureKindDefinition:
    kind: str
    collection_name: str
    parser_key: str
    merge_policy: FeatureMergePolicy = FeatureMergePolicy.REPLACE_BY_IDENTIFIER


FEATURE_KIND_DEFINITIONS: tuple[FeatureKindDefinition, ...] = (
    FeatureKindDefinition("item", "items", "item"),
    FeatureKindDefinition("block", "blocks", "block"),
    FeatureKindDefinition("machine", "machines", "machine"),
    FeatureKindDefinition("entity", "entities", "entity"),
    FeatureKindDefinition("dimension", "dimensions", "dimension"),
    FeatureKindDefinition("biome", "biomes", "biome"),
    FeatureKindDefinition("world_feature", "world_features", "world_feature"),
    FeatureKindDefinition("structure", "structures", "structure"),
    FeatureKindDefinition("loot_pool", "loot_pools", "loot_pool"),
    FeatureKindDefinition("java_extension", "java_extensions", "java_extension"),
    FeatureKindDefinition("ore", "ores", "ore"),
    FeatureKindDefinition("food", "foods", "food"),
    FeatureKindDefinition("sword", "swords", "sword"),
    FeatureKindDefinition("tool", "tools", "tool"),
    FeatureKindDefinition("armor", "armors", "armor"),
    FeatureKindDefinition("recipe", "recipes", "recipe", FeatureMergePolicy.REPLACE_RECIPE_BY_IDENTIFIER),
    FeatureKindDefinition("progression", "progressions", "progression", FeatureMergePolicy.MERGE_PROGRESSION),
    FeatureKindDefinition("balance_plan", "balance_plans", "balance_plan"),
    FeatureKindDefinition("quest", "quests", "quest"),
)

_DEFINITIONS_BY_KIND = {definition.kind: definition for definition in FEATURE_KIND_DEFINITIONS}
_DEFINITIONS_BY_COLLECTION = {definition.collection_name: definition for definition in FEATURE_KIND_DEFINITIONS}


def iter_feature_kind_definitions() -> tuple[FeatureKindDefinition, ...]:
    return FEATURE_KIND_DEFINITIONS


def definition_for_kind(kind: str) -> FeatureKindDefinition:
    normalized = str(kind or "").strip().lower()
    try:
        return _DEFINITIONS_BY_KIND[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown Feature Kind: {kind}") from exc


def definition_for_collection(collection_name: str) -> FeatureKindDefinition:
    normalized = str(collection_name or "").strip()
    try:
        return _DEFINITIONS_BY_COLLECTION[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown Feature Kind collection: {collection_name}") from exc

