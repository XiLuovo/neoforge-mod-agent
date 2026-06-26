from __future__ import annotations

import json
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

from neoforge_agent import AppConfig, MockLLMClient, ModProjectPlanner, WorkspaceAuditor, plan_with_llm
from neoforge_agent.models import BuildResult, ModSpec
from neoforge_agent.validator import validate_mod_spec


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class GenerationAuditTests(unittest.TestCase):
    def test_basic_ruby_generation_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            result = planner.execute(
                "Create a ruby mod with ruby.",
                workspace_name="ruby",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            self.assertTrue((result.workspace_dir / "src" / "main" / "resources" / "pack.mcmeta").exists())
            self.assertIn("src\\main\\resources\\pack.mcmeta", result.generated_files)
            item_definition_path = result.workspace_dir / "src" / "main" / "resources" / "assets" / "ruby_mod" / "items" / "ruby.json"
            texture_path = result.workspace_dir / "src" / "main" / "resources" / "assets" / "ruby_mod" / "textures" / "item" / "ruby.png"
            manifest_path = result.workspace_dir / ".agent" / "texture-manifest.json"
            resource_report_path = result.workspace_dir / ".agent" / "resource-quality-report.json"
            atlas_path = result.workspace_dir / ".agent" / "texture-atlas.png"
            self.assertTrue(item_definition_path.exists())
            self.assertEqual(
                json.loads(item_definition_path.read_text(encoding="utf-8"))["model"]["model"],
                "ruby_mod:item/ruby",
            )
            self.assertTrue(texture_path.exists())
            self.assertTrue(texture_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertTrue(manifest_path.exists())
            self.assertTrue(resource_report_path.exists())
            self.assertTrue(atlas_path.exists())
            self.assertIn(".agent\\texture-manifest.json", result.generated_files)
            self.assertIn(".agent\\resource-quality-report.json", result.generated_files)
            self.assertIn(".agent\\texture-atlas.png", result.generated_files)

            modspec = json.loads((result.workspace_dir / ".agent" / "modspec.json").read_text(encoding="utf-8"))
            feature_ids = {feature["id"] for feature in modspec["features"]}
            self.assertIn("ruby", feature_ids)

    def test_resource_quality_upgrade_writes_profiles_atlas_and_structure_previews(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "resource_quality_showcase.json")

            result = planner.execute_spec(
                spec,
                workspace_name="resource-quality",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            report_path = result.workspace_dir / ".agent" / "resource-quality-report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            atlas_path = result.workspace_dir / ".agent" / "texture-atlas.png"
            preview_path = result.workspace_dir / ".agent" / "previews" / "ruby_gallery.png"

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            self.assertEqual(report["version"], 8)
            self.assertEqual(report["generator"], "deterministic_resource_quality_v8")
            self.assertGreaterEqual(report["summary"]["textures"], 3)
            self.assertGreaterEqual(report["summary"]["model_variants"], 4)
            self.assertEqual(report["summary"]["structure_previews"], 1)
            self.assertTrue(atlas_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertTrue(preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertIn("quality_profile", report["texture_profiles"][0])
            self.assertIn("profile_id", report["texture_profiles"][0]["quality_profile"])
            self.assertEqual(report["structure_previews"][0]["path"], ".agent\\previews\\ruby_gallery.png")
            self.assertIn(".agent\\resource-quality-report.md", result.generated_files)
            self.assertTrue(any(check.id == "resources:quality_report:atlas_png" and check.status == "pass" for check in audit.checks))

    def test_audit_fails_when_generated_item_model_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            result = planner.execute(
                "Create a ruby mod with ruby.",
                workspace_name="ruby",
                overwrite=True,
                run_build=False,
            )
            model_path = (
                result.workspace_dir
                / "src"
                / "main"
                / "resources"
                / "assets"
                / "ruby_mod"
                / "models"
                / "item"
                / "ruby.json"
            )
            model_path.unlink()

            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertFalse(audit.success)
            self.assertTrue(any("item:ruby:model" == issue.id for issue in audit.errors))

    def test_audit_fails_when_generated_item_definition_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            result = planner.execute(
                "Create a ruby mod with ruby.",
                workspace_name="ruby",
                overwrite=True,
                run_build=False,
            )
            definition_path = (
                result.workspace_dir
                / "src"
                / "main"
                / "resources"
                / "assets"
                / "ruby_mod"
                / "items"
                / "ruby.json"
            )
            definition_path.unlink()

            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertFalse(audit.success)
            self.assertTrue(any("item:ruby:definition" == issue.id for issue in audit.errors))

    def test_audit_fails_when_generated_item_texture_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            result = planner.execute(
                "Create a ruby mod with ruby.",
                workspace_name="ruby",
                overwrite=True,
                run_build=False,
            )
            texture_path = (
                result.workspace_dir
                / "src"
                / "main"
                / "resources"
                / "assets"
                / "ruby_mod"
                / "textures"
                / "item"
                / "ruby.png"
            )
            texture_path.unlink()

            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertFalse(audit.success)
            self.assertTrue(any("item:ruby:texture" == issue.id for issue in audit.errors))

    def test_ruby_pickaxe_generation_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            result = planner.execute(
                "Create a ruby mod with ruby pickaxe.",
                workspace_name="ruby-pickaxe",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            self.assertEqual(result.spec.tools[0].identifier, "ruby_pickaxe")
            self.assertTrue(
                (
                    result.workspace_dir
                    / "src"
                    / "main"
                    / "resources"
                    / "assets"
                    / "ruby_mod"
                    / "textures"
                    / "item"
                    / "ruby_pickaxe.png"
                ).exists()
            )
            self.assertEqual(result.spec.tools[0].tool_material, "ruby")
            self.assertIn("ruby_pickaxe", {recipe.identifier for recipe in result.spec.recipes})

    def test_recipe_audit_rejects_invalid_resource_reference_shape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            result = planner.execute(
                "Create a ruby mod with ruby pickaxe.",
                workspace_name="ruby-pickaxe-invalid-recipe",
                overwrite=True,
                run_build=False,
            )
            recipe_path = result.workspace_dir / "src" / "main" / "resources" / "data" / "ruby_mod" / "recipe" / "ruby_pickaxe.json"
            recipe_json = json.loads(recipe_path.read_text(encoding="utf-8"))
            recipe_json["key"]["R"] = "{'item':ruby_mod_ruby"
            recipe_path.write_text(json.dumps(recipe_json, ensure_ascii=False, indent=2), encoding="utf-8")

            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertFalse(audit.success)
            self.assertTrue(any(issue.id == "recipe:ruby_pickaxe:json_key:R" for issue in audit.errors))
            self.assertTrue(any("Invalid resource reference" in issue.message for issue in audit.errors))

    def test_ruby_tool_set_generates_sword_tools_and_recipes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            result = planner.execute(
                "Create a ruby mod with ruby tool set.",
                workspace_name="ruby-tools",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            self.assertIn("ruby", {item.identifier for item in result.spec.items})
            self.assertEqual({sword.identifier for sword in result.spec.swords}, {"ruby_sword"})
            self.assertEqual(
                {tool.identifier for tool in result.spec.tools},
                {"ruby_pickaxe", "ruby_axe", "ruby_shovel", "ruby_hoe"},
            )
            self.assertTrue(all(tool.tool_material == "ruby" for tool in result.spec.tools))
            self.assertTrue(all(sword.tool_material == "ruby" for sword in result.spec.swords))
            self.assertEqual(
                {recipe.identifier for recipe in result.spec.recipes},
                {"ruby_sword", "ruby_pickaxe", "ruby_axe", "ruby_shovel", "ruby_hoe"},
            )
            self.assertTrue(
                (
                    result.workspace_dir
                    / "src"
                    / "main"
                    / "resources"
                    / "data"
                    / "ruby_mod"
                    / "recipe"
                    / "ruby_sword.json"
                ).exists()
            )

    def test_chinese_ruby_equipment_sets_generate_material_item_and_recipes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            tool_result = planner.execute(
                "做一个红宝石模组，添加红宝石工具套装。",
                workspace_name="ruby-tools-zh",
                overwrite=True,
                run_build=False,
            )
            armor_result = planner.execute(
                "做一个红宝石模组，添加红宝石护甲套装。",
                workspace_name="ruby-armor-zh",
                overwrite=True,
                run_build=False,
            )

            self.assertTrue(tool_result.succeeded)
            self.assertTrue(armor_result.succeeded)
            self.assertIn("ruby", {item.identifier for item in tool_result.spec.items})
            self.assertIn("ruby_sword", {sword.identifier for sword in tool_result.spec.swords})
            self.assertIn("ruby_pickaxe", {tool.identifier for tool in tool_result.spec.tools})
            self.assertIn("ruby", {item.identifier for item in armor_result.spec.items})
            self.assertIn("ruby_helmet", {armor.identifier for armor in armor_result.spec.armors})
            self.assertIn("ruby_helmet", {recipe.identifier for recipe in armor_result.spec.recipes})

    def test_ruby_armor_set_generation_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            result = planner.execute(
                "Create a ruby mod with ruby armor set.",
                workspace_name="ruby-armor",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            self.assertEqual(
                {armor.identifier for armor in result.spec.armors},
                {"ruby_helmet", "ruby_chestplate", "ruby_leggings", "ruby_boots"},
            )
            self.assertIn("ruby", {item.identifier for item in result.spec.items})
            self.assertTrue(all(armor.armor_material == "ruby" for armor in result.spec.armors))
            self.assertEqual(
                {recipe.identifier for recipe in result.spec.recipes},
                {"ruby_helmet", "ruby_chestplate", "ruby_leggings", "ruby_boots"},
            )

    def test_ruby_block_variants_generate_assets_recipes_and_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            result = planner.execute(
                "Create a ruby mod with ruby block variants.",
                workspace_name="ruby-block-variants",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            block_kinds = {block.identifier: block.block_kind for block in result.spec.blocks}
            self.assertEqual(block_kinds["ruby_block"], "cube")
            self.assertEqual(block_kinds["ruby_stairs"], "stairs")
            self.assertEqual(block_kinds["ruby_slab"], "slab")
            self.assertEqual(block_kinds["ruby_wall"], "wall")
            self.assertEqual(block_kinds["ruby_button"], "button")
            self.assertEqual(block_kinds["ruby_pressure_plate"], "pressure_plate")
            self.assertEqual(block_kinds["ruby_fence"], "fence")
            self.assertEqual(block_kinds["ruby_fence_gate"], "fence_gate")
            self.assertEqual(block_kinds["ruby_door"], "door")
            self.assertEqual(block_kinds["ruby_trapdoor"], "trapdoor")
            self.assertTrue(all(block.base_block == "ruby_block" for block in result.spec.blocks if block.identifier != "ruby_block"))
            self.assertEqual(
                {
                    "ruby_block",
                    "ruby_stairs",
                    "ruby_slab",
                    "ruby_wall",
                    "ruby_button",
                    "ruby_pressure_plate",
                    "ruby_fence",
                    "ruby_fence_gate",
                    "ruby_door",
                    "ruby_trapdoor",
                },
                {recipe.identifier for recipe in result.spec.recipes},
            )
            asset_root = result.workspace_dir / "src" / "main" / "resources" / "assets" / "ruby_mod"
            self.assertTrue((asset_root / "blockstates" / "ruby_stairs.json").exists())
            self.assertTrue((asset_root / "models" / "block" / "ruby_stairs_inner.json").exists())
            self.assertTrue((asset_root / "models" / "block" / "ruby_wall_side_tall.json").exists())
            self.assertTrue((asset_root / "models" / "block" / "ruby_door_bottom_left.json").exists())
            self.assertTrue((asset_root / "models" / "block" / "ruby_trapdoor_open.json").exists())

    def test_chinese_ruby_block_variants_generate_set(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)

            result = planner.execute(
                "做一个红宝石模组，添加红宝石方块变体。",
                workspace_name="ruby-block-variants-zh",
                overwrite=True,
                run_build=False,
            )

            self.assertTrue(result.succeeded)
            self.assertIn("ruby_trapdoor", {block.identifier for block in result.spec.blocks})
            self.assertIn("ruby_fence_gate", {block.identifier for block in result.spec.blocks})
            self.assertIn("ruby_door", {recipe.identifier for recipe in result.spec.recipes})

    def test_behavior_dsl_item_and_block_generation_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "behavior_dsl_battle_charm.json")

            result = planner.execute_spec(
                spec,
                workspace_name="behavior-dsl",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            self.assertIn(".agent\\behavior-report.json", result.generated_files)
            self.assertIn(".agent\\behavior-report.md", result.generated_files)
            behavior_report = json.loads((result.workspace_dir / ".agent" / "behavior-report.json").read_text(encoding="utf-8"))
            self.assertEqual(behavior_report["totals"]["host_count"], 2)
            self.assertEqual(behavior_report["totals"]["compiled_host_count"], 2)
            self.assertGreaterEqual(behavior_report["totals"]["combo_event_count"], 1)
            self.assertGreaterEqual(behavior_report["totals"]["chain_action_count"], 1)
            self.assertGreaterEqual(behavior_report["totals"]["resource_action_count"], 1)
            self.assertGreaterEqual(behavior_report["totals"]["state_action_count"], 1)
            self.assertEqual(result.spec.items[0].behavior.behavior_type, "event_action")
            self.assertEqual(
                [event.trigger for event in result.spec.items[0].behavior.events],
                ["right_click", "inventory_tick"],
            )
            item_class = (
                result.workspace_dir
                / "src"
                / "main"
                / "java"
                / "com"
                / "generated"
                / "behavior_mod"
                / "item"
                / "BattleCharmItem.java"
            )
            block_class = (
                result.workspace_dir
                / "src"
                / "main"
                / "java"
                / "com"
                / "generated"
                / "behavior_mod"
                / "block"
                / "RubyPedestalBlock.java"
            )
            item_java = item_class.read_text(encoding="utf-8")
            block_java = block_class.read_text(encoding="utf-8")
            self.assertIn("public InteractionResult use", item_java)
            self.assertIn("public void inventoryTick", item_java)
            self.assertIn("spawnParticles", item_java)
            self.assertIn("playSound", item_java)
            self.assertIn("protected InteractionResult useWithoutItem", block_java)
            self.assertIn("RubyPedestalBlock", (result.workspace_dir / "src" / "main" / "java" / "com" / "generated" / "behavior_mod" / "BehaviorMod.java").read_text(encoding="utf-8"))

    def test_machine_blockentity_gui_generation_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "machine_ruby_compressor.json")

            result = planner.execute_spec(
                spec,
                workspace_name="machine",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            behavior_report = json.loads((result.workspace_dir / ".agent" / "behavior-report.json").read_text(encoding="utf-8"))
            self.assertIn(".agent\\behavior-report.json", result.generated_files)
            self.assertEqual(behavior_report["totals"]["host_count"], 1)
            self.assertEqual(behavior_report["totals"]["report_only_host_count"], 1)
            self.assertGreaterEqual(behavior_report["totals"]["trigger_counts"]["server_tick"], 1)
            self.assertGreaterEqual(behavior_report["totals"]["trigger_counts"]["machine_complete"], 1)
            machine_host = next(host for host in behavior_report["hosts"] if host["identifier"] == "ruby_compressor")
            self.assertEqual(machine_host["host_type"], "machine")
            self.assertEqual(machine_host["runtime_surface"], "report_only")
            self.assertEqual(result.spec.machines[0].machine_kind, "compressor")
            java_root = result.workspace_dir / "src" / "main" / "java" / "com" / "generated" / "machine_mod"
            main_java = (java_root / "MachineMod.java").read_text(encoding="utf-8")
            block_entity_java = (java_root / "block" / "entity" / "RubyCompressorBlockEntity.java").read_text(encoding="utf-8")
            menu_java = (java_root / "menu" / "RubyCompressorMenu.java").read_text(encoding="utf-8")
            screen_java = (java_root / "client" / "RubyCompressorScreen.java").read_text(encoding="utf-8")
            client_java = (java_root / "client" / "MachineModClient.java").read_text(encoding="utf-8")
            self.assertIn("BLOCK_ENTITY_TYPES", main_java)
            self.assertIn("MENU_TYPES", main_java)
            self.assertIn("ContainerData", block_entity_java)
            self.assertIn("serverTick", block_entity_java)
            self.assertIn("AbstractContainerMenu", menu_java)
            self.assertIn("AbstractContainerScreen", screen_java)
            self.assertIn("GuiGraphicsExtractor", screen_java)
            self.assertNotIn("playerInventoryTitle", screen_java)
            self.assertIn("RegisterMenuScreensEvent", client_java)
            self.assertIn("@EventBusSubscriber(modid = MachineMod.MODID, value = Dist.CLIENT)", client_java)
            self.assertTrue(
                (
                    result.workspace_dir
                    / "src"
                    / "main"
                    / "resources"
                    / "assets"
                    / "machine_mod"
                    / "items"
                    / "ruby_compressor.json"
                ).exists()
            )
            self.assertTrue(
                (
                    result.workspace_dir
                    / "src"
                    / "main"
                    / "resources"
                    / "assets"
                    / "machine_mod"
                    / "textures"
                    / "block"
                    / "ruby_compressor.png"
                ).exists()
            )

    def test_ore_worldgen_generation_uses_rule_test_targets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "ruby_worldgen.json")

            result = planner.execute_spec(
                spec,
                workspace_name="ruby-worldgen",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            configured_feature = json.loads(
                (
                    result.workspace_dir
                    / "src"
                    / "main"
                    / "resources"
                    / "data"
                    / "ruby_mod"
                    / "worldgen"
                    / "configured_feature"
                    / "ruby_ore.json"
                ).read_text(encoding="utf-8")
            )
            ore_rule_test = configured_feature["config"]["targets"][0]["target"]
            self.assertEqual(ore_rule_test["predicate_type"], "minecraft:tag_match")
            self.assertEqual(ore_rule_test["tag"], "minecraft:stone_ore_replaceables")

    def test_entity_mob_dsl_generation_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "entity_ruby_goblin.json")

            result = planner.execute_spec(
                spec,
                workspace_name="entity",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            behavior_report = json.loads((result.workspace_dir / ".agent" / "behavior-report.json").read_text(encoding="utf-8"))
            self.assertIn(".agent\\behavior-report.json", result.generated_files)
            self.assertEqual(behavior_report["totals"]["host_type_counts"]["entity"], 1)
            self.assertEqual(behavior_report["totals"]["report_only_host_count"], 1)
            self.assertGreaterEqual(behavior_report["totals"]["trigger_counts"]["spawn"], 1)
            self.assertGreaterEqual(behavior_report["totals"]["trigger_counts"]["hurt"], 1)
            entity_host = next(host for host in behavior_report["hosts"] if host["identifier"] == "ruby_goblin")
            self.assertEqual(entity_host["runtime_surface"], "report_only")
            self.assertEqual(result.spec.entities[0].identifier, "ruby_goblin")
            java_root = result.workspace_dir / "src" / "main" / "java" / "com" / "generated" / "entity_mod"
            main_java = (java_root / "EntityMod.java").read_text(encoding="utf-8")
            entity_java = (java_root / "entity" / "RubyGoblinEntity.java").read_text(encoding="utf-8")
            renderer_java = (java_root / "client" / "RubyGoblinRenderer.java").read_text(encoding="utf-8")
            client_java = (java_root / "client" / "EntityModEntityClient.java").read_text(encoding="utf-8")
            spawn_modifier = (
                result.workspace_dir
                / "src"
                / "main"
                / "resources"
                / "data"
                / "entity_mod"
                / "neoforge"
                / "biome_modifier"
                / "add_ruby_goblin.json"
            )
            loot_table = (
                result.workspace_dir
                / "src"
                / "main"
                / "resources"
                / "data"
                / "entity_mod"
                / "loot_table"
                / "entities"
                / "ruby_goblin.json"
            )
            texture = (
                result.workspace_dir
                / "src"
                / "main"
                / "resources"
                / "assets"
                / "entity_mod"
                / "textures"
                / "entity"
                / "ruby_goblin.png"
            )
            self.assertIn("ENTITY_TYPES", main_java)
            self.assertIn("Identifier.fromNamespaceAndPath", main_java)
            self.assertNotIn("ResourceLocation", main_java)
            self.assertIn("clientTrackingRange", main_java)
            self.assertIn("updateInterval", main_java)
            self.assertIn("registerEntityAttributes", main_java)
            self.assertIn("MeleeAttackGoal", entity_java)
            self.assertIn("NearestAttackableTargetGoal", entity_java)
            self.assertIn("NoopRenderer<RubyGoblinEntity>", renderer_java)
            self.assertNotIn("ResourceLocation", renderer_java)
            self.assertIn("RegisterRenderers", client_java)
            self.assertNotIn("EventBusSubscriber.Bus.MOD", client_java)
            self.assertTrue(spawn_modifier.exists())
            self.assertTrue(loot_table.exists())
            self.assertTrue(texture.exists())

    def test_entity_prompt_plans_ruby_goblin(self) -> None:
        planner = ModProjectPlanner(AppConfig.default())

        spec = planner.parse_request("Create a ruby goblin mob with melee attack, emerald drops, and overworld spawn.")

        self.assertEqual(spec.mod_id, "ruby_mod")
        self.assertEqual(len(spec.entities), 1)
        entity = spec.entities[0]
        self.assertEqual(entity.identifier, "ruby_goblin")
        self.assertEqual(entity.entity_kind, "monster")
        self.assertEqual(entity.attack.attack_type, "melee")
        self.assertEqual(entity.drops[0].item, "minecraft:emerald")
        self.assertIsNotNone(entity.spawn)

    def test_mock_llm_plans_ruby_goblin_entity(self) -> None:
        spec, artifacts = plan_with_llm(
            "Create a ruby goblin mob with melee attack, emerald drops, and overworld spawn.",
            MockLLMClient(PROJECT_ROOT),
            config=AppConfig.default(),
        )

        self.assertEqual(artifacts.warnings, [])
        self.assertEqual(len(spec.entities), 1)
        self.assertEqual(spec.entities[0].identifier, "ruby_goblin")
        self.assertEqual(spec.entities[0].drops[0].item, "minecraft:emerald")

    def test_world_structure_dsl_generation_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "world_ruby_realm.json")

            result = planner.execute_spec(
                spec,
                workspace_name="world-ruby-realm",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            data_root = result.workspace_dir / "src" / "main" / "resources" / "data" / "world_mod"
            self.assertTrue((data_root / "dimension_type" / "ruby_realm.json").exists())
            self.assertTrue((data_root / "dimension" / "ruby_realm.json").exists())
            self.assertTrue((data_root / "worldgen" / "biome" / "ruby_fields.json").exists())
            self.assertTrue((data_root / "worldgen" / "configured_feature" / "ruby_vein.json").exists())
            self.assertTrue((data_root / "worldgen" / "structure" / "ruby_shrine.json").exists())
            self.assertTrue((data_root / "worldgen" / "structure_set" / "ruby_shrine.json").exists())
            self.assertTrue((data_root / "worldgen" / "template_pool" / "ruby_shrine" / "start_pool.json").exists())
            self.assertTrue((data_root / "loot_table" / "chests" / "ruby_shrine_loot.json").exists())
            dimension_type = json.loads((data_root / "dimension_type" / "ruby_realm.json").read_text(encoding="utf-8"))
            self.assertIs(dimension_type["has_ender_dragon_fight"], False)
            self.assertEqual(dimension_type["monster_spawn_light_level"]["type"], "minecraft:uniform")
            self.assertEqual(dimension_type["monster_spawn_light_level"]["min_inclusive"], 0)
            self.assertEqual(dimension_type["monster_spawn_light_level"]["max_inclusive"], 7)
            self.assertNotIn("value", dimension_type["monster_spawn_light_level"])
            biome = json.loads((data_root / "worldgen" / "biome" / "ruby_fields.json").read_text(encoding="utf-8"))
            self.assertIsInstance(biome["carvers"], list)
            configured_feature = json.loads((data_root / "worldgen" / "configured_feature" / "ruby_vein.json").read_text(encoding="utf-8"))
            world_rule_test = configured_feature["config"]["targets"][0]["target"]
            self.assertEqual(world_rule_test["predicate_type"], "minecraft:tag_match")
            self.assertEqual(world_rule_test["tag"], "minecraft:stone_ore_replaceables")

    def test_quest_advancement_root_uses_valid_background_sprite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "quest_guide_gameplay_loop.json")

            result = planner.execute_spec(
                spec,
                workspace_name="quest-guide",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            advancement = json.loads(
                (
                    result.workspace_dir
                    / "src"
                    / "main"
                    / "resources"
                    / "data"
                    / "quest_mod"
                    / "advancement"
                    / "ruby_questline"
                    / "mine_ruby_ore.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(advancement["display"]["background"], "minecraft:gui/advancements/backgrounds/stone")

    def test_world_prompt_plans_ruby_realm(self) -> None:
        planner = ModProjectPlanner(AppConfig.default())

        spec = planner.parse_request("Create a Ruby Realm dimension with Ruby Fields biome, ruby vein world feature, ruby shrine structure, and loot pool.")

        self.assertEqual(spec.dimensions[0].identifier, "ruby_realm")
        self.assertEqual(spec.biomes[0].identifier, "ruby_fields")
        self.assertEqual(spec.world_features[0].identifier, "ruby_vein")
        self.assertEqual(spec.structures[0].identifier, "ruby_shrine")
        self.assertEqual(spec.loot_pools[0].identifier, "ruby_shrine_loot")

    def test_mock_llm_plans_world_structure_dsl(self) -> None:
        spec, artifacts = plan_with_llm(
            "Create a Ruby Realm dimension with Ruby Fields biome, ruby vein world feature, ruby shrine structure, and loot pool.",
            MockLLMClient(PROJECT_ROOT),
            config=AppConfig.default(),
        )

        self.assertEqual(artifacts.warnings, [])
        self.assertEqual(spec.mod_id, "world_mod")
        self.assertEqual({dimension.identifier for dimension in spec.dimensions}, {"ruby_realm"})
        self.assertEqual({biome.identifier for biome in spec.biomes}, {"ruby_fields"})
        self.assertEqual({feature.identifier for feature in spec.world_features}, {"ruby_vein"})
        self.assertEqual({structure.identifier for structure in spec.structures}, {"ruby_shrine"})
        self.assertEqual({pool.identifier for pool in spec.loot_pools}, {"ruby_shrine_loot"})

    def test_controlled_java_extension_generation_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "controlled_java_extension.json")

            result = planner.execute_spec(
                spec,
                workspace_name="java-extension",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            extension_java = (
                result.workspace_dir
                / "src"
                / "main"
                / "java"
                / "com"
                / "generated"
                / "extension_mod"
                / "extension"
                / "SafeInfoExtension.java"
            )
            report_json = result.workspace_dir / ".agent" / "java-extension-report.json"
            diff_md = result.workspace_dir / ".agent" / "java-extension-diff.md"
            rollback_json = result.workspace_dir / ".agent" / "java-extension-rollback-report.json"
            self.assertTrue(extension_java.exists())
            self.assertTrue(report_json.exists())
            self.assertTrue(diff_md.exists())
            self.assertTrue(rollback_json.exists())
            java_text = extension_java.read_text(encoding="utf-8")
            self.assertIn("package com.generated.extension_mod.extension;", java_text)
            self.assertIn("public final class SafeInfoExtension", java_text)
            self.assertIn("public static String describe()", java_text)
            report = json.loads(report_json.read_text(encoding="utf-8"))
            rollback = json.loads(rollback_json.read_text(encoding="utf-8"))
            self.assertEqual(report["version"], "6.1")
            self.assertEqual(report["build_gate"]["status"], "not_run")
            self.assertEqual(report["proof_artifacts"]["diff_report"], ".agent/java-extension-diff.md")
            self.assertEqual(rollback["status"], "standby")
            self.assertFalse(rollback["rollback_required"])
            diff_text = diff_md.read_text(encoding="utf-8")
            self.assertIn("+++ b/src/main/java/com/generated/extension_mod/extension/SafeInfoExtension.java", diff_text)
            self.assertIn("+public final class SafeInfoExtension", diff_text)
            self.assertIn(".agent\\java-extension-report.json", result.generated_files)
            self.assertIn(".agent\\java-extension-diff.md", result.generated_files)
            self.assertIn(".agent\\java-extension-rollback-report.json", result.generated_files)

    def test_controlled_java_extension_build_gate_updates_acceptance_report(self) -> None:
        class FakeBuilder:
            def build(self, project_dir: Path) -> BuildResult:
                return BuildResult(
                    attempted=True,
                    success=True,
                    command=["gradlew.bat", "build"],
                    return_code=0,
                    jar_path=project_dir / "build" / "libs" / "extension_mod-0.1.0.jar",
                    log_path=project_dir / ".agent" / "logs" / "gradle-build.log",
                    summary="Gradle build completed successfully.",
                )

        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            planner.builder = FakeBuilder()
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "controlled_java_extension.json")

            result = planner.execute_spec(
                spec,
                workspace_name="java-extension-build",
                overwrite=True,
                run_build=True,
            )

            report = json.loads((result.workspace_dir / ".agent" / "java-extension-report.json").read_text(encoding="utf-8"))
            rollback = json.loads((result.workspace_dir / ".agent" / "java-extension-rollback-report.json").read_text(encoding="utf-8"))
            self.assertTrue(result.succeeded)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["build_gate"]["status"], "pass")
            self.assertTrue(report["build_gate"]["success"])
            self.assertEqual(rollback["status"], "not_needed")
            self.assertFalse(rollback["rollback_required"])

    def test_controlled_java_extension_build_failure_marks_rollback_report(self) -> None:
        class FakeBuilder:
            def build(self, project_dir: Path) -> BuildResult:
                return BuildResult(
                    attempted=True,
                    success=False,
                    command=["gradlew.bat", "build"],
                    return_code=1,
                    log_path=project_dir / ".agent" / "logs" / "gradle-build.log",
                    summary="Gradle build failed.",
                )

        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            planner.builder = FakeBuilder()
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "controlled_java_extension.json")

            result = planner.execute_spec(
                spec,
                workspace_name="java-extension-build-fail",
                overwrite=True,
                run_build=True,
            )

            report = json.loads((result.workspace_dir / ".agent" / "java-extension-report.json").read_text(encoding="utf-8"))
            rollback = json.loads((result.workspace_dir / ".agent" / "java-extension-rollback-report.json").read_text(encoding="utf-8"))
            self.assertFalse(result.succeeded)
            self.assertEqual(report["status"], "failed-build")
            self.assertEqual(report["build_gate"]["status"], "fail")
            self.assertEqual(rollback["status"], "recommended")
            self.assertTrue(rollback["rollback_required"])
            self.assertEqual(rollback["failure"]["return_code"], 1)

    def test_controlled_java_extension_prompt_plans_safe_class(self) -> None:
        planner = ModProjectPlanner(AppConfig.default())

        spec = planner.parse_request("Create a controlled Java extension for a safe info helper.")

        self.assertEqual(spec.mod_id, "extension_mod")
        self.assertEqual(len(spec.java_extensions), 1)
        self.assertEqual(spec.java_extensions[0].class_name, "SafeInfoExtension")
        self.assertEqual(spec.java_extensions[0].methods[0].name, "describe")
        self.assertIn("Java Extensions", spec.requested_features)

    def test_mock_llm_plans_controlled_java_extension(self) -> None:
        spec, artifacts = plan_with_llm(
            "Create a controlled Java extension for a safe info helper.",
            MockLLMClient(PROJECT_ROOT),
            config=AppConfig.default(),
        )

        self.assertEqual(artifacts.warnings, [])
        self.assertEqual(spec.mod_id, "extension_mod")
        self.assertEqual({extension.class_name for extension in spec.java_extensions}, {"SafeInfoExtension"})

    def test_java_extension_validator_rejects_forbidden_token(self) -> None:
        spec = ModSpec.from_dict(
            {
                "mod_id": "extension_mod",
                "mod_name": "Extension Mod",
                "package": "com.generated.extension_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "java_extension",
                        "id": "bad_extension",
                        "display_name_en_us": "Bad Extension",
                        "class_name": "BadExtension",
                        "purpose": "Show validator rejection.",
                        "explanation": "This should fail before generation.",
                        "methods": [
                            {
                                "name": "describe",
                                "return_type": "String",
                                "return_value": "Runtime.getRuntime()",
                                "explanation": "Unsafe token should be blocked.",
                            }
                        ],
                    }
                ],
            }
        )

        report = validate_mod_spec(spec, AppConfig.default())

        self.assertFalse(report.is_valid)
        self.assertTrue(any("forbidden token" in issue.message for issue in report.errors))

    def test_java_extension_violation_example_is_rejected(self) -> None:
        data = json.loads((PROJECT_ROOT / "examples" / "invalid" / "controlled_java_extension_violation.json").read_text(encoding="utf-8"))
        spec = ModSpec.from_dict(data)

        report = validate_mod_spec(spec, AppConfig.default())

        self.assertFalse(report.is_valid)
        self.assertTrue(any("outside the sandbox allowlist" in issue.message for issue in report.errors))
        self.assertTrue(any("forbidden token" in issue.message for issue in report.errors))

    def test_chinese_machine_prompt_plans_machine_kind(self) -> None:
        planner = ModProjectPlanner(AppConfig.default())

        compressor = planner.parse_request("生成一个红宝石压缩机机器，带菜单界面、能量和进度条。")
        altar = planner.parse_request("生成一个魔法祭坛机器，带容器和 Screen。")
        storage = planner.parse_request("生成一个储物方块，右键打开容器界面。")

        self.assertEqual(compressor.machines[0].machine_kind, "compressor")
        self.assertEqual(altar.machines[0].machine_kind, "magic_altar")
        self.assertEqual(storage.machines[0].machine_kind, "storage")
        self.assertEqual(altar.mod_id, "machine_mod")


if __name__ == "__main__":
    unittest.main()
