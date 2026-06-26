from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

from .config import AppConfig
from .java_extension_generator import JAVA_EXTENSION_SOURCE_FORBIDDEN_TOKENS
from .models import FoodSpec, MachineSpec, ModSpec, OreSpec, SwordSpec


def _valid_resource_reference(reference: str) -> bool:
    value = reference[1:] if reference.startswith("#") else reference
    if not value:
        return False
    if ":" in value:
        namespace, path = value.split(":", 1)
        return bool(re.fullmatch(r"[a-z0-9_.-]+", namespace) and re.fullmatch(r"[a-z0-9_./-]+", path))
    return bool(re.fullmatch(r"[a-z0-9_./-]+", value))


@dataclass(slots=True)
class AuditIssue:
    id: str
    severity: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
        }


@dataclass(slots=True)
class AuditCheck:
    id: str
    status: str
    path: str | None = None
    message: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "path": self.path,
            "message": self.message,
        }


@dataclass(slots=True)
class AuditResult:
    success: bool
    workspace: str
    mod_id: str
    checked_features: int
    errors: list[AuditIssue] = field(default_factory=list)
    warnings: list[AuditIssue] = field(default_factory=list)
    checks: list[AuditCheck] = field(default_factory=list)
    audit_report_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "workspace": self.workspace,
            "mod_id": self.mod_id,
            "checked_features": self.checked_features,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
            "checks": [check.to_dict() for check in self.checks],
            "audit_report_path": self.audit_report_path,
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "checks_count": len(self.checks),
        }


