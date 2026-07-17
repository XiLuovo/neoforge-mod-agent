from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import LootEntrySpec, LootPoolSpec, ModSpec, OreSpec, WorldBiomeSpec, WorldDimensionSpec, WorldFeatureSpec, WorldStructureSpec
from .tools import ensure_directory, write_json


class WorldgenGenerator:
    def generate(self, resources_dir: Path, spec: ModSpec) -> list[Path]:
        generated: list[Path] = []
        for dimension in spec.dimensions:
            generated.extend(self._generate_dimension(resources_dir, spec, dimension))
        for biome in spec.biomes:
            generated.append(self._generate_biome(resources_dir, spec, biome))
        for feature in spec.world_features:
            generated.extend(self._generate_world_feature(resources_dir, spec, feature))
        for structure in spec.structures:
            generated.extend(self._generate_structure(resources_dir, spec, structure))
        for loot_pool in spec.loot_pools:
            generated.append(self._generate_loot_pool(resources_dir, spec, loot_pool))
        for ore in spec.ores:
            if ore.worldgen is None or not ore.worldgen.enabled:
                continue
            generated.extend(self._generate_ore_worldgen(resources_dir, spec, ore))
        return generated

    def _generate_dimension(self, resources_dir: Path, spec: ModSpec, dimension: WorldDimensionSpec) -> list[Path]:
        dimension_type_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "dimension_type")
        dimension_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "dimension")
        return [
            write_json(dimension_type_dir / f"{dimension.identifier}.json", self._dimension_type_payload(dimension)),
            write_json(dimension_dir / f"{dimension.identifier}.json", self._dimension_payload(spec, dimension)),
        ]

    def _dimension_type_payload(self, dimension: WorldDimensionSpec) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ultrawarm": dimension.ultrawarm,
            "natural": dimension.natural,
            "coordinate_scale": dimension.coordinate_scale,
            "piglin_safe": False,
            "respawn_anchor_works": dimension.respawn_anchor_works,
            "bed_works": dimension.bed_works,
            "has_raids": True,
            "has_skylight": dimension.has_skylight,
            "has_ceiling": dimension.has_ceiling,
            "has_ender_dragon_fight": False,
            "ambient_light": dimension.ambient_light,
            "logical_height": dimension.logical_height,
            "min_y": dimension.min_y,
            "height": dimension.height,
            "infiniburn": "#minecraft:infiniburn_overworld",
            "effects": "minecraft:overworld",
            "monster_spawn_light_level": {
                "type": "minecraft:uniform",
                "min_inclusive": 0,
                "max_inclusive": 7,
            },
            "monster_spawn_block_light_limit": 0,
        }
        if dimension.fixed_time is not None:
            payload["fixed_time"] = dimension.fixed_time
        return payload

    def _dimension_payload(self, spec: ModSpec, dimension: WorldDimensionSpec) -> dict[str, Any]:
        return {
            "type": f"{spec.mod_id}:{dimension.identifier}",
            "generator": {
                "type": "minecraft:noise",
                "settings": "minecraft:overworld",
                "biome_source": {
                    "type": "minecraft:fixed",
                    "biome": self._world_reference(spec, dimension.biome),
                },
            },
        }

    def _generate_biome(self, resources_dir: Path, spec: ModSpec, biome: WorldBiomeSpec) -> Path:
        biome_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "worldgen" / "biome")
        return write_json(biome_dir / f"{biome.identifier}.json", self._biome_payload(spec, biome))

    def _biome_payload(self, spec: ModSpec, biome: WorldBiomeSpec) -> dict[str, Any]:
        effects: dict[str, Any] = {
            "sky_color": biome.sky_color,
            "water_color": biome.water_color,
            "water_fog_color": biome.water_fog_color,
            "fog_color": biome.fog_color,
        }
        if biome.grass_color is not None:
            effects["grass_color"] = biome.grass_color
        if biome.foliage_color is not None:
            effects["foliage_color"] = biome.foliage_color
        return {
            "temperature": biome.temperature,
            "downfall": biome.downfall,
            "has_precipitation": biome.has_precipitation,
            "effects": effects,
            "spawners": {},
            "spawn_costs": {},
            "carvers": [],
            "features": self._biome_features(spec, biome),
        }

    def _biome_features(self, spec: ModSpec, biome: WorldBiomeSpec) -> list[list[str]]:
        steps = [[] for _ in range(12)]
        if biome.features:
            steps[4] = [self._world_reference(spec, feature) for feature in biome.features]
        return steps

    def _generate_world_feature(self, resources_dir: Path, spec: ModSpec, feature: WorldFeatureSpec) -> list[Path]:
        configured_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "worldgen" / "configured_feature")
        placed_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "worldgen" / "placed_feature")
        biome_modifier_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "neoforge" / "biome_modifier")
        return [
            write_json(configured_dir / f"{feature.identifier}.json", self._world_feature_configured_payload(feature)),
            write_json(placed_dir / f"{feature.identifier}.json", self._world_feature_placed_payload(spec, feature)),
            write_json(biome_modifier_dir / f"add_{feature.identifier}.json", self._world_feature_biome_modifier_payload(spec, feature)),
        ]

    def _world_feature_configured_payload(self, feature: WorldFeatureSpec) -> dict[str, Any]:
        if feature.feature_kind == "ore_vein":
            return {
                "type": "minecraft:ore",
                "config": {
                    "discard_chance_on_air_exposure": feature.discard_chance_on_air_exposure,
                    "size": feature.vein_size,
                    "targets": [
                        {
                            "target": self._rule_test_payload(feature.target_block),
                            "state": {
                                "Name": feature.placed_block,
                            },
                        }
                    ],
                },
            }
        return {
            "type": "minecraft:ore",
            "config": {
                "discard_chance_on_air_exposure": 0.0,
                "size": feature.vein_size,
                "targets": [
                    {
                        "target": self._rule_test_payload("minecraft:stone_ore_replaceables"),
                        "state": {
                            "Name": feature.placed_block,
                        },
                    }
                ],
            },
        }

    def _world_feature_placed_payload(self, spec: ModSpec, feature: WorldFeatureSpec) -> dict[str, Any]:
        return {
            "feature": f"{spec.mod_id}:{feature.identifier}",
            "placement": [
                {"type": "minecraft:count", "count": feature.veins_per_chunk},
                {"type": "minecraft:in_square"},
                {
                    "type": "minecraft:height_range",
                    "height": {
                        "type": "minecraft:uniform",
                        "min_inclusive": {"absolute": feature.min_y},
                        "max_inclusive": {"absolute": feature.max_y},
                    },
                },
                {"type": "minecraft:biome"},
            ],
        }

    def _world_feature_biome_modifier_payload(self, spec: ModSpec, feature: WorldFeatureSpec) -> dict[str, Any]:
        return {
            "type": "neoforge:add_features",
            "biomes": feature.biomes,
            "features": [f"{spec.mod_id}:{feature.identifier}"],
            "step": feature.step,
        }

    def _generate_structure(self, resources_dir: Path, spec: ModSpec, structure: WorldStructureSpec) -> list[Path]:
        structure_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "worldgen" / "structure")
        structure_set_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "worldgen" / "structure_set")
        template_pool_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "worldgen" / "template_pool" / structure.identifier)
        return [
            write_json(structure_dir / f"{structure.identifier}.json", self._structure_payload(spec, structure)),
            write_json(structure_set_dir / f"{structure.identifier}.json", self._structure_set_payload(spec, structure)),
            write_json(template_pool_dir / "start_pool.json", self._template_pool_payload(spec, structure)),
        ]

    def _structure_payload(self, spec: ModSpec, structure: WorldStructureSpec) -> dict[str, Any]:
        return {
            "type": "minecraft:jigsaw",
            "biomes": structure.biomes,
            "step": structure.step,
            "spawn_overrides": {},
            "terrain_adaptation": structure.terrain_adaptation,
            "start_pool": f"{spec.mod_id}:{structure.identifier}/start_pool",
            "size": structure.size,
            "start_height": {"absolute": structure.start_height},
            "project_start_to_heightmap": "WORLD_SURFACE_WG",
            "max_distance_from_center": 80,
            "use_expansion_hack": False,
        }

    def _structure_set_payload(self, spec: ModSpec, structure: WorldStructureSpec) -> dict[str, Any]:
        return {
            "structures": [
                {
                    "structure": f"{spec.mod_id}:{structure.identifier}",
                    "weight": 1,
                }
            ],
            "placement": {
                "type": "minecraft:random_spread",
                "spacing": structure.spacing,
                "separation": structure.separation,
                "salt": structure.salt,
                "spread_type": "linear",
            },
        }

    def _template_pool_payload(self, spec: ModSpec, structure: WorldStructureSpec) -> dict[str, Any]:
        return {
            "name": f"{spec.mod_id}:{structure.identifier}/start_pool",
            "fallback": "minecraft:empty",
            "elements": [
                {
                    "weight": 1,
                    "element": {
                        "element_type": "minecraft:empty_pool_element",
                        "projection": "rigid",
                    },
                }
            ],
        }

    def _generate_loot_pool(self, resources_dir: Path, spec: ModSpec, loot_pool: LootPoolSpec) -> Path:
        loot_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "loot_table" / "chests")
        return write_json(loot_dir / f"{loot_pool.identifier}.json", self._loot_pool_payload(loot_pool))

    def _loot_pool_payload(self, loot_pool: LootPoolSpec) -> dict[str, Any]:
        return {
            "type": "minecraft:chest",
            "pools": [
                {
                    "rolls": loot_pool.rolls,
                    "entries": [self._loot_entry_payload(entry) for entry in loot_pool.entries],
                }
            ],
        }

    def _loot_entry_payload(self, entry: LootEntrySpec) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "minecraft:item",
            "name": entry.item,
            "weight": entry.weight,
        }
        functions = []
        if entry.min_count != 1 or entry.max_count != 1:
            functions.append(
                {
                    "function": "minecraft:set_count",
                    "count": {
                        "type": "minecraft:uniform",
                        "min": entry.min_count,
                        "max": entry.max_count,
                    },
                }
            )
        if functions:
            payload["functions"] = functions
        if entry.chance < 1.0:
            payload["conditions"] = [{"condition": "minecraft:random_chance", "chance": entry.chance}]
        return payload

    def _generate_ore_worldgen(self, resources_dir: Path, spec: ModSpec, ore: OreSpec) -> list[Path]:
        generated: list[Path] = []
        configured_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "worldgen" / "configured_feature")
        placed_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "worldgen" / "placed_feature")
        biome_modifier_dir = ensure_directory(resources_dir / "data" / spec.mod_id / "neoforge" / "biome_modifier")

        configured_id = ore.identifier
        placed_id = ore.identifier
        biome_modifier_id = f"add_{ore.identifier}"

        generated.append(
            write_json(
                configured_dir / f"{configured_id}.json",
                {
                    "type": "minecraft:ore",
                    "config": {
                        "discard_chance_on_air_exposure": 0.0,
                        "size": ore.worldgen.vein_size,
                        "targets": [
                            {
                                "target": self._rule_test_payload("minecraft:stone_ore_replaceables"),
                                "state": {
                                    "Name": f"{spec.mod_id}:{ore.identifier}",
                                },
                            },
                            *(
                                [
                                    {
                                        "target": self._rule_test_payload("minecraft:deepslate_ore_replaceables"),
                                        "state": {
                                            "Name": f"{spec.mod_id}:{ore.identifier}",
                                        },
                                    }
                                ]
                                if ore.worldgen.min_y < 0
                                else []
                            ),
                        ],
                    },
                },
            )
        )

        generated.append(
            write_json(
                placed_dir / f"{placed_id}.json",
                {
                    "feature": f"{spec.mod_id}:{configured_id}",
                    "placement": [
                        {"type": "minecraft:count", "count": ore.worldgen.veins_per_chunk},
                        {"type": "minecraft:in_square"},
                        {
                            "type": "minecraft:height_range",
                            "height": {
                                "type": "minecraft:uniform",
                                "min_inclusive": {"absolute": ore.worldgen.min_y},
                                "max_inclusive": {"absolute": ore.worldgen.max_y},
                            },
                        },
                        {"type": "minecraft:biome"},
                    ],
                },
            )
        )

        generated.append(
            write_json(
                biome_modifier_dir / f"{biome_modifier_id}.json",
                {
                    "type": "neoforge:add_features",
                    "biomes": "#minecraft:is_overworld",
                    "features": [f"{spec.mod_id}:{placed_id}"],
                    "step": "underground_ores",
                },
            )
        )
        return generated

    def _rule_test_payload(self, reference: str) -> dict[str, Any]:
        normalized = reference[1:] if reference.startswith("#") else reference
        if reference.startswith("#") or normalized.endswith("_replaceables"):
            return {
                "predicate_type": "minecraft:tag_match",
                "tag": normalized,
            }
        return {
            "predicate_type": "minecraft:block_match",
            "block": normalized,
        }

    def _world_reference(self, spec: ModSpec, reference: str) -> str:
        if ":" in reference or reference.startswith("#"):
            return reference
        return f"{spec.mod_id}:{reference}"
