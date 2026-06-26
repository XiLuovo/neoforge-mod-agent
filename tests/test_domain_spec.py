from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neoforge_agent import AppConfig, DomainSpecRegistry, ModSpec
from neoforge_agent.feature_catalog import (
    FeatureMergePolicy,
    definition_for_collection,
    definition_for_kind,
    iter_feature_kind_definitions,
)


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class DomainSpecTests(unittest.TestCase):
    def test_feature_kind_catalog_preserves_stable_order_and_lookup(self) -> None:
        definitions = iter_feature_kind_definitions()
        kinds = [definition.kind for definition in definitions]
        collections = [definition.collection_name for definition in definitions]

        self.assertEqual(
            kinds,
            [
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
            ],
        )
        self.assertEqual(len(kinds), len(set(kinds)))
        self.assertEqual(len(collections), len(set(collections)))
        self.assertEqual(definition_for_kind("ore").collection_name, "ores")
        self.assertEqual(definition_for_collection("progressions").kind, "progression")
        self.assertEqual(definition_for_kind("recipe").merge_policy, FeatureMergePolicy.REPLACE_RECIPE_BY_IDENTIFIER)
        self.assertEqual(definition_for_kind("progression").merge_policy, FeatureMergePolicy.MERGE_PROGRESSION)

    def test_modspec_features_round_trip_uses_catalog_order(self) -> None:
        feature_payloads = [
            {"type": "item", "id": "ruby"},
            {"type": "block", "id": "ruby_block"},
            {"type": "machine", "id": "ruby_compressor"},
            {"type": "entity", "id": "ruby_guardian"},
            {"type": "dimension", "id": "ruby_realm"},
            {"type": "biome", "id": "ruby_fields"},
            {"type": "world_feature", "id": "ruby_geode"},
            {"type": "structure", "id": "ruby_tower"},
            {"type": "loot_pool", "id": "ruby_chest"},
            {"type": "java_extension", "id": "ruby_helper", "class_name": "RubyHelper"},
            {"type": "ore", "id": "ruby_ore"},
            {"type": "food", "id": "ruby_apple"},
            {"type": "sword", "id": "ruby_sword"},
            {"type": "tool", "id": "ruby_pickaxe"},
            {"type": "armor", "id": "ruby_helmet"},
            {
                "type": "recipe",
                "id": "ruby_pickaxe",
                "recipe_type": "shaped",
                "result": "ruby_mod:ruby_pickaxe",
            },
            {
                "type": "progression",
                "id": "ruby_progression",
                "entry_stage": "start",
                "end_stage": "finish",
                "stages": [{"id": "start"}, {"id": "finish"}],
                "links": [{"from": "start", "to": "finish"}],
            },
            {"type": "balance_plan", "id": "ruby_balance", "target_progression": "ruby_progression"},
            {"type": "quest", "id": "ruby_quest", "target_progression": "ruby_progression"},
        ]

        spec = ModSpec.from_dict(
            {
                "mod_id": "ruby_mod",
                "mod_name": "Ruby Mod",
                "package": "com.generated.ruby_mod",
                "features": list(reversed(feature_payloads)),
            }
        )

        self.assertEqual(
            [feature.feature_type for feature in spec.iter_features()],
            [definition.kind for definition in iter_feature_kind_definitions()],
        )
        self.assertEqual(
            [feature["type"] for feature in spec.to_dict()["features"]],
            [definition.kind for definition in iter_feature_kind_definitions()],
        )

    def test_default_registry_exposes_stable_neoforge_and_planned_future_domains(self) -> None:
        registry = DomainSpecRegistry.default()
        payload = registry.to_dict()

        domain_ids = {domain["domain_id"] for domain in payload["domains"]}
        self.assertIn("minecraft.neoforge", domain_ids)
        self.assertIn("spring.api", domain_ids)
        self.assertIn("unity.component", domain_ids)
        self.assertEqual(payload["stable_count"], 1)
        self.assertEqual(payload["planned_count"], 2)

    def test_modspec_is_domain_spec_and_round_trips_through_registry(self) -> None:
        registry = DomainSpecRegistry.default()
        spec = ModSpec(
            raw_request="Create a ruby item.",
            mod_id="ruby_mod",
            display_name="Ruby Mod",
            package_name="com.generated.ruby_mod",
        )

        self.assertEqual(spec.domain_id, "minecraft.neoforge")
        self.assertEqual(spec.domain_spec_type, "ModSpec")

        dumped = registry.get("minecraft.neoforge").dump(spec)
        self.assertEqual(dumped["domain"], "minecraft.neoforge")
        self.assertEqual(dumped["domain_spec_type"], "ModSpec")

        loaded = registry.load(dumped)
        self.assertIsInstance(loaded, ModSpec)
        self.assertEqual(loaded.mod_id, "ruby_mod")
        self.assertEqual(loaded.domain_id, "minecraft.neoforge")

        legacy_alias_loaded = registry.load({**dumped, "domain": "neoforge"})
        self.assertIsInstance(legacy_alias_loaded, ModSpec)
        self.assertEqual(legacy_alias_loaded.mod_id, "ruby_mod")

    def test_modspec_recipe_dict_references_round_trip_to_resource_ids(self) -> None:
        spec = ModSpec.from_dict(
            {
                "mod_id": "ruby_mod",
                "features": [
                    {"type": "item", "id": "ruby"},
                    {
                        "type": "recipe",
                        "id": "ruby_pickaxe",
                        "recipe_type": "shaped",
                        "pattern": ["RRR", " S ", " S "],
                        "keys": {"R": {"item": "ruby_mod:ruby"}, "S": {"item": "minecraft:stick"}},
                        "result": {"id": "ruby_mod:ruby_pickaxe", "count": 1},
                    },
                ],
            }
        )

        recipe = spec.recipes[0]
        self.assertEqual(recipe.keys, {"R": "ruby_mod:ruby", "S": "minecraft:stick"})
        self.assertEqual(recipe.result, "ruby_mod:ruby_pickaxe")

    def test_neoforge_plugin_validates_existing_modspec_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            registry = DomainSpecRegistry.default()
            plugin = registry.get("minecraft.neoforge")
            spec = plugin.load(
                {
                    "domain": "minecraft.neoforge",
                    "domain_spec_type": "ModSpec",
                    "raw_request": "Create a ruby item.",
                    "mod_id": "ruby_mod",
                    "mod_name": "Ruby Mod",
                    "package": "com.generated.ruby_mod",
                    "features": [
                        {
                            "type": "item",
                            "id": "ruby",
                            "display_name_en_us": "Ruby",
                        }
                    ],
                }
            )

            report = plugin.validate(spec, test_config(Path(tmp)))
            description = plugin.describe(spec)

            self.assertTrue(report.is_valid)
            self.assertEqual(description["domain_id"], "minecraft.neoforge")
            self.assertEqual(description["feature_count"], 1)
            self.assertEqual(description["feature_counts"]["item"], 1)

    def test_planned_domain_cannot_load_until_plugin_is_implemented(self) -> None:
        registry = DomainSpecRegistry.default()
        plugin = registry.get("spring.api")

        self.assertTrue(plugin.can_load({"domain": "spring.api", "domain_spec_type": "SpringApiSpec"}))
        with self.assertRaises(NotImplementedError):
            plugin.load({"domain": "spring.api", "domain_spec_type": "SpringApiSpec"})

    def test_domains_cli_lists_registry_as_json(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent.cli",
                "domains",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONPATH": str(SRC_ROOT)},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(completed.stdout)
        domain_ids = {domain["domain_id"] for domain in payload["domains"]}

        self.assertTrue(payload["success"])
        self.assertIn("minecraft.neoforge", domain_ids)
        self.assertIn("spring.api", domain_ids)
        self.assertIn("unity.component", domain_ids)


if __name__ == "__main__":
    unittest.main()