class WorkspaceAuditor:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def audit_workspace(self, workspace: Path) -> AuditResult:
        workspace = workspace.resolve()
        agent_dir = self.config.agent_dir_for(workspace)
        modspec_path = agent_dir / "modspec.json"
        summary_path = agent_dir / "generation-summary.json"
        if not modspec_path.exists():
            raise FileNotFoundError(f"Missing modspec.json: {modspec_path}")
        spec = ModSpec.from_dict(json.loads(modspec_path.read_text(encoding="utf-8")))
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}

        result = AuditResult(
            success=True,
            workspace=str(workspace),
            mod_id=spec.mod_id,
            checked_features=len(list(spec.iter_features())),
        )

        self._check_path(result, "project:settings_gradle", workspace / "settings.gradle", required=True)
        self._check_path(result, "project:build_gradle", workspace / "build.gradle", required=True)
        self._check_path(result, "project:src_main_java", workspace / "src" / "main" / "java", required=True)
        self._check_path(result, "project:src_main_resources", workspace / "src" / "main" / "resources", required=True)
        self._check_path(result, "project:mods_toml", workspace / "src" / "main" / "templates" / "META-INF" / "neoforge.mods.toml", required=True)
        self._check_path(result, "project:modspec", modspec_path, required=True)
        self._check_path(result, "project:generation_summary", summary_path, required=True)
        self._check_path(result, "project:manual_checklist", agent_dir / "manual-test-checklist.md", required=True)
        pack_mcmeta_path = workspace / "src" / "main" / "resources" / "pack.mcmeta"
        summary_generated_files = summary.get("generated_files", []) if isinstance(summary, dict) else []
        pack_mcmeta_required = "src\\main\\resources\\pack.mcmeta" in summary_generated_files or "src/main/resources/pack.mcmeta" in summary_generated_files
        self._check_path(result, "project:pack_mcmeta", pack_mcmeta_path, required=pack_mcmeta_required, warning=not pack_mcmeta_required)
        if pack_mcmeta_path.exists():
            self._audit_pack_mcmeta(result, pack_mcmeta_path)
        self._audit_texture_manifest(result, workspace, summary)
        self._audit_resource_quality_report(result, workspace, summary)

        self._audit_generation_summary(result, workspace, summary)
        self._audit_items(result, workspace, spec)
        self._audit_blocks(result, workspace, spec)
        self._audit_foods(result, workspace, spec)
        self._audit_swords(result, workspace, spec)
        self._audit_tools(result, workspace, spec)
        self._audit_armors(result, workspace, spec)
        self._audit_entities(result, workspace, spec)
        self._audit_recipes(result, workspace, spec)
        self._audit_worldgen(result, workspace, spec)
        self._audit_java_extensions(result, workspace, spec)
        self._audit_progressions(result, workspace, spec)
        self._audit_balance_plans(result, workspace, spec)
        self._audit_quests(result, workspace, spec)
        self._audit_behavior_report(result, workspace, spec)

        result.success = not result.errors
        report_json = self._write_report_json(workspace, result)
        self._write_report_md(workspace, result)
        result.audit_report_path = str(report_json)
        return result

    def _audit_generation_summary(self, result: AuditResult, workspace: Path, summary: dict) -> None:
        files = summary.get("generated_files", [])
        if not isinstance(files, list):
            self._error(result, "summary:generated_files", "generation-summary.json missing generated_files array", str(self.config.agent_dir_for(workspace) / "generation-summary.json"))
            return
        for relative in files:
            path = workspace / str(relative)
            if workspace not in path.resolve().parents and path.resolve() != workspace:
                self._error(result, "summary:path_escape", f"generated_files contains path outside workspace: {relative}", str(path))
                continue
            self._check_path(result, f"summary:{relative}", path, required=True)

    def _audit_items(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        main_java = self._main_java_text(workspace, spec)
        en_us, zh_cn = self._load_langs(workspace, spec)
        for item in spec.items:
            self._check_path(result, f"item:{item.identifier}:model", workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "models" / "item" / f"{item.identifier}.json", True)
            self._check_item_definition(result, workspace, spec, item.identifier)
            self._check_texture(result, workspace, spec, "item", item.identifier)
            self._check_path(result, f"item:{item.identifier}:lang_en", workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "lang" / "en_us.json", True, key=f"item.{spec.mod_id}.{item.identifier}", data=en_us)
            self._check_path(result, f"item:{item.identifier}:lang_zh", workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "lang" / "zh_cn.json", True, key=f"item.{spec.mod_id}.{item.identifier}", data=zh_cn)
            self._check_contains(result, f"item:{item.identifier}:register", main_java, item.identifier, str(workspace / "src" / "main" / "java"))
            if item.behavior is not None:
                class_name = self._behavior_class_name(item.identifier)
                path = workspace / "src" / "main" / "java" / Path(*spec.package_name.split(".")) / "item" / f"{class_name}.java"
                self._check_path(result, f"item:{item.identifier}:behavior_class", path, True)
                self._check_contains(result, f"item:{item.identifier}:behavior_register", main_java, class_name, str(path))

    def _audit_blocks(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        en_us, zh_cn = self._load_langs(workspace, spec)
        main_java = self._main_java_text(workspace, spec)
        for block in [*spec.blocks, *spec.machines, *spec.ores]:
            asset_root = workspace / "src" / "main" / "resources" / "assets" / spec.mod_id
            self._check_path(result, f"block:{block.identifier}:blockstate", asset_root / "blockstates" / f"{block.identifier}.json", True)
            self._check_path(result, f"block:{block.identifier}:block_model", asset_root / "models" / "block" / f"{block.identifier}.json", True)
            self._check_path(result, f"block:{block.identifier}:item_model", asset_root / "models" / "item" / f"{block.identifier}.json", True)
            self._check_item_definition(result, workspace, spec, block.identifier)
            self._check_texture(result, workspace, spec, "block", block.identifier)
            self._check_path(result, f"block:{block.identifier}:loot", workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "loot_table" / "blocks" / f"{block.identifier}.json", True)
            self._check_path(result, f"block:{block.identifier}:lang_en", asset_root / "lang" / "en_us.json", True, key=f"block.{spec.mod_id}.{block.identifier}", data=en_us)
            self._check_path(result, f"block:{block.identifier}:lang_zh", asset_root / "lang" / "zh_cn.json", True, key=f"block.{spec.mod_id}.{block.identifier}", data=zh_cn)
            self._check_contains(result, f"block:{block.identifier}:register", main_java, block.identifier, str(workspace / 'src' / 'main' / 'java'))
            block_kind = getattr(block, "block_kind", "cube")
            expected_class = self._block_class_name(block_kind)
            if expected_class is not None:
                self._check_contains(result, f"block:{block.identifier}:block_class", main_java, expected_class, str(workspace / "src" / "main" / "java"))
            if block.requires_correct_tool:
                self._check_path(result, f"block:{block.identifier}:mineable", workspace / "src" / "main" / "resources" / "data" / "minecraft" / "tags" / "block" / "mineable" / "pickaxe.json", True)
            if isinstance(block, MachineSpec):
                self._audit_machine_sources(result, workspace, spec, block, main_java)
            if block.behavior is not None:
                class_name = self._behavior_block_class_name(block.identifier)
                path = workspace / "src" / "main" / "java" / Path(*spec.package_name.split(".")) / "block" / f"{class_name}.java"
                self._check_path(result, f"block:{block.identifier}:behavior_class", path, True)
                self._check_contains(result, f"block:{block.identifier}:behavior_register", main_java, class_name, str(path))

    def _audit_machine_sources(self, result: AuditResult, workspace: Path, spec: ModSpec, machine: MachineSpec, main_java: str) -> None:
        package_root = workspace / "src" / "main" / "java" / Path(*spec.package_name.split("."))
        base_name = "".join(part.capitalize() for part in machine.identifier.split("_"))
        block_class = f"{base_name}Block"
        block_entity_class = f"{base_name}BlockEntity"
        menu_class = f"{base_name}Menu"
        screen_class = f"{base_name}Screen"
        constant_name = machine.identifier.upper()
        main_class = self._main_class_name(spec)
        paths = {
            "block_class": package_root / "block" / f"{block_class}.java",
            "block_entity_class": package_root / "block" / "entity" / f"{block_entity_class}.java",
            "menu_class": package_root / "menu" / f"{menu_class}.java",
            "screen_class": package_root / "client" / f"{screen_class}.java",
            "client_class": package_root / "client" / f"{main_class}Client.java",
        }
        for suffix, path in paths.items():
            self._check_path(result, f"machine:{machine.identifier}:{suffix}", path, True)
        self._check_contains(result, f"machine:{machine.identifier}:block_entity_type", main_java, f"{constant_name}_BLOCK_ENTITY", str(package_root))
        self._check_contains(result, f"machine:{machine.identifier}:menu_type", main_java, f"{constant_name}_MENU", str(package_root))
        if paths["block_entity_class"].exists():
            text = paths["block_entity_class"].read_text(encoding="utf-8")
            self._check_contains(result, f"machine:{machine.identifier}:data_sync", text, "ContainerData", str(paths["block_entity_class"]))
            self._check_contains(result, f"machine:{machine.identifier}:server_tick", text, "serverTick", str(paths["block_entity_class"]))
        if paths["menu_class"].exists():
            self._check_contains(result, f"machine:{machine.identifier}:abstract_menu", paths["menu_class"].read_text(encoding="utf-8"), "AbstractContainerMenu", str(paths["menu_class"]))
        if paths["screen_class"].exists():
            self._check_contains(result, f"machine:{machine.identifier}:screen", paths["screen_class"].read_text(encoding="utf-8"), "AbstractContainerScreen", str(paths["screen_class"]))
        if paths["client_class"].exists():
            self._check_contains(result, f"machine:{machine.identifier}:screen_registration", paths["client_class"].read_text(encoding="utf-8"), "RegisterMenuScreensEvent", str(paths["client_class"]))

    def _audit_foods(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        main_java = self._main_java_text(workspace, spec)
        asset_root = workspace / "src" / "main" / "resources" / "assets" / spec.mod_id
        for food in spec.foods:
            self._check_path(result, f"food:{food.identifier}:model", asset_root / "models" / "item" / f"{food.identifier}.json", True)
            self._check_item_definition(result, workspace, spec, food.identifier)
            self._check_texture(result, workspace, spec, "item", food.identifier)
            self._check_contains(result, f"food:{food.identifier}:register", main_java, food.identifier, str(workspace / "src" / "main" / "java"))
            for effect in food.effects:
                self._check_contains(result, f"food:{food.identifier}:effect", main_java, effect.effect.split(":")[1].upper(), str(workspace / "src" / "main" / "java"))

    def _audit_swords(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        main_java = self._main_java_text(workspace, spec)
        asset_root = workspace / "src" / "main" / "resources" / "assets" / spec.mod_id
        for sword in spec.swords:
            self._check_path(result, f"sword:{sword.identifier}:model", asset_root / "models" / "item" / f"{sword.identifier}.json", True)
            self._check_item_definition(result, workspace, spec, sword.identifier)
            self._check_texture(result, workspace, spec, "item", sword.identifier)
            self._check_contains(result, f"sword:{sword.identifier}:register", main_java, sword.identifier, str(workspace / "src" / "main" / "java"))
            if sword.on_hit is not None or sword.behavior is not None:
                class_name = self._behavior_class_name(sword.identifier)
                path = workspace / "src" / "main" / "java" / Path(*spec.package_name.split(".")) / "item" / f"{class_name}.java"
                self._check_path(result, f"sword:{sword.identifier}:behavior_class", path, True)
                if sword.on_hit is not None and path.exists():
                    self._check_contains(result, f"sword:{sword.identifier}:ignite_logic", path.read_text(encoding="utf-8"), "igniteForSeconds", str(path))

    def _audit_tools(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        main_java = self._main_java_text(workspace, spec)
        en_us, zh_cn = self._load_langs(workspace, spec)
        asset_root = workspace / "src" / "main" / "resources" / "assets" / spec.mod_id
        for tool in spec.tools:
            self._check_path(result, f"tool:{tool.identifier}:model", asset_root / "models" / "item" / f"{tool.identifier}.json", True)
            self._check_item_definition(result, workspace, spec, tool.identifier)
            self._check_texture(result, workspace, spec, "item", tool.identifier)
            self._check_path(result, f"tool:{tool.identifier}:lang_en", asset_root / "lang" / "en_us.json", True, key=f"item.{spec.mod_id}.{tool.identifier}", data=en_us)
            self._check_path(result, f"tool:{tool.identifier}:lang_zh", asset_root / "lang" / "zh_cn.json", True, key=f"item.{spec.mod_id}.{tool.identifier}", data=zh_cn)
            self._check_contains(result, f"tool:{tool.identifier}:register", main_java, tool.identifier, str(workspace / "src" / "main" / "java"))
            self._check_contains(result, f"tool:{tool.identifier}:method", main_java, f".{tool.tool_type}(", str(workspace / "src" / "main" / "java"))

    def _audit_armors(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        main_java = self._main_java_text(workspace, spec)
        en_us, zh_cn = self._load_langs(workspace, spec)
        asset_root = workspace / "src" / "main" / "resources" / "assets" / spec.mod_id
        armor_type_names = {
            "helmet": "HELMET",
            "chestplate": "CHESTPLATE",
            "leggings": "LEGGINGS",
            "boots": "BOOTS",
        }
        for armor in spec.armors:
            self._check_path(result, f"armor:{armor.identifier}:model", asset_root / "models" / "item" / f"{armor.identifier}.json", True)
            self._check_item_definition(result, workspace, spec, armor.identifier)
            self._check_texture(result, workspace, spec, "item", armor.identifier)
            self._check_path(result, f"armor:{armor.identifier}:lang_en", asset_root / "lang" / "en_us.json", True, key=f"item.{spec.mod_id}.{armor.identifier}", data=en_us)
            self._check_path(result, f"armor:{armor.identifier}:lang_zh", asset_root / "lang" / "zh_cn.json", True, key=f"item.{spec.mod_id}.{armor.identifier}", data=zh_cn)
            self._check_contains(result, f"armor:{armor.identifier}:register", main_java, armor.identifier, str(workspace / "src" / "main" / "java"))
            self._check_contains(result, f"armor:{armor.identifier}:humanoid_armor", main_java, "humanoidArmor", str(workspace / "src" / "main" / "java"))
            self._check_contains(
                result,
                f"armor:{armor.identifier}:armor_type",
                main_java,
                f"ArmorType.{armor_type_names.get(armor.armor_type.lower(), 'HELMET')}",
                str(workspace / "src" / "main" / "java"),
            )

    def _audit_entities(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        main_java = self._main_java_text(workspace, spec)
        en_us, zh_cn = self._load_langs(workspace, spec)
        asset_root = workspace / "src" / "main" / "resources" / "assets" / spec.mod_id
        package_root = workspace / "src" / "main" / "java" / Path(*spec.package_name.split("."))
        main_class = self._main_class_name(spec)
        for entity in spec.entities:
            base_name = "".join(part.capitalize() for part in entity.identifier.split("_") if part)
            entity_class = f"{base_name}Entity"
            renderer_class = f"{base_name}Renderer"
            entity_path = package_root / "entity" / f"{entity_class}.java"
            renderer_path = package_root / "client" / f"{renderer_class}.java"
            client_path = package_root / "client" / f"{main_class}EntityClient.java"
            loot_path = workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "loot_table" / "entities" / f"{entity.identifier}.json"

            self._check_path(result, f"entity:{entity.identifier}:class", entity_path, True)
            self._check_path(result, f"entity:{entity.identifier}:renderer", renderer_path, True)
            self._check_path(result, f"entity:{entity.identifier}:client", client_path, True)
            self._check_texture(result, workspace, spec, "entity", entity.identifier)
            self._check_path(result, f"entity:{entity.identifier}:loot", loot_path, True)
            self._check_path(result, f"entity:{entity.identifier}:lang_en", asset_root / "lang" / "en_us.json", True, key=f"entity.{spec.mod_id}.{entity.identifier}", data=en_us)
            self._check_path(result, f"entity:{entity.identifier}:lang_zh", asset_root / "lang" / "zh_cn.json", True, key=f"entity.{spec.mod_id}.{entity.identifier}", data=zh_cn)
            self._check_contains(result, f"entity:{entity.identifier}:register", main_java, entity.identifier, str(package_root))
            self._check_contains(result, f"entity:{entity.identifier}:entity_type", main_java, "ENTITY_TYPES", str(package_root))
            self._check_contains(result, f"entity:{entity.identifier}:attributes", main_java, "registerEntityAttributes", str(package_root))
            if entity_path.exists():
                entity_java = entity_path.read_text(encoding="utf-8")
                self._check_contains(result, f"entity:{entity.identifier}:attribute_source", entity_java, "createAttributes", str(entity_path))
                if entity.attack is not None and entity.attack.attack_type == "melee":
                    self._check_contains(result, f"entity:{entity.identifier}:melee_goal", entity_java, "MeleeAttackGoal", str(entity_path))
            if client_path.exists():
                self._check_contains(result, f"entity:{entity.identifier}:renderer_registration", client_path.read_text(encoding="utf-8"), "RegisterRenderers", str(client_path))
            if entity.spawn is not None and entity.spawn.enabled:
                spawn_path = workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "neoforge" / "biome_modifier" / f"add_{entity.identifier}.json"
                self._check_path(result, f"entity:{entity.identifier}:spawn_modifier", spawn_path, True)
                if spawn_path.exists():
                    text = spawn_path.read_text(encoding="utf-8")
                    self._check_contains(result, f"entity:{entity.identifier}:spawn_type", text, f"{spec.mod_id}:{entity.identifier}", str(spawn_path))
                    self._check_contains(result, f"entity:{entity.identifier}:spawn_biomes", text, entity.spawn.biomes, str(spawn_path))

    def _audit_recipes(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        known_ids = {feature.identifier for feature in spec.all_content()}
        for recipe in spec.recipes:
            path = workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "recipe" / f"{recipe.identifier}.json"
            self._check_path(result, f"recipe:{recipe.identifier}:file", path, True)
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self._error(result, f"recipe:{recipe.identifier}:json", f"Recipe JSON is invalid: {exc}", str(path))
                continue
            self._check(result, f"recipe:{recipe.identifier}:json", True, str(path), None)
            self._check_reference(result, f"recipe:{recipe.identifier}:result", recipe.result, spec.mod_id, known_ids, str(path))
            for ingredient in recipe.ingredients:
                self._check_reference(result, f"recipe:{recipe.identifier}:ingredient", ingredient, spec.mod_id, known_ids, str(path))
            for ingredient in recipe.keys.values():
                self._check_reference(result, f"recipe:{recipe.identifier}:key", ingredient, spec.mod_id, known_ids, str(path))
            for check_id, reference in self._recipe_json_references(recipe.identifier, data):
                self._check_reference(result, check_id, reference, spec.mod_id, known_ids, str(path))

    def _audit_worldgen(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        data_root = workspace / "src" / "main" / "resources" / "data" / spec.mod_id
        for ore in spec.ores:
            if ore.worldgen is None or not ore.worldgen.enabled:
                continue
            configured = data_root / "worldgen" / "configured_feature" / f"{ore.identifier}.json"
            placed = data_root / "worldgen" / "placed_feature" / f"{ore.identifier}.json"
            biome_modifier = data_root / "neoforge" / "biome_modifier" / f"add_{ore.identifier}.json"
            for check_id, path in (
                (f"ore:{ore.identifier}:configured_feature", configured),
                (f"ore:{ore.identifier}:placed_feature", placed),
                (f"ore:{ore.identifier}:biome_modifier", biome_modifier),
            ):
                self._check_path(result, check_id, path, True)
            if configured.exists():
                text = configured.read_text(encoding="utf-8")
                self._check_contains(result, f"ore:{ore.identifier}:configured_ref", text, f"{spec.mod_id}:{ore.identifier}", str(configured))
                self._audit_configured_feature_rule_test(result, f"ore:{ore.identifier}", configured, expected_reference="minecraft:stone_ore_replaceables")
            if placed.exists():
                text = placed.read_text(encoding="utf-8")
                self._check_contains(result, f"ore:{ore.identifier}:placed_ref", text, f"{spec.mod_id}:{ore.identifier}", str(placed))
            if biome_modifier.exists():
                text = biome_modifier.read_text(encoding="utf-8")
                self._check_contains(result, f"ore:{ore.identifier}:biome_ref", text, "#minecraft:is_overworld", str(biome_modifier))
                self._check_contains(result, f"ore:{ore.identifier}:step", text, "underground_ores", str(biome_modifier))

        for dimension in spec.dimensions:
            dimension_type = data_root / "dimension_type" / f"{dimension.identifier}.json"
            dimension_path = data_root / "dimension" / f"{dimension.identifier}.json"
            self._check_path(result, f"dimension:{dimension.identifier}:dimension_type", dimension_type, True)
            self._check_path(result, f"dimension:{dimension.identifier}:dimension", dimension_path, True)
            if dimension_type.exists():
                text = dimension_type.read_text(encoding="utf-8")
                self._check_contains(result, f"dimension:{dimension.identifier}:height", text, str(dimension.height), str(dimension_type))
                self._check_contains(result, f"dimension:{dimension.identifier}:logical_height", text, str(dimension.logical_height), str(dimension_type))
                self._audit_dimension_type_runtime_shape(result, f"dimension:{dimension.identifier}", dimension_type)
            if dimension_path.exists():
                text = dimension_path.read_text(encoding="utf-8")
                self._check_contains(result, f"dimension:{dimension.identifier}:type_ref", text, f"{spec.mod_id}:{dimension.identifier}", str(dimension_path))
                self._check_contains(result, f"dimension:{dimension.identifier}:biome_ref", text, self._world_reference(spec, dimension.biome), str(dimension_path))

        for biome in spec.biomes:
            biome_path = data_root / "worldgen" / "biome" / f"{biome.identifier}.json"
            self._check_path(result, f"biome:{biome.identifier}:file", biome_path, True)
            if biome_path.exists():
                text = biome_path.read_text(encoding="utf-8")
                self._check_contains(result, f"biome:{biome.identifier}:temperature", text, str(biome.temperature), str(biome_path))
                self._check_contains(result, f"biome:{biome.identifier}:sky_color", text, str(biome.sky_color), str(biome_path))
                self._audit_biome_runtime_shape(result, f"biome:{biome.identifier}", biome_path)

        for feature in spec.world_features:
            configured = data_root / "worldgen" / "configured_feature" / f"{feature.identifier}.json"
            placed = data_root / "worldgen" / "placed_feature" / f"{feature.identifier}.json"
            biome_modifier = data_root / "neoforge" / "biome_modifier" / f"add_{feature.identifier}.json"
            for check_id, path in (
                (f"world_feature:{feature.identifier}:configured_feature", configured),
                (f"world_feature:{feature.identifier}:placed_feature", placed),
                (f"world_feature:{feature.identifier}:biome_modifier", biome_modifier),
            ):
                self._check_path(result, check_id, path, True)
            if configured.exists():
                text = configured.read_text(encoding="utf-8")
                self._check_contains(result, f"world_feature:{feature.identifier}:placed_block", text, feature.placed_block, str(configured))
                self._check_contains(result, f"world_feature:{feature.identifier}:vein_size", text, str(feature.vein_size), str(configured))
                self._audit_configured_feature_rule_test(result, f"world_feature:{feature.identifier}", configured, expected_reference=feature.target_block)
            if placed.exists():
                text = placed.read_text(encoding="utf-8")
                self._check_contains(result, f"world_feature:{feature.identifier}:placed_ref", text, f"{spec.mod_id}:{feature.identifier}", str(placed))
                self._check_contains(result, f"world_feature:{feature.identifier}:count", text, str(feature.veins_per_chunk), str(placed))
            if biome_modifier.exists():
                text = biome_modifier.read_text(encoding="utf-8")
                self._check_contains(result, f"world_feature:{feature.identifier}:biome_ref", text, feature.biomes, str(biome_modifier))
                self._check_contains(result, f"world_feature:{feature.identifier}:step", text, feature.step, str(biome_modifier))

        for structure in spec.structures:
            structure_path = data_root / "worldgen" / "structure" / f"{structure.identifier}.json"
            structure_set = data_root / "worldgen" / "structure_set" / f"{structure.identifier}.json"
            start_pool = data_root / "worldgen" / "template_pool" / structure.identifier / "start_pool.json"
            for check_id, path in (
                (f"structure:{structure.identifier}:structure", structure_path),
                (f"structure:{structure.identifier}:structure_set", structure_set),
                (f"structure:{structure.identifier}:template_pool", start_pool),
            ):
                self._check_path(result, check_id, path, True)
            if structure_path.exists():
                text = structure_path.read_text(encoding="utf-8")
                self._check_contains(result, f"structure:{structure.identifier}:start_pool", text, f"{spec.mod_id}:{structure.identifier}/start_pool", str(structure_path))
                self._check_contains(result, f"structure:{structure.identifier}:biomes", text, structure.biomes, str(structure_path))
                self._check_contains(result, f"structure:{structure.identifier}:step", text, structure.step, str(structure_path))
            if structure_set.exists():
                text = structure_set.read_text(encoding="utf-8")
                self._check_contains(result, f"structure:{structure.identifier}:structure_ref", text, f"{spec.mod_id}:{structure.identifier}", str(structure_set))
                self._check_contains(result, f"structure:{structure.identifier}:spacing", text, str(structure.spacing), str(structure_set))
                self._check_contains(result, f"structure:{structure.identifier}:separation", text, str(structure.separation), str(structure_set))
            if start_pool.exists():
                self._check_contains(result, f"structure:{structure.identifier}:empty_pool", start_pool.read_text(encoding="utf-8"), "minecraft:empty_pool_element", str(start_pool))

        for pool in spec.loot_pools:
            loot_path = data_root / "loot_table" / "chests" / f"{pool.identifier}.json"
            self._check_path(result, f"loot_pool:{pool.identifier}:file", loot_path, True)
            if loot_path.exists():
                text = loot_path.read_text(encoding="utf-8")
                self._check_contains(result, f"loot_pool:{pool.identifier}:kind", text, "minecraft:chest", str(loot_path))
                for entry in pool.entries:
                    self._check_contains(result, f"loot_pool:{pool.identifier}:entry:{entry.item}", text, entry.item, str(loot_path))

    def _audit_java_extensions(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        if not spec.java_extensions:
            return

        package_root = workspace / "src" / "main" / "java" / Path(*spec.package_name.split("."))
        report_path = self.config.agent_dir_for(workspace) / "java-extension-report.json"
        diff_path = self.config.agent_dir_for(workspace) / "java-extension-diff.md"
        rollback_json_path = self.config.agent_dir_for(workspace) / "java-extension-rollback-report.json"
        rollback_md_path = self.config.agent_dir_for(workspace) / "java-extension-rollback-report.md"
        self._check_path(result, "java_extension:report_json", report_path, True)
        self._check_path(result, "java_extension:diff_md", diff_path, True)
        self._check_path(result, "java_extension:rollback_json", rollback_json_path, True)
        self._check_path(result, "java_extension:rollback_md", rollback_md_path, True)
        report_classes: set[str] = set()
        if report_path.exists():
            try:
                data = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self._error(result, "java_extension:report_json:parse", f"java-extension-report.json is invalid JSON: {exc}", str(report_path))
                data = {}
            entries = data.get("extensions", []) if isinstance(data, dict) else []
            if isinstance(entries, list):
                report_classes = {
                    str(entry.get("class_name", ""))
                    for entry in entries
                    if isinstance(entry, dict)
                }
            self._check(result, "java_extension:report:sandbox", data.get("sandbox", {}).get("mode") == "managed-additive-class" if isinstance(data, dict) else False, str(report_path), "Java extension report missing sandbox mode.")
            self._check(result, "java_extension:report:build_gate", "build_gate" in data if isinstance(data, dict) else False, str(report_path), "Java extension report missing build gate.")
            self._check(result, "java_extension:report:proof_artifacts", "proof_artifacts" in data if isinstance(data, dict) else False, str(report_path), "Java extension report missing proof artifacts.")
        if rollback_json_path.exists():
            try:
                rollback_data = json.loads(rollback_json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self._error(result, "java_extension:rollback_json:parse", f"java-extension-rollback-report.json is invalid JSON: {exc}", str(rollback_json_path))
                rollback_data = {}
            self._check(result, "java_extension:rollback:steps", "rollback_steps" in rollback_data if isinstance(rollback_data, dict) else False, str(rollback_json_path), "Java extension rollback report missing rollback steps.")

        for extension in spec.java_extensions:
            path = package_root / "extension" / f"{extension.class_name}.java"
            self._check_path(result, f"java_extension:{extension.identifier}:class", path, True)
            self._check(result, f"java_extension:{extension.identifier}:report_entry", extension.class_name in report_classes, str(report_path), f"Report missing Java extension class '{extension.class_name}'.")
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self._check_contains(result, f"java_extension:{extension.identifier}:package", text, f"package {spec.package_name}.extension;", str(path))
            self._check_contains(result, f"java_extension:{extension.identifier}:final_class", text, f"public final class {extension.class_name}", str(path))
            for method in extension.methods:
                self._check_contains(result, f"java_extension:{extension.identifier}:method:{method.name}", text, f"public static {method.return_type} {method.name}()", str(path))
            for token in JAVA_EXTENSION_SOURCE_FORBIDDEN_TOKENS:
                self._check(result, f"java_extension:{extension.identifier}:forbidden:{token}", token not in text, str(path), f"Forbidden token '{token}' found in controlled Java extension.")

    def _audit_progressions(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        if not spec.progressions:
            return

        agent_dir = self.config.agent_dir_for(workspace)
        report_json = agent_dir / "progression-report.json"
        report_md = agent_dir / "progression-report.md"
        self._check_path(result, "progression:report_json", report_json, True)
        self._check_path(result, "progression:report_md", report_md, True)
        if not report_json.exists():
            return
        try:
            data = json.loads(report_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, "progression:report_json:parse", f"progression-report.json is invalid JSON: {exc}", str(report_json))
            return

        totals = data.get("totals", {}) if isinstance(data, dict) else {}
        progressions = data.get("progressions", []) if isinstance(data, dict) else []
        self._check(result, "progression:report:version", data.get("version") == "7.0" if isinstance(data, dict) else False, str(report_json), "Progression report missing V7 version.")
        self._check(result, "progression:report:loop_count", int(totals.get("loop_count", -1)) == len(spec.progressions) if isinstance(totals, dict) else False, str(report_json), "Progression report loop count does not match ModSpec.")
        self._check(result, "progression:report:list", isinstance(progressions, list), str(report_json), "Progression report missing progressions list.")
        report_ids = {
            str(entry.get("id", ""))
            for entry in progressions
            if isinstance(entry, dict)
        } if isinstance(progressions, list) else set()
        for progression in spec.progressions:
            self._check(result, f"progression:{progression.identifier}:report_entry", progression.identifier in report_ids, str(report_json), f"Progression report missing loop '{progression.identifier}'.")

    def _audit_balance_plans(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        if not spec.balance_plans:
            return

        agent_dir = self.config.agent_dir_for(workspace)
        report_json = agent_dir / "balance-report.json"
        report_md = agent_dir / "balance-report.md"
        self._check_path(result, "balance:report_json", report_json, True)
        self._check_path(result, "balance:report_md", report_md, True)
        if not report_json.exists():
            return
        try:
            data = json.loads(report_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, "balance:report_json:parse", f"balance-report.json is invalid JSON: {exc}", str(report_json))
            return

        totals = data.get("totals", {}) if isinstance(data, dict) else {}
        plans = data.get("plans", []) if isinstance(data, dict) else []
        self._check(result, "balance:report:version", data.get("version") == "7.1" if isinstance(data, dict) else False, str(report_json), "Balance report missing V7.1 version.")
        self._check(result, "balance:report:plan_count", int(totals.get("plan_count", -1)) == len(spec.balance_plans) if isinstance(totals, dict) else False, str(report_json), "Balance report plan count does not match ModSpec.")
        self._check(result, "balance:report:list", isinstance(plans, list), str(report_json), "Balance report missing plans list.")
        self._check(result, "balance:report:recipes", int(totals.get("recipe_recommendations_count", -1)) >= 0 if isinstance(totals, dict) else False, str(report_json), "Balance report missing recipe recommendation count.")
        report_ids = {
            str(entry.get("id", ""))
            for entry in plans
            if isinstance(entry, dict)
        } if isinstance(plans, list) else set()
        for plan in spec.balance_plans:
            self._check(result, f"balance:{plan.identifier}:report_entry", plan.identifier in report_ids, str(report_json), f"Balance report missing plan '{plan.identifier}'.")

    def _audit_quests(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        if not spec.quests:
            return

        agent_dir = self.config.agent_dir_for(workspace)
        data_root = workspace / "src" / "main" / "resources" / "data" / spec.mod_id
        report_json = agent_dir / "quest-report.json"
        report_md = agent_dir / "quest-report.md"
        guide_md = agent_dir / "guidebook.md"
        self._check_path(result, "quest:report_json", report_json, True)
        self._check_path(result, "quest:report_md", report_md, True)
        self._check_path(result, "quest:guidebook_md", guide_md, True)
        if not report_json.exists():
            return
        try:
            data = json.loads(report_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, "quest:report_json:parse", f"quest-report.json is invalid JSON: {exc}", str(report_json))
            return

        totals = data.get("totals", {}) if isinstance(data, dict) else {}
        quests = data.get("quests", []) if isinstance(data, dict) else []
        self._check(result, "quest:report:version", data.get("version") == "7.2" if isinstance(data, dict) else False, str(report_json), "Quest report missing V7.2 version.")
        self._check(result, "quest:report:quest_count", int(totals.get("quest_count", -1)) == len(spec.quests) if isinstance(totals, dict) else False, str(report_json), "Quest report quest count does not match ModSpec.")
        self._check(result, "quest:report:list", isinstance(quests, list), str(report_json), "Quest report missing quests list.")
        report_ids = {
            str(entry.get("id", ""))
            for entry in quests
            if isinstance(entry, dict)
        } if isinstance(quests, list) else set()
        for quest in spec.quests:
            self._check(result, f"quest:{quest.identifier}:report_entry", quest.identifier in report_ids, str(report_json), f"Quest report missing quest '{quest.identifier}'.")
            for task_id in self._quest_task_ids(quest, spec):
                advancement_path = data_root / "advancement" / quest.identifier / f"{task_id}.json"
                self._check_path(result, f"quest:{quest.identifier}:{task_id}:advancement", advancement_path, True)
                if advancement_path.exists():
                    self._audit_advancement_runtime_shape(result, f"quest:{quest.identifier}:{task_id}", advancement_path)
            book_root = data_root / "patchouli_books" / quest.guidebook_id
            self._check_path(result, f"quest:{quest.identifier}:book", book_root / "book.json", True)
            self._check_path(result, f"quest:{quest.identifier}:category", book_root / "en_us" / "categories" / f"{quest.category}.json", True)
            self._check_path(result, f"quest:{quest.identifier}:entry", book_root / "en_us" / "entries" / f"{quest.identifier}.json", True)

    def _audit_behavior_report(self, result: AuditResult, workspace: Path, spec: ModSpec) -> None:
        behavior_features = [feature for feature in spec.iter_features() if getattr(feature, "behavior", None) is not None]
        if not behavior_features:
            return

        agent_dir = self.config.agent_dir_for(workspace)
        report_json = agent_dir / "behavior-report.json"
        report_md = agent_dir / "behavior-report.md"
        self._check_path(result, "behavior:report_json", report_json, True)
        self._check_path(result, "behavior:report_md", report_md, True)
        if not report_json.exists():
            return

        try:
            data = json.loads(report_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, "behavior:report_json:parse", f"behavior-report.json is invalid JSON: {exc}", str(report_json))
            return

        totals = data.get("totals", {}) if isinstance(data, dict) else {}
        hosts = data.get("hosts", []) if isinstance(data, dict) else []
        self._check(result, "behavior:report:version", data.get("version") == "5.1-shared" if isinstance(data, dict) else False, str(report_json), "Behavior report missing shared V5.1 version.")
        self._check(result, "behavior:report:host_count", int(totals.get("host_count", -1)) == len(behavior_features) if isinstance(totals, dict) else False, str(report_json), "Behavior report host count does not match ModSpec.")
        self._check(result, "behavior:report:list", isinstance(hosts, list), str(report_json), "Behavior report missing hosts list.")
        report_ids = {
            str(entry.get("identifier", ""))
            for entry in hosts
            if isinstance(entry, dict)
        } if isinstance(hosts, list) else set()
        for feature in behavior_features:
            self._check(result, f"behavior:{feature.identifier}:report_entry", feature.identifier in report_ids, str(report_json), f"Behavior report missing host '{feature.identifier}'.")

    def _quest_task_ids(self, quest, spec: ModSpec) -> list[str]:
        if quest.tasks:
            return [task.identifier for task in quest.tasks]
        progression = next(
            (candidate for candidate in spec.progressions if candidate.identifier == quest.target_progression),
            None,
        )
        if progression is None:
            return []
        return [stage.identifier for stage in progression.stages]

    def _world_reference(self, spec: ModSpec, reference: str) -> str:
        if ":" in reference or reference.startswith("#"):
            return reference
        return f"{spec.mod_id}:{reference}"

    def _main_java_text(self, workspace: Path, spec: ModSpec) -> str:
        java_root = workspace / "src" / "main" / "java" / Path(*spec.package_name.split("."))
        if not java_root.exists():
            return ""
        files = list(java_root.rglob("*.java"))
        if not files:
            return ""
        return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files)

    def _load_langs(self, workspace: Path, spec: ModSpec) -> tuple[dict, dict]:
        asset_root = workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "lang"
        en_us = json.loads((asset_root / "en_us.json").read_text(encoding="utf-8")) if (asset_root / "en_us.json").exists() else {}
        zh_cn = json.loads((asset_root / "zh_cn.json").read_text(encoding="utf-8")) if (asset_root / "zh_cn.json").exists() else {}
        return en_us, zh_cn

    def _behavior_class_name(self, identifier: str) -> str:
        return "".join(part.capitalize() for part in identifier.split("_")) + "Item"

    def _behavior_block_class_name(self, identifier: str) -> str:
        return "".join(part.capitalize() for part in identifier.split("_")) + "Block"

    def _main_class_name(self, spec: ModSpec) -> str:
        class_name = "".join(part.capitalize() for part in spec.mod_id.split("_") if part)
        return class_name if class_name.endswith("Mod") else f"{class_name}Mod"

    def _block_class_name(self, block_kind: str) -> str | None:
        return {
            "stairs": "StairBlock",
            "slab": "SlabBlock",
            "wall": "WallBlock",
            "button": "ButtonBlock",
            "pressure_plate": "PressurePlateBlock",
            "fence": "FenceBlock",
            "fence_gate": "FenceGateBlock",
            "door": "DoorBlock",
            "trapdoor": "TrapDoorBlock",
        }.get(block_kind)

    def _check_path(self, result: AuditResult, check_id: str, path: Path, required: bool, key: str | None = None, data: dict | None = None, warning: bool = False) -> None:
        if key is not None and data is not None:
            ok = key in data
            message = None if ok else f"Missing lang key '{key}'"
            self._check(result, check_id, ok, str(path), message, warning=warning)
            return
        if not required and not warning and not path.exists():
            result.checks.append(AuditCheck(id=check_id, status="skip", path=str(path), message="Optional file not present"))
            return
        ok = path.exists()
        message = None if ok else "Missing required file"
        self._check(result, check_id, ok, str(path), message, warning=warning)

    def _check_contains(self, result: AuditResult, check_id: str, haystack: str, needle: str, path: str) -> None:
        self._check(result, check_id, needle in haystack, path, None if needle in haystack else f"Missing expected content '{needle}'")

    def _check_reference(self, result: AuditResult, check_id: str, reference: str, mod_id: str, known_ids: set[str], path: str) -> None:
        if not _valid_resource_reference(reference):
            self._check(result, check_id, False, path, f"Invalid resource reference '{reference}'")
            return
        ok = True
        if ":" in reference:
            namespace, value = reference.split(":", 1)
            if namespace == mod_id:
                ok = value in known_ids
        else:
            ok = reference in known_ids
        self._check(result, check_id, ok, path, None if ok else f"Missing referenced id '{reference}'")

    def _recipe_json_references(self, recipe_id: str, data: dict) -> list[tuple[str, str]]:
        references: list[tuple[str, str]] = []
        result_ref = self._extract_recipe_reference(data.get("result"))
        if result_ref:
            references.append((f"recipe:{recipe_id}:json_result", result_ref))

        keys = data.get("key")
        if isinstance(keys, dict):
            for symbol, value in keys.items():
                reference = self._extract_recipe_reference(value)
                if reference:
                    references.append((f"recipe:{recipe_id}:json_key:{symbol}", reference))

        ingredients = data.get("ingredients")
        if isinstance(ingredients, list):
            for index, value in enumerate(ingredients):
                reference = self._extract_recipe_reference(value)
                if reference:
                    references.append((f"recipe:{recipe_id}:json_ingredient:{index}", reference))
        return references

    def _extract_recipe_reference(self, value: object) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("id", "item"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate:
                    return candidate
        return None

    def _audit_configured_feature_rule_test(self, result: AuditResult, prefix: str, path: Path, *, expected_reference: str) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, f"{prefix}:configured_json", f"Configured feature JSON is invalid: {exc}", str(path))
            return
        config = data.get("config") if isinstance(data, dict) else None
        targets = config.get("targets") if isinstance(config, dict) else None
        ok_targets = isinstance(targets, list) and bool(targets)
        self._check(result, f"{prefix}:configured_targets", ok_targets, str(path), None if ok_targets else "Configured feature must declare a non-empty config.targets array.")
        if not ok_targets:
            return
        first = targets[0]
        ok_first = isinstance(first, dict)
        self._check(result, f"{prefix}:configured_target_entry", ok_first, str(path), None if ok_first else "Configured feature target entry must be an object.")
        if not ok_first:
            return
        rule_test = first.get("target")
        ok_rule_test = isinstance(rule_test, dict)
        self._check(result, f"{prefix}:configured_rule_test", ok_rule_test, str(path), None if ok_rule_test else "Configured feature target must be a rule-test object, not a bare string.")
        if not ok_rule_test:
            return
        predicate_type = rule_test.get("predicate_type")
        ok_predicate = predicate_type in {"minecraft:tag_match", "minecraft:block_match"}
        self._check(result, f"{prefix}:configured_predicate_type", ok_predicate, str(path), None if ok_predicate else "Configured feature target.predicate_type must be minecraft:tag_match or minecraft:block_match.")
        expected_key = "tag" if str(expected_reference).startswith("#") or str(expected_reference).endswith("_replaceables") else "block"
        expected_value = expected_reference[1:] if expected_key == "tag" and str(expected_reference).startswith("#") else expected_reference
        self._check(
            result,
            f"{prefix}:configured_predicate_value",
            rule_test.get(expected_key) == expected_value,
            str(path),
            None if rule_test.get(expected_key) == expected_value else f"Configured feature target must store '{expected_value}' under '{expected_key}'.",
        )

    def _audit_dimension_type_runtime_shape(self, result: AuditResult, prefix: str, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, f"{prefix}:dimension_type_json", f"Dimension type JSON is invalid: {exc}", str(path))
            return
        self._check(
            result,
            f"{prefix}:dimension_has_ender_dragon_fight",
            "has_ender_dragon_fight" in data,
            str(path),
            "Dimension type must include has_ender_dragon_fight for MC 26.1 registry loading.",
        )
        light_level = data.get("monster_spawn_light_level")
        ok_light = (
            isinstance(light_level, dict)
            and light_level.get("type") == "minecraft:uniform"
            and "min_inclusive" in light_level
            and "max_inclusive" in light_level
            and "value" not in light_level
        )
        self._check(
            result,
            f"{prefix}:dimension_monster_spawn_light_level",
            ok_light,
            str(path),
            "Dimension type monster_spawn_light_level must use top-level min_inclusive/max_inclusive, not a nested value object.",
        )

    def _audit_biome_runtime_shape(self, result: AuditResult, prefix: str, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, f"{prefix}:biome_json", f"Biome JSON is invalid: {exc}", str(path))
            return
        carvers = data.get("carvers")
        self._check(
            result,
            f"{prefix}:biome_carvers_shape",
            isinstance(carvers, list),
            str(path),
            "Biome carvers must be an array for MC 26.1 registry loading.",
        )

    def _audit_advancement_runtime_shape(self, result: AuditResult, prefix: str, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, f"{prefix}:advancement_json", f"Advancement JSON is invalid: {exc}", str(path))
            return
        if "parent" in data:
            return
        display = data.get("display") if isinstance(data, dict) else None
        background = display.get("background") if isinstance(display, dict) else None
        ok_background = (
            isinstance(background, str)
            and bool(background)
            and not background.startswith("minecraft:textures/")
            and not background.endswith(".png")
        )
        self._check(
            result,
            f"{prefix}:advancement_root_background",
            ok_background,
            str(path),
            "Root advancement display.background must use a GUI sprite id such as minecraft:gui/advancements/backgrounds/stone.",
        )

    def _check(self, result: AuditResult, check_id: str, ok: bool, path: str | None, message: str | None, warning: bool = False) -> None:
        result.checks.append(AuditCheck(id=check_id, status="pass" if ok else "fail", path=path, message=message))
        if ok:
            return
        issue = AuditIssue(id=check_id, severity="warning" if warning else "error", message=message or "Check failed", path=path)
        if warning:
            result.warnings.append(issue)
        else:
            result.errors.append(issue)

    def _audit_pack_mcmeta(self, result: AuditResult, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, "project:pack_mcmeta:json", f"pack.mcmeta is invalid JSON: {exc}", str(path))
            return

        ok_pack = isinstance(data.get("pack"), dict)
        self._check(result, "project:pack_mcmeta:pack", ok_pack, str(path), None if ok_pack else "pack.mcmeta missing 'pack' object")
        if not ok_pack:
            return

        pack = data["pack"]
        has_description = isinstance(pack.get("description"), str) and bool(pack.get("description"))
        self._check(result, "project:pack_mcmeta:description", has_description, str(path), None if has_description else "pack.mcmeta missing pack.description")
        has_pack_format = isinstance(pack.get("pack_format"), int)
        self._check(result, "project:pack_mcmeta:pack_format", has_pack_format, str(path), None if has_pack_format else "pack.mcmeta missing integer pack.pack_format")

    def _audit_texture_manifest(self, result: AuditResult, workspace: Path, summary: dict) -> None:
        path = self.config.agent_dir_for(workspace) / "texture-manifest.json"
        generated_files = summary.get("generated_files", []) if isinstance(summary, dict) else []
        required = ".agent\\texture-manifest.json" in generated_files or ".agent/texture-manifest.json" in generated_files
        self._check_path(result, "textures:manifest", path, required=required, warning=not required)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, "textures:manifest:json", f"texture-manifest.json is invalid JSON: {exc}", str(path))
            return
        textures = data.get("textures")
        ok = isinstance(textures, list)
        self._check(result, "textures:manifest:textures", ok, str(path), None if ok else "texture-manifest.json missing textures array")
        if not ok:
            return
        for index, entry in enumerate(textures):
            if not isinstance(entry, dict):
                self._error(result, f"textures:manifest:{index}", "Texture manifest entry must be an object.", str(path))
                continue
            relative = entry.get("path")
            if not relative:
                self._error(result, f"textures:manifest:{index}:path", "Texture manifest entry missing path.", str(path))
                continue
            texture_path = workspace / str(relative)
            resolved = texture_path.resolve()
            if workspace not in resolved.parents and resolved != workspace:
                self._error(result, f"textures:manifest:{index}:path_escape", f"Texture manifest path escapes workspace: {relative}", str(texture_path))
                continue
            self._check_path(result, f"textures:manifest:{index}:file", texture_path, required=True)
            if texture_path.exists():
                self._audit_png_texture(result, f"textures:manifest:{index}:png", texture_path)

    def _audit_resource_quality_report(self, result: AuditResult, workspace: Path, summary: dict) -> None:
        path = self.config.agent_dir_for(workspace) / "resource-quality-report.json"
        generated_files = summary.get("generated_files", []) if isinstance(summary, dict) else []
        required = ".agent\\resource-quality-report.json" in generated_files or ".agent/resource-quality-report.json" in generated_files
        self._check_path(result, "resources:quality_report", path, required=required, warning=not required)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, "resources:quality_report:json", f"resource-quality-report.json is invalid JSON: {exc}", str(path))
            return
        self._check(result, "resources:quality_report:version", data.get("version") == 8, str(path), None if data.get("version") == 8 else "resource-quality-report.json must use V8 schema version.")
        summary_payload = data.get("summary")
        self._check(result, "resources:quality_report:summary", isinstance(summary_payload, dict), str(path), None if isinstance(summary_payload, dict) else "resource-quality-report.json missing summary object.")
        texture_profiles = data.get("texture_profiles")
        self._check(result, "resources:quality_report:texture_profiles", isinstance(texture_profiles, list), str(path), None if isinstance(texture_profiles, list) else "resource-quality-report.json missing texture_profiles array.")
        model_variants = data.get("model_variants")
        self._check(result, "resources:quality_report:model_variants", isinstance(model_variants, list), str(path), None if isinstance(model_variants, list) else "resource-quality-report.json missing model_variants array.")
        preview_artifacts = data.get("preview_artifacts")
        self._check(result, "resources:quality_report:preview_artifacts", isinstance(preview_artifacts, dict), str(path), None if isinstance(preview_artifacts, dict) else "resource-quality-report.json missing preview_artifacts object.")
        if isinstance(preview_artifacts, dict):
            atlas = preview_artifacts.get("texture_atlas")
            if isinstance(atlas, dict) and atlas.get("path"):
                atlas_path = workspace / str(atlas["path"])
                if workspace not in atlas_path.resolve().parents and atlas_path.resolve() != workspace:
                    self._error(result, "resources:quality_report:atlas_path_escape", f"Texture atlas path escapes workspace: {atlas['path']}", str(atlas_path))
                else:
                    self._check_path(result, "resources:quality_report:atlas_file", atlas_path, required=True)
                    if atlas_path.exists():
                        self._audit_png_preview(result, "resources:quality_report:atlas_png", atlas_path)
        previews = data.get("structure_previews", [])
        if isinstance(previews, list):
            for index, preview in enumerate(previews):
                if not isinstance(preview, dict):
                    self._error(result, f"resources:quality_report:structure_preview:{index}", "Structure preview entry must be an object.", str(path))
                    continue
                relative = preview.get("path")
                if not relative:
                    self._error(result, f"resources:quality_report:structure_preview:{index}:path", "Structure preview entry missing path.", str(path))
                    continue
                preview_path = workspace / str(relative)
                if workspace not in preview_path.resolve().parents and preview_path.resolve() != workspace:
                    self._error(result, f"resources:quality_report:structure_preview:{index}:path_escape", f"Structure preview path escapes workspace: {relative}", str(preview_path))
                    continue
                self._check_path(result, f"resources:quality_report:structure_preview:{index}:file", preview_path, required=True)
                if preview_path.exists():
                    self._audit_png_preview(result, f"resources:quality_report:structure_preview:{index}:png", preview_path)

    def _check_texture(self, result: AuditResult, workspace: Path, spec: ModSpec, texture_dir: str, identifier: str) -> None:
        path = workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "textures" / texture_dir / f"{identifier}.png"
        self._check_path(result, f"{texture_dir}:{identifier}:texture", path, required=True)
        if path.exists():
            self._audit_png_texture(result, f"{texture_dir}:{identifier}:texture_png", path)

    def _check_item_definition(self, result: AuditResult, workspace: Path, spec: ModSpec, identifier: str) -> None:
        path = workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "items" / f"{identifier}.json"
        self._check_path(result, f"item:{identifier}:definition", path, required=True)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._error(result, f"item:{identifier}:definition_json", f"Item definition JSON is invalid: {exc}", str(path))
            return
        model = data.get("model")
        ok = isinstance(model, dict) and model.get("type") == "minecraft:model" and isinstance(model.get("model"), str)
        self._check(
            result,
            f"item:{identifier}:definition_model",
            ok,
            str(path),
            None if ok else "Item definition must contain model.type=minecraft:model and a model path.",
        )

    def _audit_png_texture(self, result: AuditResult, check_id: str, path: Path) -> None:
        data = path.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            self._check(result, check_id, False, str(path), "Texture is not a PNG file.")
            return
        if len(data) < 33:
            self._check(result, check_id, False, str(path), "Texture PNG is truncated.")
            return
        ihdr_length = struct.unpack(">I", data[8:12])[0]
        ihdr_kind = data[12:16]
        if ihdr_length != 13 or ihdr_kind != b"IHDR":
            self._check(result, check_id, False, str(path), "Texture PNG missing IHDR chunk.")
            return
        width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", data[16:29])
        ok = (
            width == 16
            and height == 16
            and bit_depth == 8
            and color_type == 6
            and compression == 0
            and filter_method == 0
            and interlace == 0
        )
        message = None if ok else f"Expected 16x16 RGBA PNG, got {width}x{height}, bit_depth={bit_depth}, color_type={color_type}."
        self._check(result, check_id, ok, str(path), message)

    def _audit_png_preview(self, result: AuditResult, check_id: str, path: Path) -> None:
        data = path.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            self._check(result, check_id, False, str(path), "Preview is not a PNG file.")
            return
        if len(data) < 33:
            self._check(result, check_id, False, str(path), "Preview PNG is truncated.")
            return
        ihdr_length = struct.unpack(">I", data[8:12])[0]
        ihdr_kind = data[12:16]
        if ihdr_length != 13 or ihdr_kind != b"IHDR":
            self._check(result, check_id, False, str(path), "Preview PNG missing IHDR chunk.")
            return
        width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", data[16:29])
        ok = (
            width > 0
            and height > 0
            and bit_depth == 8
            and color_type == 6
            and compression == 0
            and filter_method == 0
            and interlace == 0
        )
        message = None if ok else f"Expected RGBA PNG preview, got {width}x{height}, bit_depth={bit_depth}, color_type={color_type}."
        self._check(result, check_id, ok, str(path), message)

    def _error(self, result: AuditResult, issue_id: str, message: str, path: str | None = None) -> None:
        result.errors.append(AuditIssue(id=issue_id, severity="error", message=message, path=path))
        result.checks.append(AuditCheck(id=issue_id, status="fail", path=path, message=message))

    def _write_report_json(self, workspace: Path, result: AuditResult) -> Path:
        path = self.config.agent_dir_for(workspace) / "audit-report.json"
        path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def _write_report_md(self, workspace: Path, result: AuditResult) -> Path:
        path = self.config.agent_dir_for(workspace) / "audit-report.md"
        lines = [
            "# Audit Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Errors: {len(result.errors)}",
            f"Warnings: {len(result.warnings)}",
            f"Checks: {len(result.checks)}",
            "",
        ]
        if result.errors:
            lines.extend(["## Errors", ""])
            for issue in result.errors:
                lines.append(f"- `{issue.id}`: {issue.message}")
            lines.append("")
        if result.warnings:
            lines.extend(["## Warnings", ""])
            for issue in result.warnings:
                lines.append(f"- `{issue.id}`: {issue.message}")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path


def audit_workspace(workspace: Path, config: AppConfig | None = None) -> AuditResult:
    return WorkspaceAuditor(config).audit_workspace(workspace)
