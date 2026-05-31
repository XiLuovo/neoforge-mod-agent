from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

from .asset_generator import AssetGenerator
from .balance_generator import BalancePlanGenerator
from .behavior_report import BehaviorReportGenerator
from .builder import GradleBuilder
from .code_generator import CodeGenerator
from .config import AppConfig
from .java_extension_generator import finalize_java_extension_acceptance
from .models import (
    BlockSpec,
    BuildResult,
    ArmorSpec,
    BalancePlanSpec,
    BehaviorActionSpec,
    BehaviorConditionSpec,
    BehaviorEventSpec,
    FoodSpec,
    EntityAttackSpec,
    EntityAttributeSpec,
    EntityDropSpec,
    EntityGoalSpec,
    EntitySpawnSpec,
    EntitySpec,
    GenerationResult,
    FoodEffectSpec,
    ItemBehaviorSpec,
    ItemSpec,
    JavaExtensionMethodSpec,
    JavaExtensionSpec,
    MachineSpec,
    ModSpec,
    OnHitBehaviorSpec,
    OreSpec,
    PlanStep,
    ProgressionLinkSpec,
    ProgressionSpec,
    ProgressionStageSpec,
    QuestSpec,
    RecipeSpec,
    RequestOverrides,
    StepStatus,
    SwordSpec,
    ToolSpec,
    ValidationReport,
    LootEntrySpec,
    LootPoolSpec,
    WorldBiomeSpec,
    WorldDimensionSpec,
    WorldFeatureSpec,
    WorldStructureSpec,
)
from .project_generator import ProjectGenerator
from .progression_generator import ProgressionGenerator
from .quest_generator import QuestGuideGenerator
from .tools import (
    copy_template_tree,
    derive_display_name,
    derive_package_name,
    prepare_workspace_dir,
    slugify_mod_id,
    write_generation_summary,
    write_manual_test_checklist,
    write_modspec_snapshot,
    write_pending_work_note,
)
from .validator import validate_generated_project, validate_mod_spec
from .worldgen_generator import WorldgenGenerator


class ModProjectPlanner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()
        self.project_generator = ProjectGenerator(self.config)
        self.code_generator = CodeGenerator()
        self.asset_generator = AssetGenerator()
        self.worldgen_generator = WorldgenGenerator()
        self.progression_generator = ProgressionGenerator()
        self.behavior_report_generator = BehaviorReportGenerator()
        self.balance_plan_generator = BalancePlanGenerator()
        self.quest_guide_generator = QuestGuideGenerator()
        self.builder = GradleBuilder(self.config)

    def parse_request(
        self,
        request: str,
        overrides: RequestOverrides | None = None,
    ) -> ModSpec:
        overrides = overrides or RequestOverrides()
        request = request.strip()

        mod_id = overrides.mod_id or self._extract_mod_id(request)
        display_name = overrides.display_name or self._extract_display_name(request, mod_id)
        package_name = overrides.package_name or self._extract_package_name(request, mod_id)
        version = overrides.version or self._extract_version(request) or self.config.default_mod_version
        description = overrides.description or request
        authors = overrides.authors or self._extract_authors(request)
        license_name = overrides.license_name or self._extract_license_name(request) or self.config.default_license_name

        items = self._extract_item_specs(request)
        blocks = self._extract_block_specs(request)
        machines = self._extract_machine_specs(request)
        entities = self._extract_entity_specs(request)
        dimensions = self._extract_dimension_specs(request)
        biomes = self._extract_biome_specs(request)
        world_features = self._extract_world_feature_specs(request, mod_id)
        structures = self._extract_structure_specs(request, mod_id)
        loot_pools = self._extract_loot_pool_specs(request)
        java_extensions = self._extract_java_extension_specs(request)
        ores = self._extract_ore_specs(request, mod_id)
        foods = self._extract_food_specs(request)
        swords = self._extract_sword_specs(request)
        tools = self._extract_tool_specs(request)
        armors = self._extract_armor_specs(request)
        if self._needs_ruby_material_item(request, swords, tools, armors) and not any(item.identifier == "ruby" for item in items):
            items.append(self._make_ruby_item())
        recipes = self._extract_recipe_specs(request, mod_id, items, blocks, machines, swords, tools, armors)
        progressions: list[ProgressionSpec] = []
        if self._has_progression_hint(request) or self._has_balance_hint(request) or self._has_quest_hint(request):
            self._ensure_progression_scaffold(
                mod_id,
                items=items,
                ores=ores,
                machines=machines,
                swords=swords,
                entities=entities,
                dimensions=dimensions,
                biomes=biomes,
                world_features=world_features,
                structures=structures,
                loot_pools=loot_pools,
                recipes=recipes,
            )
            progressions = self._make_progression_specs(mod_id)
        balance_plans = self._make_balance_plan_specs() if self._has_balance_hint(request) else []
        quests = self._make_quest_specs() if self._has_quest_hint(request) else []

        requested_features = self._derive_requested_features(
            request,
            items,
            blocks,
            machines,
            entities,
            dimensions,
            biomes,
            world_features,
            structures,
            loot_pools,
            java_extensions,
            ores,
            foods,
            swords,
            tools,
            armors,
            recipes,
            progressions,
            balance_plans,
            quests,
        )
        extra_notes = []
        if not any([items, blocks, machines, entities, dimensions, biomes, world_features, structures, loot_pools, java_extensions, ores, foods, swords, tools, armors]):
            extra_notes.append("No concrete generated content features were detected in the natural language request.")

        return ModSpec(
            raw_request=request,
            mod_id=mod_id,
            display_name=display_name,
            package_name=package_name,
            version=version,
            description=description,
            authors=authors,
            license_name=license_name,
            loader=self.config.loader,
            neo_version=self.config.neo_version,
            java_version=self.config.java_version,
            items=items,
            blocks=blocks,
            machines=machines,
            entities=entities,
            dimensions=dimensions,
            biomes=biomes,
            world_features=world_features,
            structures=structures,
            loot_pools=loot_pools,
            java_extensions=java_extensions,
            ores=ores,
            foods=foods,
            swords=swords,
            tools=tools,
            armors=armors,
            recipes=recipes,
            progressions=progressions,
            balance_plans=balance_plans,
            quests=quests,
            requested_features=requested_features,
            extra_notes=extra_notes,
        )

    def spec_from_file(self, path: Path) -> ModSpec:
        data = json.loads(path.read_text(encoding="utf-8"))
        spec = ModSpec.from_dict(data)
        if not spec.raw_request:
            spec.raw_request = f"Loaded from spec file: {path.name}"
        if not spec.loader:
            spec.loader = self.config.loader
        if not spec.neo_version:
            spec.neo_version = self.config.neo_version
        if not spec.java_version:
            spec.java_version = self.config.java_version
        return spec

    def build_plan(self, run_build: bool) -> list[PlanStep]:
        steps = [
            PlanStep(name="Parse request", status=StepStatus.PENDING),
            PlanStep(name="Validate ModSpec", status=StepStatus.PENDING),
            PlanStep(name="Copy NeoForge template", status=StepStatus.PENDING),
            PlanStep(name="Rewrite project metadata", status=StepStatus.PENDING),
            PlanStep(name="Generate Java sources", status=StepStatus.PENDING),
            PlanStep(name="Generate assets and data", status=StepStatus.PENDING),
            PlanStep(name="Persist agent metadata", status=StepStatus.PENDING),
            PlanStep(name="Validate generated project", status=StepStatus.PENDING),
        ]
        if run_build:
            steps.append(PlanStep(name="Run Gradle build", status=StepStatus.PENDING))
        else:
            steps.append(
                PlanStep(
                    name="Run Gradle build",
                    status=StepStatus.SKIPPED,
                    detail="Build disabled for this run.",
                )
            )
        return steps

    def validate(self, spec: ModSpec) -> ValidationReport:
        return validate_mod_spec(spec, self.config)

    def execute(
        self,
        request: str,
        overrides: RequestOverrides | None = None,
        *,
        workspace_name: str | None = None,
        overwrite: bool = False,
        run_build: bool = False,
    ) -> GenerationResult:
        spec = self.parse_request(request, overrides=overrides)
        return self.execute_spec(
            spec,
            workspace_name=workspace_name,
            overwrite=overwrite,
            run_build=run_build,
            parsed_from_request=True,
        )

    def execute_spec(
        self,
        spec: ModSpec,
        *,
        workspace_name: str | None = None,
        overwrite: bool = False,
        run_build: bool = False,
        parsed_from_request: bool = False,
    ) -> GenerationResult:
        steps = self.build_plan(run_build=run_build)
        parse_detail = f"Parsed mod_id={spec.mod_id}." if parsed_from_request else f"Loaded mod_id={spec.mod_id}."
        steps[0] = replace(steps[0], status=StepStatus.COMPLETED, detail=parse_detail)

        validation = self.validate(spec)
        if validation.is_valid:
            detail = "Validation passed."
            if validation.warnings:
                detail = f"Validation passed with {len(validation.warnings)} warning(s)."
            steps[1] = replace(steps[1], status=StepStatus.COMPLETED, detail=detail)
        else:
            errors = "; ".join(issue.message for issue in validation.errors)
            steps[1] = replace(steps[1], status=StepStatus.FAILED, detail=errors)
            return GenerationResult(
                spec=spec,
                workspace_dir=self.config.workspace_root,
                steps=steps,
                validation=validation,
                warnings=[issue.message for issue in validation.warnings],
            )

        workspace_dir = prepare_workspace_dir(
            self.config,
            mod_id=spec.mod_id,
            workspace_name=workspace_name,
            overwrite=overwrite,
        )
        copy_template_tree(self.config.template_dir, workspace_dir)
        steps[2] = replace(steps[2], status=StepStatus.COMPLETED, detail=f"Template copied to {workspace_dir}.")

        layout = self.project_generator.generate(workspace_dir, spec)
        steps[3] = replace(
            steps[3],
            status=StepStatus.COMPLETED,
            detail="Updated package layout, gradle properties, mixin config, and mod metadata.",
        )

        java_files, code_warnings = self.code_generator.generate(layout, spec)
        java_source_count = sum(1 for path in java_files if path.suffix == ".java")
        steps[4] = replace(steps[4], status=StepStatus.COMPLETED, detail=f"Generated {java_source_count} Java source file(s).")

        asset_files = self.asset_generator.generate(layout, spec)
        worldgen_files = self.worldgen_generator.generate(layout.resources_dir, spec)
        progression_files = self.progression_generator.generate(workspace_dir, spec, self.config)
        behavior_files = self.behavior_report_generator.generate(workspace_dir, spec, self.config)
        balance_files = self.balance_plan_generator.generate(workspace_dir, spec, self.config)
        quest_files = self.quest_guide_generator.generate(workspace_dir, layout.resources_dir, spec, self.config)
        steps[5] = replace(
            steps[5],
            status=StepStatus.COMPLETED,
            detail=f"Generated {len(asset_files) + len(worldgen_files) + len(progression_files) + len(behavior_files) + len(balance_files) + len(quest_files)} asset/data/report file(s).",
        )

        metadata_path = write_modspec_snapshot(workspace_dir, spec, self.config)
        manual_test_checklist_path = write_manual_test_checklist(workspace_dir, self.config, spec)
        pending_actions = self._derive_pending_actions(spec)
        placeholder_note_path = write_pending_work_note(workspace_dir, self.config, pending_actions) if pending_actions else None
        fallbacks = [warning for warning in code_warnings if "falling back" in warning.lower()]
        pack_mcmeta_path = workspace_dir / "src" / "main" / "resources" / "pack.mcmeta"
        generated_files = [
            str(path.relative_to(workspace_dir))
            for path in [*java_files, *asset_files, *worldgen_files, *progression_files, *behavior_files, *balance_files, *quest_files, pack_mcmeta_path]
        ]
        write_generation_summary(
            workspace_dir,
            self.config,
            {
                "stage": "pre-build",
                "spec": spec.to_dict(),
                "features_count": self._feature_counts(spec),
                "generated_files": generated_files,
                "warnings": list(code_warnings),
                "fallbacks": list(fallbacks),
                "manual_test_checklist_path": str(manual_test_checklist_path),
            },
        )
        steps[6] = replace(
            steps[6],
            status=StepStatus.COMPLETED,
            detail=f"Saved ModSpec snapshot to {metadata_path}.",
        )

        project_warnings = validate_generated_project(workspace_dir, spec)
        if project_warnings:
            steps[7] = replace(
                steps[7],
                status=StepStatus.COMPLETED,
                detail=f"Project validation reported {len(project_warnings)} warning(s).",
            )
        else:
            steps[7] = replace(steps[7], status=StepStatus.COMPLETED, detail="Project validation passed.")

        warnings = [issue.message for issue in validation.warnings]
        warnings.extend(code_warnings)
        warnings.extend(project_warnings)

        build_result = (
            self.builder.build(workspace_dir)
            if run_build
            else BuildResult(attempted=False, success=None, summary="Gradle build was not executed.")
        )

        if run_build:
            status = StepStatus.COMPLETED if build_result.success else StepStatus.FAILED
            steps[8] = replace(steps[8], status=status, detail=build_result.summary)
        else:
            steps[8] = replace(steps[8], status=StepStatus.SKIPPED, detail="Build disabled for this run.")

        acceptance_files = finalize_java_extension_acceptance(workspace_dir, self.config, spec, build_result)
        for path in acceptance_files:
            relative = str(path.relative_to(workspace_dir))
            if relative not in generated_files:
                generated_files.append(relative)

        result = GenerationResult(
            spec=spec,
            workspace_dir=workspace_dir,
            steps=steps,
            validation=validation,
            build=build_result,
            metadata_path=metadata_path,
            placeholder_note_path=placeholder_note_path,
            manual_test_checklist_path=manual_test_checklist_path,
            pending_actions=pending_actions,
            warnings=warnings,
            fallbacks=fallbacks,
            generated_files=generated_files,
        )
        write_generation_summary(workspace_dir, self.config, result.to_dict())
        return result

    def _extract_mod_id(self, request: str) -> str:
        explicit = self._search(
            [r"(?:mod[\s_-]?id|modid|模组\s*id|模组标识)\s*[:：=]\s*([A-Za-z0-9_]+)"],
            request,
        )
        if explicit:
            return slugify_mod_id(explicit, fallback="generated_mod")
        if self._has_ruby_hint(request):
            return "ruby_mod"
        if self._has_machine_hint(request):
            return "machine_mod"
        if self._has_java_extension_hint(request):
            return "extension_mod"
        quoted_name = self._extract_quoted_phrase(request)
        if quoted_name:
            return slugify_mod_id(quoted_name, fallback="generated_mod")
        return slugify_mod_id(request, fallback="generated_mod")

    def _extract_display_name(self, request: str, mod_id: str) -> str:
        explicit = self._search([r"(?:display\s+name|name|名称|模组名)\s*[:：=]\s*([^\n;,]+)"], request)
        if explicit:
            return explicit.strip().strip("\"' ")
        if self._has_ruby_hint(request):
            return "Ruby Mod"
        if self._has_java_extension_hint(request):
            return "Extension Mod"
        quoted_name = self._extract_quoted_phrase(request)
        if quoted_name:
            return quoted_name.strip()
        return derive_display_name(mod_id)

    def _extract_package_name(self, request: str, mod_id: str) -> str:
        explicit = self._search([r"(?:package(?:\s+name)?|包名)\s*[:：=]\s*([A-Za-z_][A-Za-z0-9_.]*)"], request)
        if explicit:
            return explicit.strip()
        return derive_package_name(mod_id, base_package=self.config.default_group_prefix)

    def _extract_version(self, request: str) -> str | None:
        return self._search([r"(?:version|版本)\s*[:：=]?\s*([0-9A-Za-z_.-]+)"], request)

    def _extract_authors(self, request: str) -> list[str]:
        explicit = self._search([r"(?:authors?|作者)\s*[:：=]\s*([^\n;]+)"], request)
        if not explicit:
            return []
        return [part.strip() for part in re.split(r"[,，/]+", explicit) if part.strip()]

    def _extract_license_name(self, request: str) -> str | None:
        return self._search([r"(?:license|许可|协议)\s*[:：=]\s*([^\n;,]+)"], request)

    def _extract_item_specs(self, request: str) -> list[ItemSpec]:
        explicit = self._extract_named_specs(request, ["items?", "物品"], self._make_generic_item)
        if explicit:
            return explicit

        specs: list[ItemSpec] = []
        behavior_item = self._extract_behavior_item_spec(request)
        if behavior_item is not None:
            specs.append(behavior_item)
        if self._should_add_ruby_base_item(request):
            specs.append(self._make_ruby_item())
        return specs

    def _extract_block_specs(self, request: str) -> list[BlockSpec]:
        explicit = self._extract_named_specs(request, ["blocks?", "方块"], self._make_generic_block)
        if explicit:
            return explicit

        specs: list[BlockSpec] = []
        variant_kinds = self._ruby_block_variant_kinds(request)
        behavior_block = self._extract_behavior_block_spec(request)
        if behavior_block is not None:
            specs.append(behavior_block)
        if self._mentions_any(request, ["红宝石方块", "ruby block"]) or variant_kinds:
            specs.append(self._make_ruby_block())
        for block_kind in variant_kinds:
            specs.append(self._make_ruby_block_variant(block_kind))
        return specs

    def _extract_machine_specs(self, request: str) -> list[MachineSpec]:
        explicit = self._extract_named_specs(request, ["machines?", "machine", "机器", "机器方块"], self._make_generic_machine)
        if explicit:
            return explicit

        specs: list[MachineSpec] = []
        lowered = request.lower()
        english_tokens = (
            "ruby compressor",
            "compressor",
            "machine",
            "furnace machine",
            "upgrade table",
            "magic altar",
            "storage block",
        )
        chinese_tokens = ("机器", "压缩机", "熔炉", "升级台", "魔法祭坛", "祭坛", "储物方块", "储物", "容器")
        if any(token in lowered for token in english_tokens) or any(token in request for token in chinese_tokens):
            specs.append(self._make_ruby_machine(request))
        return specs

    def _extract_entity_specs(self, request: str) -> list[EntitySpec]:
        explicit = self._extract_named_specs(
            request,
            ["entities?", "entity", "mobs?", "mob", "creatures?", "creature"],
            self._make_generic_entity,
        )
        if explicit:
            return explicit

        lowered = request.lower()
        entity_tokens = (
            "mob",
            "entity",
            "monster",
            "creature",
            "pet",
            "boss",
            "npc",
            "goblin",
        )
        if any(token in lowered for token in entity_tokens):
            if "ruby" in lowered or "goblin" in lowered:
                return [self._make_ruby_goblin_entity(request)]
            return [self._make_generic_entity("generated_mob")]
        return []

    def _extract_dimension_specs(self, request: str) -> list[WorldDimensionSpec]:
        explicit = self._extract_named_specs(request, ["dimensions?", "dimension"], self._make_generic_dimension)
        if explicit:
            return explicit
        if self._has_world_structure_hint(request):
            return [self._make_ruby_realm_dimension()]
        return []

    def _extract_biome_specs(self, request: str) -> list[WorldBiomeSpec]:
        explicit = self._extract_named_specs(request, ["biomes?", "biome"], self._make_generic_biome)
        if explicit:
            return explicit
        if self._has_world_structure_hint(request):
            return [self._make_ruby_fields_biome()]
        return []

    def _extract_world_feature_specs(self, request: str, mod_id: str) -> list[WorldFeatureSpec]:
        explicit = self._extract_named_specs(
            request,
            ["world[_\\s-]?features?", "worldgen[_\\s-]?features?", "veins?"],
            self._make_generic_world_feature,
        )
        if explicit:
            return explicit
        if self._has_world_structure_hint(request):
            return [self._make_ruby_vein_world_feature(mod_id)]
        return []

    def _extract_structure_specs(self, request: str, mod_id: str) -> list[WorldStructureSpec]:
        explicit = self._extract_named_specs(request, ["structures?", "structure"], lambda token: self._make_generic_structure(token, mod_id))
        if explicit:
            return explicit
        if self._has_world_structure_hint(request):
            return [self._make_ruby_shrine_structure(mod_id)]
        return []

    def _extract_loot_pool_specs(self, request: str) -> list[LootPoolSpec]:
        explicit = self._extract_named_specs(request, ["loot[_\\s-]?pools?", "loot"], self._make_generic_loot_pool)
        if explicit:
            return explicit
        if self._has_world_structure_hint(request):
            return [self._make_ruby_shrine_loot_pool()]
        return []

    def _extract_java_extension_specs(self, request: str) -> list[JavaExtensionSpec]:
        if not self._has_java_extension_hint(request):
            return []
        return [self._make_safe_info_extension()]

    def _extract_ore_specs(self, request: str, mod_id: str) -> list[OreSpec]:
        explicit = self._extract_named_specs(request, ["ores?", "矿石"], self._make_generic_ore)
        if explicit:
            return explicit

        specs: list[OreSpec] = []
        if self._mentions_any(request, ["红宝石矿石", "ruby ore"]):
            drop = f"{mod_id}:ruby" if self._mentions_any(request, ["掉落红宝石", "drop ruby", "掉落 ruby"]) else f"{mod_id}:ruby"
            specs.append(self._make_ruby_ore(drop, request))
        return specs

    def _extract_food_specs(self, request: str) -> list[FoodSpec]:
        explicit = self._extract_named_specs(request, ["foods?", "食物"], self._make_generic_food)
        if explicit:
            return explicit

        specs: list[FoodSpec] = []
        if self._mentions_any(request, ["红宝石苹果", "ruby apple"]):
            specs.append(self._make_ruby_apple(request))
        return specs

    def _extract_sword_specs(self, request: str) -> list[SwordSpec]:
        explicit = self._extract_named_specs(request, ["swords?", "剑"], self._make_generic_sword)
        if explicit:
            return explicit

        specs: list[SwordSpec] = []
        if self._is_ruby_tool_set_request(request) or self._mentions_any(request, ["红宝石剑", "ruby sword"]):
            specs.append(self._make_ruby_sword(request))
        return specs

    def _extract_tool_specs(self, request: str) -> list[ToolSpec]:
        explicit = self._extract_named_specs(request, ["tools?", "工具"], self._make_generic_tool)
        if explicit:
            return explicit

        specs: list[ToolSpec] = []
        lowered = request.lower()
        if self._is_ruby_tool_set_request(request):
            return [self._make_ruby_tool(tool_type) for tool_type in ("pickaxe", "axe", "shovel", "hoe")]

        checks = [
            ("pickaxe", ["红宝石镐", "红宝石稿", "ruby pickaxe"]),
            ("axe", ["红宝石斧", "ruby axe"]),
            ("shovel", ["红宝石铲", "ruby shovel"]),
            ("hoe", ["红宝石锄", "红宝石锄头", "ruby hoe"]),
        ]
        for tool_type, tokens in checks:
            if self._mentions_any(request, tokens):
                specs.append(self._make_ruby_tool(tool_type))
        return specs

    def _extract_armor_specs(self, request: str) -> list[ArmorSpec]:
        explicit = self._extract_named_specs(request, ["armors?", "armor", "护甲"], self._make_generic_armor)
        if explicit:
            return explicit

        specs: list[ArmorSpec] = []
        lowered = request.lower()
        if self._is_ruby_armor_set_request(request):
            return [self._make_ruby_armor(armor_type) for armor_type in ("helmet", "chestplate", "leggings", "boots")]

        checks = [
            ("helmet", ["红宝石头盔", "ruby helmet"]),
            ("chestplate", ["红宝石胸甲", "ruby chestplate"]),
            ("leggings", ["红宝石护腿", "ruby leggings"]),
            ("boots", ["红宝石靴子", "红宝石靴", "ruby boots"]),
        ]
        for armor_type, tokens in checks:
            if self._mentions_any(request, tokens):
                specs.append(self._make_ruby_armor(armor_type))
        return specs

    def _extract_recipe_specs(
        self,
        request: str,
        mod_id: str,
        items: list[ItemSpec],
        blocks: list[BlockSpec],
        machines: list[MachineSpec],
        swords: list[SwordSpec],
        tools: list[ToolSpec],
        armors: list[ArmorSpec],
    ) -> list[RecipeSpec]:
        recipes: list[RecipeSpec] = []
        ruby_item = next((item for item in items if item.identifier == "ruby"), None)
        ruby_block = next((block for block in blocks if block.identifier == "ruby_block"), None)

        has_recipe_hint = self._mentions_any(request, ["合成", "craft", "recipe"])
        has_ruby_block_recipe = self._mentions_any(request, ["九个红宝石", "9个红宝石", "9 ruby", "nine ruby"])
        if ruby_item and ruby_block and (has_recipe_hint or has_ruby_block_recipe):
            recipes.append(
                RecipeSpec(
                    identifier="ruby_block",
                    recipe_type="shaped",
                    pattern=["RRR", "RRR", "RRR"],
                    keys={"R": f"{mod_id}:ruby"},
                    result=f"{mod_id}:ruby_block",
                    count=1,
                )
            )
        if ruby_item and ruby_block and any(block.block_kind != "cube" for block in blocks) and not any(recipe.identifier == "ruby_block" for recipe in recipes):
            recipes.append(
                RecipeSpec(
                    identifier="ruby_block",
                    recipe_type="shaped",
                    pattern=["RRR", "RRR", "RRR"],
                    keys={"R": f"{mod_id}:ruby"},
                    result=f"{mod_id}:ruby_block",
                    count=1,
                    category="building",
                    group="ruby_block_variants",
                )
            )

        has_unmake_hint = self._mentions_any(
            request,
            ["分解成九个红宝石", "拆成九个红宝石", "分解成 9 个红宝石", "9 ruby", "nine ruby", "unpack"],
        )
        if ruby_item and ruby_block and has_unmake_hint:
            recipes.append(
                RecipeSpec(
                    identifier="ruby_from_ruby_block",
                    recipe_type="shapeless",
                    ingredients=[f"{mod_id}:ruby_block"],
                    result=f"{mod_id}:ruby",
                    count=9,
                )
            )
        if ruby_item is not None:
            for recipe in self._ruby_equipment_recipes(mod_id, swords, tools, armors):
                if not any(existing.identifier == recipe.identifier for existing in recipes):
                    recipes.append(recipe)
        for recipe in self._ruby_block_variant_recipes(mod_id, blocks):
            if not any(existing.identifier == recipe.identifier for existing in recipes):
                recipes.append(recipe)
        for recipe in self._machine_recipes(request, mod_id, items, machines):
            if not any(existing.identifier == recipe.identifier for existing in recipes):
                recipes.append(recipe)
        return recipes

    def _machine_recipes(
        self,
        request: str,
        mod_id: str,
        items: list[ItemSpec],
        machines: list[MachineSpec],
    ) -> list[RecipeSpec]:
        if not machines or not self._mentions_any(request, ["craft", "recipe", "鍚堟垚"]):
            return []
        material = f"{mod_id}:ruby" if any(item.identifier == "ruby" for item in items) else "minecraft:redstone"
        recipes: list[RecipeSpec] = []
        for machine in machines:
            recipes.append(
                RecipeSpec(
                    identifier=machine.identifier,
                    recipe_type="shaped",
                    pattern=["IRI", "R R", "IRI"],
                    keys={"I": "minecraft:iron_ingot", "R": material},
                    result=f"{mod_id}:{machine.identifier}",
                    count=1,
                    category="redstone",
                    group="machines",
                )
            )
        return recipes

    def _ruby_block_variant_recipes(self, mod_id: str, blocks: list[BlockSpec]) -> list[RecipeSpec]:
        block_ids = {block.identifier for block in blocks}
        if "ruby_block" not in block_ids:
            return []
        material = f"{mod_id}:ruby_block"
        stick = "minecraft:stick"
        recipes_by_id = {
            "ruby_stairs": RecipeSpec(
                identifier="ruby_stairs",
                recipe_type="shaped",
                pattern=["R  ", "RR ", "RRR"],
                keys={"R": material},
                result=f"{mod_id}:ruby_stairs",
                count=4,
                category="building",
                group="ruby_block_variants",
            ),
            "ruby_slab": RecipeSpec(
                identifier="ruby_slab",
                recipe_type="shaped",
                pattern=["RRR"],
                keys={"R": material},
                result=f"{mod_id}:ruby_slab",
                count=6,
                category="building",
                group="ruby_block_variants",
            ),
            "ruby_wall": RecipeSpec(
                identifier="ruby_wall",
                recipe_type="shaped",
                pattern=["RRR", "RRR"],
                keys={"R": material},
                result=f"{mod_id}:ruby_wall",
                count=6,
                category="building",
                group="ruby_block_variants",
            ),
            "ruby_button": RecipeSpec(
                identifier="ruby_button",
                recipe_type="shapeless",
                ingredients=[material],
                result=f"{mod_id}:ruby_button",
                count=1,
                category="redstone",
                group="ruby_block_variants",
            ),
            "ruby_pressure_plate": RecipeSpec(
                identifier="ruby_pressure_plate",
                recipe_type="shaped",
                pattern=["RR"],
                keys={"R": material},
                result=f"{mod_id}:ruby_pressure_plate",
                count=1,
                category="redstone",
                group="ruby_block_variants",
            ),
            "ruby_fence": RecipeSpec(
                identifier="ruby_fence",
                recipe_type="shaped",
                pattern=["RSR", "RSR"],
                keys={"R": material, "S": stick},
                result=f"{mod_id}:ruby_fence",
                count=3,
                category="building",
                group="ruby_block_variants",
            ),
            "ruby_fence_gate": RecipeSpec(
                identifier="ruby_fence_gate",
                recipe_type="shaped",
                pattern=["SRS", "SRS"],
                keys={"R": material, "S": stick},
                result=f"{mod_id}:ruby_fence_gate",
                count=1,
                category="redstone",
                group="ruby_block_variants",
            ),
            "ruby_door": RecipeSpec(
                identifier="ruby_door",
                recipe_type="shaped",
                pattern=["RR", "RR", "RR"],
                keys={"R": material},
                result=f"{mod_id}:ruby_door",
                count=3,
                category="redstone",
                group="ruby_block_variants",
            ),
            "ruby_trapdoor": RecipeSpec(
                identifier="ruby_trapdoor",
                recipe_type="shaped",
                pattern=["RRR", "RRR"],
                keys={"R": material},
                result=f"{mod_id}:ruby_trapdoor",
                count=2,
                category="redstone",
                group="ruby_block_variants",
            ),
        }
        return [recipes_by_id[block.identifier] for block in blocks if block.identifier in recipes_by_id]

    def _ruby_equipment_recipes(
        self,
        mod_id: str,
        swords: list[SwordSpec],
        tools: list[ToolSpec],
        armors: list[ArmorSpec],
    ) -> list[RecipeSpec]:
        material = f"{mod_id}:ruby"
        stick = "minecraft:stick"
        recipes: list[RecipeSpec] = []
        patterns = {
            "ruby_sword": (["R", "R", "S"], {"R": material, "S": stick}),
            "ruby_pickaxe": (["RRR", " S ", " S "], {"R": material, "S": stick}),
            "ruby_axe": (["RR ", "RS ", " S "], {"R": material, "S": stick}),
            "ruby_shovel": (["R", "S", "S"], {"R": material, "S": stick}),
            "ruby_hoe": (["RR ", " S ", " S "], {"R": material, "S": stick}),
            "ruby_helmet": (["RRR", "R R"], {"R": material}),
            "ruby_chestplate": (["R R", "RRR", "RRR"], {"R": material}),
            "ruby_leggings": (["RRR", "R R", "R R"], {"R": material}),
            "ruby_boots": (["R R", "R R"], {"R": material}),
        }
        equipment_ids = {
            *(sword.identifier for sword in swords if sword.tool_material.lower() == "ruby"),
            *(tool.identifier for tool in tools if tool.tool_material.lower() == "ruby"),
            *(armor.identifier for armor in armors if armor.armor_material.lower() == "ruby"),
        }
        for identifier in sorted(equipment_ids):
            if identifier not in patterns:
                continue
            pattern, keys = patterns[identifier]
            recipes.append(
                RecipeSpec(
                    identifier=identifier,
                    recipe_type="shaped",
                    pattern=list(pattern),
                    keys=dict(keys),
                    result=f"{mod_id}:{identifier}",
                    count=1,
                    category="equipment",
                    group="ruby_equipment",
                )
            )
        return recipes

    def _derive_requested_features(
        self,
        request: str,
        items: list[ItemSpec],
        blocks: list[BlockSpec],
        machines: list[MachineSpec],
        entities: list[EntitySpec],
        dimensions: list[WorldDimensionSpec],
        biomes: list[WorldBiomeSpec],
        world_features: list[WorldFeatureSpec],
        structures: list[WorldStructureSpec],
        loot_pools: list[LootPoolSpec],
        java_extensions: list[JavaExtensionSpec],
        ores: list[OreSpec],
        foods: list[FoodSpec],
        swords: list[SwordSpec],
        tools: list[ToolSpec],
        armors: list[ArmorSpec],
        recipes: list[RecipeSpec],
        progressions: list[ProgressionSpec],
        balance_plans: list[BalancePlanSpec],
        quests: list[QuestSpec],
    ) -> list[str]:
        features: list[str] = []
        if items:
            features.append("Items")
        if blocks:
            features.append("Blocks")
        if machines:
            features.append("Machines")
            features.append("BlockEntity")
            features.append("GUI")
        if entities:
            features.append("Entities")
        if dimensions:
            features.append("Dimensions")
        if biomes:
            features.append("Biomes")
        if world_features:
            features.append("World Features")
            features.append("Worldgen")
        if structures:
            features.append("Structures")
        if loot_pools:
            features.append("Loot Pools")
        if java_extensions:
            features.append("Java Extensions")
        if ores:
            features.append("Ores")
        if foods:
            features.append("Foods")
        if swords:
            features.append("Swords")
        if tools:
            features.append("Tools")
        if armors:
            features.append("Armor")
        if recipes:
            features.append("Recipes")
        if progressions:
            features.append("Progression")
        if balance_plans:
            features.append("Balance Planner")
        if quests:
            features.append("Quests")
            features.append("Advancements")
            features.append("Guidebook")

        keyword_map = {
            "config": "Config",
            "配置": "Config",
            "entity": "Entity",
            "实体": "Entity",
            "gui": "GUI",
            "screen": "GUI",
            "界面": "GUI",
            "worldgen": "Worldgen",
            "dimension": "Dimensions",
            "biome": "Biomes",
            "structure": "Structures",
            "world feature": "World Features",
            "loot pool": "Loot Pools",
            "java extension": "Java Extensions",
            "controlled java extension": "Java Extensions",
            "受控 java 扩展": "Java Extensions",
            "受控 Java 扩展": "Java Extensions",
            "vein": "World Features",
            "维度": "Dimensions",
            "群系": "Biomes",
            "结构": "Structures",
            "地物": "World Features",
            "战利品池": "Loot Pools",
            "世界生成": "Worldgen",
            "progression": "Progression",
            "gameplay loop": "Progression",
            "玩法线": "Progression",
            "成长路线": "Progression",
            "维度推进": "Progression",
            "balance": "Balance Planner",
            "economy": "Balance Planner",
            "rarity": "Balance Planner",
            "machine cost": "Balance Planner",
            "经济": "Balance Planner",
            "平衡": "Balance Planner",
            "稀有度": "Balance Planner",
            "机器耗时": "Balance Planner",
            "能量消耗": "Balance Planner",
            "战利品权重": "Balance Planner",
            "quest": "Quests",
            "quests": "Quests",
            "questline": "Quests",
            "advancement": "Advancements",
            "advancements": "Advancements",
            "guidebook": "Guidebook",
            "guide book": "Guidebook",
            "patchouli": "Guidebook",
            "任务": "Quests",
            "任务链": "Quests",
            "成就": "Advancements",
            "引导": "Guidebook",
            "指南": "Guidebook",
        }
        lowered = request.lower()
        for token, label in keyword_map.items():
            haystack = lowered if token.isascii() else request
            if token in haystack and label not in features:
                features.append(label)
        return features

    def _derive_pending_actions(self, spec: ModSpec) -> list[str]:
        actions: list[str] = []
        unsupported_features = {
            "Config": "Config screen and config file generation are not implemented yet.",
            "Entity": "Entity code generation is not implemented yet.",
            "GUI": "Custom GUI generation is not implemented yet.",
        }
        for feature in spec.requested_features:
            if feature == "GUI" and spec.machines:
                continue
            if feature == "Entity" and spec.entities:
                continue
            if feature == "Entities":
                continue
            if feature in unsupported_features and unsupported_features[feature] not in actions:
                actions.append(unsupported_features[feature])
        return actions

    def _extract_named_specs(self, request: str, labels: list[str], factory):
        boundary = (
            r"(?=\s+(?:items?|物品|blocks?|方块|ores?|矿石|foods?|食物|swords?|剑|tools?|工具|armors?|armor|护甲|"
            r"mod[\s_-]?id|modid|package(?:\s+name)?|包名|version|版本|authors?|作者|license|许可|协议)\s*[:：=]|$)"
        )
        label_pattern = "|".join(labels)
        match = self._search([rf"(?:{label_pattern})\s*[:：]\s*(.+?){boundary}"], request)
        if not match:
            return []
        return [factory(part.strip()) for part in re.split(r"[,，、/]+", match) if part.strip()]

    def _make_generic_item(self, token: str) -> ItemSpec:
        identifier = slugify_mod_id(token, fallback="generated_item")
        return ItemSpec(identifier=identifier, display_name=self._english_label(token), display_name_zh_cn=self._zh_label(token))

    def _make_generic_block(self, token: str) -> BlockSpec:
        identifier = slugify_mod_id(token, fallback="generated_block")
        return BlockSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            strength=5.0,
            resistance=6.0,
            sound="stone",
            requires_correct_tool=True,
            tool_tier="iron",
        )

    def _make_generic_machine(self, token: str) -> MachineSpec:
        machine_kind = self._detect_machine_kind(token)
        identifier = slugify_mod_id(token, fallback=f"generated_{machine_kind}")
        return MachineSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            strength=4.0,
            resistance=6.0,
            sound="metal",
            requires_correct_tool=True,
            tool_tier="iron",
            machine_kind=machine_kind,
            inventory_slots=2 if machine_kind != "storage" else 9,
            input_slots=1 if machine_kind != "storage" else 9,
            output_slots=1 if machine_kind != "storage" else 0,
            energy_capacity=10000 if machine_kind != "storage" else 0,
            energy_per_tick=20 if machine_kind != "storage" else 0,
            max_progress=100 if machine_kind != "storage" else 1,
            menu_title=self._english_label(token),
        )

    def _make_generic_entity(self, token: str) -> EntitySpec:
        entity_kind = self._detect_entity_kind(token)
        identifier = slugify_mod_id(token, fallback=f"generated_{entity_kind}")
        return EntitySpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            entity_kind=entity_kind,
            category=self._entity_category(entity_kind),
            width=0.6,
            height=1.95,
            tracking_range=8,
            update_interval=3,
            xp_reward=5 if entity_kind in {"monster", "boss"} else 0,
            attributes=self._entity_attributes_for(entity_kind),
            drops=[],
            spawn=None,
            goals=[],
            attack=self._entity_attack_for(token, entity_kind),
        )

    def _make_generic_dimension(self, token: str) -> WorldDimensionSpec:
        identifier = slugify_mod_id(token, fallback="generated_dimension")
        return WorldDimensionSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            biome="minecraft:plains",
        )

    def _make_generic_biome(self, token: str) -> WorldBiomeSpec:
        identifier = slugify_mod_id(token, fallback="generated_biome")
        return WorldBiomeSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
        )

    def _make_generic_world_feature(self, token: str) -> WorldFeatureSpec:
        identifier = slugify_mod_id(token, fallback="generated_vein")
        return WorldFeatureSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            placed_block="minecraft:diamond_ore",
        )

    def _make_generic_structure(self, token: str, mod_id: str) -> WorldStructureSpec:
        identifier = slugify_mod_id(token, fallback="generated_structure")
        return WorldStructureSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
        )

    def _make_generic_loot_pool(self, token: str) -> LootPoolSpec:
        identifier = slugify_mod_id(token, fallback="generated_loot")
        return LootPoolSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            entries=[
                LootEntrySpec(item="minecraft:emerald", min_count=1, max_count=3, weight=2),
                LootEntrySpec(item="minecraft:diamond", min_count=1, max_count=1, weight=1, chance=0.35),
            ],
        )

    def _make_safe_info_extension(self) -> JavaExtensionSpec:
        return JavaExtensionSpec(
            identifier="safe_info_extension",
            display_name="Safe Info Extension",
            class_name="SafeInfoExtension",
            purpose="Expose a tiny compile-time helper that can be inspected without touching existing generated classes.",
            explanation="V6 renders this as an additive managed class under the extension package, with no raw Java patching.",
            allowed_imports=["net.minecraft.network.chat.Component"],
            methods=[
                JavaExtensionMethodSpec(
                    name="describe",
                    return_type="String",
                    return_value="Controlled Java extension generated from ModSpec.",
                    explanation="Returns a short explanation string for audit and demo use.",
                )
            ],
        )

    def _make_generic_ore(self, token: str) -> OreSpec:
        identifier = slugify_mod_id(token, fallback="generated_ore")
        return OreSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            strength=3.0,
            resistance=3.0,
            sound="stone",
            requires_correct_tool=True,
            tool_tier="iron",
            drop=None,
            worldgen=None,
        )

    def _make_generic_food(self, token: str) -> FoodSpec:
        identifier = slugify_mod_id(token, fallback="generated_food")
        return FoodSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            nutrition=6,
            saturation=0.8,
        )

    def _make_generic_sword(self, token: str) -> SwordSpec:
        identifier = slugify_mod_id(token, fallback="generated_sword")
        return SwordSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            attack_damage_bonus=4,
            attack_speed=-2.4,
        )

    def _make_generic_tool(self, token: str) -> ToolSpec:
        tool_type = self._detect_tool_type(token) or "pickaxe"
        identifier = slugify_mod_id(token, fallback=f"generated_{tool_type}")
        return ToolSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            tool_type=tool_type,
            tool_material="iron",
            attack_damage_bonus=self._tool_defaults(tool_type)[0],
            attack_speed=self._tool_defaults(tool_type)[1],
        )

    def _make_generic_armor(self, token: str) -> ArmorSpec:
        armor_type = self._detect_armor_type(token) or "helmet"
        identifier = slugify_mod_id(token, fallback=f"generated_{armor_type}")
        return ArmorSpec(
            identifier=identifier,
            display_name=self._english_label(token),
            display_name_zh_cn=self._zh_label(token),
            armor_type=armor_type,
            armor_material="iron",
        )

    def _make_ruby_item(self) -> ItemSpec:
        return ItemSpec(identifier="ruby", display_name="Ruby", display_name_zh_cn="红宝石")

    def _make_ruby_block(self) -> BlockSpec:
        return BlockSpec(
            identifier="ruby_block",
            display_name="Block of Ruby",
            display_name_zh_cn="红宝石方块",
            strength=5.0,
            resistance=6.0,
            sound="metal",
            requires_correct_tool=True,
        )

    def _make_ruby_block_variant(self, block_kind: str) -> BlockSpec:
        labels = {
            "stairs": ("ruby_stairs", "Ruby Stairs", "红宝石楼梯"),
            "slab": ("ruby_slab", "Ruby Slab", "红宝石台阶"),
            "wall": ("ruby_wall", "Ruby Wall", "红宝石墙"),
            "button": ("ruby_button", "Ruby Button", "红宝石按钮"),
            "pressure_plate": ("ruby_pressure_plate", "Ruby Pressure Plate", "红宝石压力板"),
            "fence": ("ruby_fence", "Ruby Fence", "红宝石栅栏"),
            "fence_gate": ("ruby_fence_gate", "Ruby Fence Gate", "红宝石栅栏门"),
            "door": ("ruby_door", "Ruby Door", "红宝石门"),
            "trapdoor": ("ruby_trapdoor", "Ruby Trapdoor", "红宝石活板门"),
        }
        identifier, display_name, display_name_zh = labels[block_kind]
        return BlockSpec(
            identifier=identifier,
            display_name=display_name,
            display_name_zh_cn=display_name_zh,
            strength=5.0,
            resistance=6.0,
            sound="metal",
            requires_correct_tool=True,
            tool_tier="iron",
            block_kind=block_kind,
            base_block="ruby_block",
        )

    def _make_ruby_machine(self, request: str) -> MachineSpec:
        machine_kind = self._detect_machine_kind(request)
        labels = {
            "furnace": ("ruby_furnace", "Ruby Furnace", "Ruby Furnace"),
            "compressor": ("ruby_compressor", "Ruby Compressor", "Ruby Compressor"),
            "upgrade_table": ("ruby_upgrade_table", "Ruby Upgrade Table", "Ruby Upgrade Table"),
            "magic_altar": ("ruby_altar", "Ruby Altar", "Ruby Altar"),
            "storage": ("ruby_storage_block", "Ruby Storage Block", "Ruby Storage Block"),
        }
        identifier, display_name, title = labels.get(machine_kind, labels["compressor"])
        storage = machine_kind == "storage"
        return MachineSpec(
            identifier=identifier,
            display_name=display_name,
            display_name_zh_cn="",
            strength=4.0,
            resistance=6.0,
            sound="metal",
            requires_correct_tool=True,
            tool_tier="iron",
            machine_kind=machine_kind,
            inventory_slots=9 if storage else 2,
            input_slots=9 if storage else 1,
            output_slots=0 if storage else 1,
            energy_capacity=0 if storage else 10000,
            energy_per_tick=0 if storage else 20,
            max_progress=1 if storage else 100,
            menu_title=title,
        )

    def _make_ruby_goblin_entity(self, request: str) -> EntitySpec:
        entity_kind = self._detect_entity_kind(request)
        if entity_kind == "creature":
            entity_kind = "monster"
        attributes = self._entity_attributes_for(entity_kind)
        attack = self._entity_attack_for(request, entity_kind)
        if attack and attack.damage is not None:
            attributes.attack_damage = attack.damage
        return EntitySpec(
            identifier="ruby_goblin",
            display_name="Ruby Goblin",
            display_name_zh_cn="",
            entity_kind=entity_kind,
            category=self._entity_category(entity_kind),
            width=0.6,
            height=1.35 if entity_kind != "boss" else 2.7,
            tracking_range=10 if entity_kind != "boss" else 12,
            update_interval=3,
            xp_reward=20 if entity_kind == "boss" else 5,
            fire_immune="fire" in request.lower(),
            attributes=attributes,
            drops=self._entity_drops_for(request),
            spawn=self._entity_spawn_for(request),
            goals=[],
            attack=attack,
        )

    def _make_ruby_realm_dimension(self) -> WorldDimensionSpec:
        return WorldDimensionSpec(
            identifier="ruby_realm",
            display_name="Ruby Realm",
            display_name_zh_cn="",
            biome="ruby_fields",
            ambient_light=0.15,
        )

    def _make_ruby_fields_biome(self) -> WorldBiomeSpec:
        return WorldBiomeSpec(
            identifier="ruby_fields",
            display_name="Ruby Fields",
            display_name_zh_cn="",
            temperature=0.9,
            downfall=0.25,
            sky_color=0xB86C8D,
            water_color=0xC24D6A,
            water_fog_color=0x7A243F,
            fog_color=0xD9A1B8,
            grass_color=0x8CCB72,
            foliage_color=0x6BBE69,
        )

    def _make_ruby_vein_world_feature(self, mod_id: str) -> WorldFeatureSpec:
        return WorldFeatureSpec(
            identifier="ruby_vein",
            display_name="Ruby Vein",
            display_name_zh_cn="",
            placed_block="minecraft:redstone_ore",
            biomes=f"{mod_id}:ruby_fields",
            vein_size=6,
            veins_per_chunk=5,
            min_y=-48,
            max_y=32,
        )

    def _make_ruby_shrine_structure(self, mod_id: str) -> WorldStructureSpec:
        return WorldStructureSpec(
            identifier="ruby_shrine",
            display_name="Ruby Shrine",
            display_name_zh_cn="",
            biomes=f"{mod_id}:ruby_fields",
            spacing=28,
            separation=8,
            salt=754321,
            size=1,
            start_height=64,
            loot_table=f"{mod_id}:chests/ruby_shrine_loot",
        )

    def _make_ruby_shrine_loot_pool(self) -> LootPoolSpec:
        return LootPoolSpec(
            identifier="ruby_shrine_loot",
            display_name="Ruby Shrine Loot",
            display_name_zh_cn="",
            rolls=2,
            entries=[
                LootEntrySpec(item="minecraft:emerald", min_count=1, max_count=4, weight=3),
                LootEntrySpec(item="minecraft:diamond", min_count=1, max_count=2, weight=1, chance=0.5),
            ],
        )

    def _ensure_progression_scaffold(
        self,
        mod_id: str,
        *,
        items: list[ItemSpec],
        ores: list[OreSpec],
        machines: list[MachineSpec],
        swords: list[SwordSpec],
        entities: list[EntitySpec],
        dimensions: list[WorldDimensionSpec],
        biomes: list[WorldBiomeSpec],
        world_features: list[WorldFeatureSpec],
        structures: list[WorldStructureSpec],
        loot_pools: list[LootPoolSpec],
        recipes: list[RecipeSpec],
    ) -> None:
        _append_missing(items, ItemSpec(identifier="raw_ruby", display_name="Raw Ruby", display_name_zh_cn="粗红宝石"))
        _append_missing(items, self._make_ruby_item())
        _append_missing(items, ItemSpec(identifier="ruby_key", display_name="Ruby Key", display_name_zh_cn="红宝石钥匙"))
        _append_missing(ores, self._make_ruby_ore(f"{mod_id}:raw_ruby", "ruby ore with overworld generation"))
        _append_missing(machines, self._make_ruby_machine("ruby compressor machine with menu"))
        _append_missing(swords, self._make_ruby_sword())
        _append_missing(entities, self._make_ruby_sentinel_entity(mod_id))
        _append_missing(biomes, self._make_ruby_fields_biome())
        _append_missing(dimensions, self._make_ruby_realm_dimension())
        _append_missing(world_features, self._make_ruby_vein_world_feature(mod_id))
        _append_missing(structures, self._make_ruby_shrine_structure(mod_id))
        _append_missing(loot_pools, self._make_progression_loot_pool(mod_id))
        _append_missing_recipe(
            recipes,
            RecipeSpec(
                identifier="raw_ruby_to_ruby",
                recipe_type="shapeless",
                ingredients=[f"{mod_id}:raw_ruby"],
                result=f"{mod_id}:ruby",
                count=1,
                category="misc",
                group="ruby_progression",
            ),
        )
        _append_missing_recipe(
            recipes,
            RecipeSpec(
                identifier="ruby_sword",
                recipe_type="shaped",
                pattern=[" R ", " R ", " S "],
                keys={"R": f"{mod_id}:ruby", "S": "minecraft:stick"},
                result=f"{mod_id}:ruby_sword",
                count=1,
                category="equipment",
                group="ruby_progression",
            ),
        )

    def _make_ruby_sentinel_entity(self, mod_id: str) -> EntitySpec:
        return EntitySpec(
            identifier="ruby_sentinel",
            display_name="Ruby Sentinel",
            display_name_zh_cn="红宝石守卫",
            entity_kind="monster",
            category="monster",
            width=0.8,
            height=2.1,
            tracking_range=12,
            update_interval=3,
            xp_reward=12,
            attributes=EntityAttributeSpec(
                max_health=32,
                movement_speed=0.24,
                attack_damage=6,
                armor=4,
                follow_range=28,
                knockback_resistance=0.1,
            ),
            drops=[EntityDropSpec(item=f"{mod_id}:ruby_key", min_count=1, max_count=1, chance=0.65)],
            spawn=EntitySpawnSpec(enabled=True, biomes="#minecraft:is_overworld", weight=20, min_count=1, max_count=1),
            goals=[
                EntityGoalSpec(goal_type="float", priority=0),
                EntityGoalSpec(goal_type="melee_attack", priority=2, speed=1.05),
                EntityGoalSpec(goal_type="target_player", priority=3),
            ],
            attack=EntityAttackSpec(attack_type="melee", damage=6, speed=1.05),
        )

    def _make_progression_loot_pool(self, mod_id: str) -> LootPoolSpec:
        return LootPoolSpec(
            identifier="ruby_shrine_loot",
            display_name="Ruby Shrine Loot",
            display_name_zh_cn="红宝石神殿战利品",
            rolls=2,
            entries=[
                LootEntrySpec(item=f"{mod_id}:ruby", min_count=2, max_count=5, weight=4),
                LootEntrySpec(item=f"{mod_id}:ruby_key", min_count=1, max_count=1, weight=1, chance=0.5),
                LootEntrySpec(item=f"{mod_id}:ruby_sword", min_count=1, max_count=1, weight=1, chance=0.35),
            ],
        )

    def _make_progression_specs(self, mod_id: str) -> list[ProgressionSpec]:
        return [
            ProgressionSpec(
                identifier="ruby_progression",
                title="Ruby Progression Loop",
                summary="Ore, material conversion, machine processing, equipment, entity drop, structure loot, and dimension entry are wired as one auditable gameplay route.",
                entry_stage="mine_ruby_ore",
                end_stage="enter_ruby_realm",
                stages=[
                    ProgressionStageSpec(
                        identifier="mine_ruby_ore",
                        stage_type="ore",
                        title="Mine Ruby Ore",
                        provides=["raw_ruby"],
                        evidence=["ruby_ore"],
                    ),
                    ProgressionStageSpec(
                        identifier="refine_raw_ruby",
                        stage_type="material",
                        title="Refine Raw Ruby",
                        requires=["raw_ruby"],
                        provides=["ruby"],
                        evidence=["recipe:raw_ruby_to_ruby"],
                    ),
                    ProgressionStageSpec(
                        identifier="process_with_machine",
                        stage_type="machine",
                        title="Process With Ruby Compressor",
                        requires=["ruby"],
                        unlocks=["ruby_sword"],
                        evidence=["ruby_compressor"],
                    ),
                    ProgressionStageSpec(
                        identifier="craft_equipment",
                        stage_type="equipment",
                        title="Craft Ruby Sword",
                        requires=["ruby"],
                        provides=["ruby_sword"],
                        evidence=["ruby_sword", "recipe:ruby_sword"],
                    ),
                    ProgressionStageSpec(
                        identifier="defeat_ruby_sentinel",
                        stage_type="entity",
                        title="Defeat Ruby Sentinel",
                        requires=["ruby_sword"],
                        provides=["ruby_key"],
                        evidence=["ruby_sentinel"],
                    ),
                    ProgressionStageSpec(
                        identifier="raid_ruby_shrine",
                        stage_type="structure",
                        title="Raid Ruby Shrine",
                        requires=["ruby_key"],
                        unlocks=["ruby_realm"],
                        evidence=["ruby_shrine", "ruby_shrine_loot"],
                    ),
                    ProgressionStageSpec(
                        identifier="enter_ruby_realm",
                        stage_type="dimension",
                        title="Enter Ruby Realm",
                        requires=["ruby_key"],
                        evidence=["ruby_realm"],
                    ),
                ],
                links=[
                    ProgressionLinkSpec("mine_ruby_ore", "refine_raw_ruby", "ore_drop", "Collect raw_ruby"),
                    ProgressionLinkSpec("refine_raw_ruby", "process_with_machine", "recipe_complete", "Craft ruby"),
                    ProgressionLinkSpec("process_with_machine", "craft_equipment", "machine_progress_complete", "Use ruby_compressor"),
                    ProgressionLinkSpec("craft_equipment", "defeat_ruby_sentinel", "combat", "Equip ruby_sword"),
                    ProgressionLinkSpec("defeat_ruby_sentinel", "raid_ruby_shrine", "drop", "Obtain ruby_key"),
                    ProgressionLinkSpec("raid_ruby_shrine", "enter_ruby_realm", "loot_unlock", "Find ruby_realm clue"),
                ],
            )
        ]

    def _make_balance_plan_specs(self) -> list[BalancePlanSpec]:
        return [
            BalancePlanSpec(
                identifier="ruby_balance_plan",
                title="Ruby Economy Balance Plan",
                target_progression="ruby_progression",
                profile="standard",
                summary="Recipe, loot, rarity, machine timing, energy, and reward weights are planned as one auditable economy layer.",
            )
        ]

    def _make_quest_specs(self) -> list[QuestSpec]:
        return [
            QuestSpec(
                identifier="ruby_questline",
                title="Ruby Questline",
                summary="A player-facing V7.2 guide layer that turns the ruby progression into visible advancements and a generated guidebook.",
                target_progression="ruby_progression",
                guidebook_id="ruby_guidebook",
                category="ruby_progression",
            )
        ]

    def _make_ruby_ore(self, drop: str, request: str = "") -> OreSpec:
        return OreSpec(
            identifier="ruby_ore",
            display_name="Ruby Ore",
            display_name_zh_cn="红宝石矿石",
            strength=3.0,
            resistance=3.0,
            sound="stone",
            requires_correct_tool=True,
            tool_tier="iron",
            drop=drop,
            min_drop=1,
            max_drop=1,
            affected_by_fortune=False,
            silk_touch_drops_self=False,
            worldgen=self._extract_worldgen(request),
        )

    def _make_ruby_apple(self, request: str = "") -> FoodSpec:
        effects = self._extract_food_effects(request)
        return FoodSpec(
            identifier="ruby_apple",
            display_name="Ruby Apple",
            display_name_zh_cn="红宝石苹果",
            nutrition=6,
            saturation=0.8,
            effects=effects,
        )

    def _make_ruby_sword(self, request: str = "") -> SwordSpec:
        on_hit = self._extract_sword_on_hit(request)
        return SwordSpec(
            identifier="ruby_sword",
            display_name="Ruby Sword",
            display_name_zh_cn="红宝石剑",
            attack_damage_bonus=4,
            attack_speed=-2.4,
            tool_material="ruby",
            on_hit=on_hit,
        )

    def _make_ruby_tool(self, tool_type: str) -> ToolSpec:
        labels = {
            "pickaxe": ("ruby_pickaxe", "Ruby Pickaxe", "红宝石镐"),
            "axe": ("ruby_axe", "Ruby Axe", "红宝石斧"),
            "shovel": ("ruby_shovel", "Ruby Shovel", "红宝石铲"),
            "hoe": ("ruby_hoe", "Ruby Hoe", "红宝石锄"),
        }
        identifier, display_name, display_name_zh = labels.get(tool_type, labels["pickaxe"])
        attack_damage, attack_speed = self._tool_defaults(tool_type)
        return ToolSpec(
            identifier=identifier,
            display_name=display_name,
            display_name_zh_cn=display_name_zh,
            tool_type=tool_type,
            tool_material="ruby",
            attack_damage_bonus=attack_damage,
            attack_speed=attack_speed,
        )

    def _make_ruby_armor(self, armor_type: str) -> ArmorSpec:
        labels = {
            "helmet": ("ruby_helmet", "Ruby Helmet", "红宝石头盔"),
            "chestplate": ("ruby_chestplate", "Ruby Chestplate", "红宝石胸甲"),
            "leggings": ("ruby_leggings", "Ruby Leggings", "红宝石护腿"),
            "boots": ("ruby_boots", "Ruby Boots", "红宝石靴子"),
        }
        identifier, display_name, display_name_zh = labels.get(armor_type, labels["helmet"])
        return ArmorSpec(
            identifier=identifier,
            display_name=display_name,
            display_name_zh_cn=display_name_zh,
            armor_type=armor_type,
            armor_material="ruby",
        )

    def _tool_defaults(self, tool_type: str) -> tuple[float, float]:
        defaults = {
            "pickaxe": (1.0, -2.8),
            "axe": (5.0, -3.0),
            "shovel": (1.5, -3.0),
            "hoe": (0.0, -3.0),
        }
        return defaults.get(tool_type, defaults["pickaxe"])

    def _detect_tool_type(self, text: str) -> str | None:
        lowered = text.lower()
        checks = {
            "pickaxe": ("pickaxe", "镐", "稿"),
            "axe": ("axe", "斧"),
            "shovel": ("shovel", "铲"),
            "hoe": ("hoe", "锄"),
        }
        for tool_type, tokens in checks.items():
            if any(token in lowered if token.isascii() else token in text for token in tokens):
                return tool_type
        return None

    def _detect_armor_type(self, text: str) -> str | None:
        lowered = text.lower()
        checks = {
            "helmet": ("helmet", "头盔"),
            "chestplate": ("chestplate", "胸甲"),
            "leggings": ("leggings", "护腿"),
            "boots": ("boots", "靴子", "靴"),
        }
        for armor_type, tokens in checks.items():
            if any(token in lowered if token.isascii() else token in text for token in tokens):
                return armor_type
        return None

    def _detect_machine_kind(self, text: str) -> str:
        lowered = text.lower()
        checks = {
            "magic_altar": ("magic altar", "altar", "魔法祭坛", "祭坛"),
            "upgrade_table": ("upgrade table", "upgrading table", "升级台"),
            "storage": ("storage", "container", "储物方块", "储物", "容器"),
            "furnace": ("furnace", "smelter", "熔炉"),
            "compressor": ("compressor", "press", "压缩机"),
        }
        for machine_kind, tokens in checks.items():
            if any(token in lowered if token.isascii() else token in text for token in tokens):
                return machine_kind
        return "compressor"

    def _detect_entity_kind(self, text: str) -> str:
        lowered = text.lower()
        checks = {
            "boss": ("boss",),
            "pet": ("pet", "companion", "tame"),
            "npc": ("npc", "villager"),
            "ambient": ("ambient",),
            "creature": ("creature", "animal", "passive"),
            "monster": ("monster", "mob", "goblin", "hostile"),
        }
        for entity_kind, tokens in checks.items():
            if any(token in lowered for token in tokens):
                return entity_kind
        return "monster"

    def _entity_category(self, entity_kind: str) -> str:
        return {
            "boss": "monster",
            "monster": "monster",
            "pet": "creature",
            "creature": "creature",
            "npc": "npc",
            "ambient": "ambient",
        }.get(entity_kind, "monster")

    def _entity_attributes_for(self, entity_kind: str) -> EntityAttributeSpec:
        if entity_kind == "boss":
            return EntityAttributeSpec(
                max_health=120.0,
                movement_speed=0.28,
                attack_damage=10.0,
                armor=8.0,
                follow_range=40.0,
                knockback_resistance=0.6,
            )
        if entity_kind == "pet":
            return EntityAttributeSpec(
                max_health=24.0,
                movement_speed=0.30,
                attack_damage=3.0,
                armor=2.0,
                follow_range=24.0,
                knockback_resistance=0.0,
            )
        if entity_kind in {"creature", "npc", "ambient"}:
            return EntityAttributeSpec(
                max_health=16.0,
                movement_speed=0.23,
                attack_damage=0.0,
                armor=0.0,
                follow_range=16.0,
                knockback_resistance=0.0,
            )
        return EntityAttributeSpec(
            max_health=24.0,
            movement_speed=0.27,
            attack_damage=4.0,
            armor=2.0,
            follow_range=28.0,
            knockback_resistance=0.0,
        )

    def _entity_attack_for(self, text: str, entity_kind: str) -> EntityAttackSpec | None:
        lowered = text.lower()
        if entity_kind in {"creature", "ambient", "npc"} or "passive" in lowered or "no attack" in lowered:
            return EntityAttackSpec(attack_type="none", damage=0.0, speed=1.0)
        damage = self._extract_number(text, patterns=[r"damage[^\d-]*(-?\d+(?:\.\d+)?)"], default_value=10.0 if entity_kind == "boss" else 4.0)
        speed = self._extract_number(text, patterns=[r"attack\s+speed[^\d-]*(-?\d+(?:\.\d+)?)"], default_value=1.0)
        return EntityAttackSpec(attack_type="melee", damage=damage, speed=max(0.1, speed))

    def _entity_drops_for(self, text: str) -> list[EntityDropSpec]:
        lowered = text.lower()
        if "diamond" in lowered:
            item = "minecraft:diamond"
        elif "emerald" in lowered or "drop" in lowered:
            item = "minecraft:emerald"
        else:
            return []
        return [EntityDropSpec(item=item, min_count=1, max_count=2, chance=0.5 if "chance" in lowered else 1.0)]

    def _entity_spawn_for(self, text: str) -> EntitySpawnSpec | None:
        lowered = text.lower()
        if not any(token in lowered for token in ("spawn", "spawns", "natural", "overworld", "biome")):
            return None
        return EntitySpawnSpec(
            enabled=True,
            biomes="#minecraft:is_overworld",
            weight=80,
            min_count=1,
            max_count=3,
            placement="on_ground",
        )

    def _extract_quoted_phrase(self, request: str) -> str | None:
        match = re.search(r"[\"“](.*?)[\"”]", request)
        if not match:
            return None
        return match.group(1).strip()

    def _has_ruby_hint(self, request: str) -> bool:
        lowered = request.lower()
        return "ruby" in lowered or "红宝石" in request

    def _has_machine_hint(self, request: str) -> bool:
        lowered = request.lower()
        return any(
            token in lowered
            for token in ("machine", "compressor", "furnace", "upgrade table", "magic altar", "storage block")
        ) or any(token in request for token in ("机器", "压缩机", "熔炉", "升级台", "魔法祭坛", "祭坛", "储物方块", "储物", "容器"))

    def _has_world_structure_hint(self, request: str) -> bool:
        lowered = request.lower()
        english_tokens = (
            "world structure dsl",
            "ruby realm",
            "dimension",
            "biome",
            "structure",
            "loot pool",
            "world feature",
        )
        chinese_tokens = ("维度", "群系", "结构", "地物", "战利品池", "矿脉规则")
        return any(token in lowered for token in english_tokens) or any(token in request for token in chinese_tokens)

    def _has_progression_hint(self, request: str) -> bool:
        lowered = request.lower()
        english_tokens = (
            "progression",
            "gameplay loop",
            "gameplay route",
            "progression loop",
            "advancement loop",
        )
        chinese_tokens = ("玩法线", "成长路线", "玩法路线", "维度推进", "矿物 -> 材料", "矿物->材料")
        return any(token in lowered for token in english_tokens) or any(token in request for token in chinese_tokens)

    def _has_balance_hint(self, request: str) -> bool:
        lowered = request.lower()
        english_tokens = (
            "balance planner",
            "recipe loot balance",
            "economy",
            "economic system",
            "rarity",
            "loot weight",
            "machine cost",
            "energy cost",
        )
        chinese_tokens = ("经济系统", "配方", "掉落", "稀有度", "机器耗时", "能量消耗", "战利品权重", "平衡")
        return any(token in lowered for token in english_tokens) or any(token in request for token in chinese_tokens)

    def _has_quest_hint(self, request: str) -> bool:
        lowered = request.lower()
        english_tokens = (
            "quest",
            "questline",
            "task chain",
            "advancement",
            "advancements",
            "guidebook",
            "guide book",
            "patchouli",
        )
        chinese_tokens = ("任务", "任务链", "成就", "引导", "指南")
        return any(token in lowered for token in english_tokens) or any(token in request for token in chinese_tokens)

    def _has_java_extension_hint(self, request: str) -> bool:
        lowered = request.lower()
        return any(
            token in lowered
            for token in (
                "controlled java extension",
                "safe java extension",
                "java extension",
                "受控 java 扩展",
            )
        )

    def _is_ruby_tool_set_request(self, request: str) -> bool:
        lowered = request.lower()
        return (
            any(token in request for token in ("一套红宝石工具", "红宝石工具套装", "红宝石全套工具"))
            or "ruby tool set" in lowered
            or "ruby tools" in lowered
        )

    def _is_ruby_armor_set_request(self, request: str) -> bool:
        lowered = request.lower()
        return (
            any(token in request for token in ("一套红宝石护甲", "红宝石护甲套装", "红宝石全套护甲"))
            or "ruby armor set" in lowered
            or "ruby armor" in lowered
        )

    def _is_ruby_block_variant_set_request(self, request: str) -> bool:
        lowered = request.lower()
        return (
            any(token in request for token in ("红宝石方块变体", "红宝石建筑方块套装", "红宝石建筑套装", "红宝石方块套装"))
            or "ruby block variants" in lowered
            or "ruby building block set" in lowered
            or "ruby building blocks" in lowered
        )

    def _ruby_block_variant_kinds(self, request: str) -> list[str]:
        if self._is_ruby_block_variant_set_request(request):
            return ["stairs", "slab", "wall", "button", "pressure_plate", "fence", "fence_gate", "door", "trapdoor"]

        lowered = request.lower()
        kinds: list[str] = []
        checks = [
            ("stairs", ["红宝石楼梯", "ruby stairs", "ruby stair"]),
            ("slab", ["红宝石台阶", "红宝石半砖", "ruby slab"]),
            ("wall", ["红宝石墙", "ruby wall"]),
            ("button", ["红宝石按钮", "ruby button"]),
            ("pressure_plate", ["红宝石压力板", "ruby pressure plate"]),
            ("fence_gate", ["红宝石栅栏门", "ruby fence gate"]),
            ("trapdoor", ["红宝石活板门", "ruby trapdoor", "ruby trap door"]),
            ("fence", ["红宝石栅栏", "ruby fence"]),
            ("door", ["红宝石门", "ruby door"]),
        ]
        for block_kind, tokens in checks:
            if block_kind == "fence" and ("红宝石栅栏门" in request or "ruby fence gate" in lowered):
                continue
            if block_kind == "door" and (
                "红宝石活板门" in request
                or "红宝石栅栏门" in request
                or "ruby trapdoor" in lowered
                or "ruby trap door" in lowered
                or "ruby fence gate" in lowered
            ):
                continue
            if self._mentions_any(request, tokens) and block_kind not in kinds:
                kinds.append(block_kind)
        return kinds

    def _needs_ruby_material_item(
        self,
        request: str,
        swords: list[SwordSpec],
        tools: list[ToolSpec],
        armors: list[ArmorSpec],
    ) -> bool:
        if self._is_ruby_tool_set_request(request) or self._is_ruby_armor_set_request(request):
            return True
        equipment = [*swords, *tools, *armors]
        return any(
            feature.identifier.startswith("ruby_")
            or getattr(feature, "tool_material", "").lower() == "ruby"
            or getattr(feature, "armor_material", "").lower() == "ruby"
            for feature in equipment
        )

    def _should_add_ruby_base_item(self, request: str) -> bool:
        lowered = request.lower()
        explicit_ruby = bool(
            re.search(r"(?:添加|加入).{0,4}红宝石(?:[，。、,\s]|$)", request)
            or re.search(r"\bruby(?:\s+item)?\b", lowered)
        )
        if explicit_ruby:
            return True
        if self._mentions_any(request, ["红宝石方块", "ruby block", "红宝石矿石", "ruby ore"]) or self._ruby_block_variant_kinds(request):
            return True
        return False

    def _mentions_any(self, request: str, phrases: list[str]) -> bool:
        lowered = request.lower()
        for phrase in phrases:
            haystack = lowered if phrase.isascii() else request
            if phrase in haystack:
                return True
        return False

    def _english_label(self, token: str) -> str:
        if re.search(r"[A-Za-z]", token):
            return derive_display_name(slugify_mod_id(token))
        return token

    def _zh_label(self, token: str) -> str:
        if re.search(r"[\u4e00-\u9fff]", token):
            return token
        return ""

    def _search(self, patterns: list[str], text: str) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _feature_counts(self, spec: ModSpec) -> dict[str, int]:
        return {
            "items": len(spec.items),
            "blocks": len(spec.blocks),
            "machines": len(spec.machines),
            "entities": len(spec.entities),
            "dimensions": len(spec.dimensions),
            "biomes": len(spec.biomes),
            "world_features": len(spec.world_features),
            "structures": len(spec.structures),
            "loot_pools": len(spec.loot_pools),
            "java_extensions": len(spec.java_extensions),
            "ores": len(spec.ores),
            "foods": len(spec.foods),
            "swords": len(spec.swords),
            "tools": len(spec.tools),
            "armors": len(spec.armors),
            "recipes": len(spec.recipes),
            "progressions": len(spec.progressions),
            "balance_plans": len(spec.balance_plans),
            "quests": len(spec.quests),
        }

    def _extract_behavior_item_spec(self, request: str) -> ItemSpec | None:
        lowered = request.lower()
        if "battle charm" in lowered or "behavior dsl" in lowered:
            return ItemSpec(
                identifier="battle_charm",
                display_name="Battle Charm",
                display_name_zh_cn="",
                behavior=self._make_behavior_dsl_charm(request),
            )
        if "红宝石护符" in request or "ruby charm" in lowered:
            return ItemSpec(
                identifier="ruby_charm",
                display_name="Ruby Charm",
                display_name_zh_cn="红宝石护符",
                behavior=(
                    self._make_behavior_dsl_charm(request)
                    if self._has_behavior_dsl_hint(request)
                    else self._extract_right_click_behavior(request, default_type="right_click_heal")
                ),
            )
        if "速度水晶" in request or "speed crystal" in lowered:
            return ItemSpec(
                identifier="speed_crystal",
                display_name="Speed Crystal",
                display_name_zh_cn="速度水晶",
                behavior=(
                    self._make_speed_behavior_dsl(request)
                    if self._has_behavior_dsl_hint(request)
                    else self._extract_right_click_behavior(request, default_type="right_click_effect", default_effect="minecraft:speed")
                ),
            )
        return None

    def _extract_behavior_block_spec(self, request: str) -> BlockSpec | None:
        lowered = request.lower()
        if "ruby pedestal" not in lowered and "behavior block" not in lowered:
            return None
        return BlockSpec(
            identifier="ruby_pedestal",
            display_name="Ruby Pedestal",
            display_name_zh_cn="",
            strength=4.0,
            resistance=6.0,
            sound="stone",
            requires_correct_tool=True,
            tool_tier="iron",
            behavior=ItemBehaviorSpec(
                behavior_type="event_action",
                events=[
                    BehaviorEventSpec(
                        trigger="block_use",
                        actions=[
                            BehaviorActionSpec(
                                action_type="apply_effect",
                                target="self",
                                effect="minecraft:regeneration",
                                duration_ticks=100,
                                amplifier=0,
                            ),
                            BehaviorActionSpec(
                                action_type="spawn_particles",
                                particle="minecraft:happy_villager",
                                count=12,
                            ),
                            BehaviorActionSpec(
                                action_type="play_sound",
                                sound="minecraft:block.amethyst_block.chime",
                                volume=0.8,
                                pitch=1.1,
                            ),
                        ],
                    )
                ],
            ),
        )

    def _has_behavior_dsl_hint(self, request: str) -> bool:
        lowered = request.lower()
        return any(
            token in lowered
            for token in (
                "behavior dsl",
                "particle",
                "particles",
                "sound",
                "tick",
                "every",
                "sneak",
                "condition",
            )
        )

    def _make_behavior_dsl_charm(self, request: str) -> ItemBehaviorSpec:
        events = [
            BehaviorEventSpec(
                trigger="right_click",
                cooldown_ticks=self._extract_seconds(request, keywords=["cooldown"], default_seconds=5),
                conditions=(
                    [BehaviorConditionSpec(condition_type="sneaking")]
                    if "sneak" in request.lower()
                    else []
                ),
                actions=[
                    BehaviorActionSpec(action_type="heal", target="self", amount=4.0),
                    BehaviorActionSpec(
                        action_type="apply_effect",
                        target="self",
                        effect="minecraft:regeneration",
                        duration_ticks=100,
                        amplifier=0,
                    ),
                    BehaviorActionSpec(
                        action_type="spawn_particles",
                        particle="minecraft:heart",
                        count=10,
                    ),
                    BehaviorActionSpec(
                        action_type="play_sound",
                        sound="minecraft:entity.experience_orb.pickup",
                        volume=0.8,
                        pitch=1.2,
                    ),
                ],
            )
        ]
        if "tick" in request.lower() or "every" in request.lower():
            interval = self._extract_seconds(request, keywords=["every"], default_seconds=5)
            events.append(
                BehaviorEventSpec(
                    trigger="inventory_tick",
                    interval_ticks=interval or 100,
                    conditions=[BehaviorConditionSpec(condition_type="health_below", threshold=12.0)],
                    actions=[
                        BehaviorActionSpec(
                            action_type="spawn_particles",
                            particle="minecraft:heart",
                            count=2,
                        )
                    ],
                )
            )
        return ItemBehaviorSpec(behavior_type="event_action", events=events)

    def _make_speed_behavior_dsl(self, request: str) -> ItemBehaviorSpec:
        return ItemBehaviorSpec(
            behavior_type="event_action",
            events=[
                BehaviorEventSpec(
                    trigger="right_click",
                    cooldown_ticks=self._extract_seconds(request, keywords=["cooldown"], default_seconds=5),
                    actions=[
                        BehaviorActionSpec(
                            action_type="apply_effect",
                            target="self",
                            effect="minecraft:speed",
                            duration_ticks=self._extract_seconds(request, keywords=["duration"], default_seconds=10),
                            amplifier=1,
                        ),
                        BehaviorActionSpec(
                            action_type="spawn_particles",
                            particle="minecraft:happy_villager",
                            count=12,
                        ),
                        BehaviorActionSpec(
                            action_type="play_sound",
                            sound="minecraft:entity.experience_orb.pickup",
                        ),
                    ],
                )
            ],
        )

    def _extract_right_click_behavior(
        self,
        request: str,
        *,
        default_type: str,
        default_effect: str | None = None,
    ) -> ItemBehaviorSpec:
        cooldown_ticks = self._extract_seconds(request, keywords=["冷却"], default_seconds=0)
        consume = any(token in request.lower() for token in ("consume", "消耗", "用掉", "使用后消失"))
        if default_type == "right_click_heal":
            amount = self._extract_number(request, patterns=[r"(?:回复|回血)[^\d-]*(-?\d+(?:\.\d+)?)", r"heal[^\d-]*(-?\d+(?:\.\d+)?)"], default_value=4.0)
            return ItemBehaviorSpec(
                behavior_type="right_click_heal",
                amount=amount,
                cooldown_ticks=cooldown_ticks,
                consume=consume,
            )

        effect = default_effect or self._extract_effect_id(request) or "minecraft:speed"
        duration_ticks = self._extract_seconds(request, keywords=["持续"], default_seconds=10)
        amplifier = self._extract_effect_level(request)
        return ItemBehaviorSpec(
            behavior_type="right_click_effect",
            effect=effect,
            duration_ticks=duration_ticks,
            amplifier=amplifier,
            cooldown_ticks=cooldown_ticks,
            consume=consume,
        )

    def _extract_food_effects(self, request: str) -> list[FoodEffectSpec]:
        effect_id = self._extract_effect_id(request)
        if effect_id is None:
            return []
        return [
            FoodEffectSpec(
                effect=effect_id,
                duration_ticks=self._extract_seconds(request, keywords=["持续"], default_seconds=5),
                amplifier=self._extract_effect_level(request),
                probability=1.0,
            )
        ]

    def _extract_sword_on_hit(self, request: str) -> OnHitBehaviorSpec | None:
        lowered = request.lower()
        if any(token in request for token in ("点燃", "着火")) or "ignite" in lowered:
            seconds = self._extract_seconds(request, keywords=["点燃", "着火", "持续"], default_seconds=5)
            return OnHitBehaviorSpec(behavior_type="ignite", seconds=max(1, seconds // 20))
        return None

    def _extract_effect_id(self, request: str) -> str | None:
        lowered = request.lower()
        mappings = {
            "速度": "minecraft:speed",
            "speed": "minecraft:speed",
            "生命恢复": "minecraft:regeneration",
            "恢复": "minecraft:regeneration",
            "regeneration": "minecraft:regeneration",
            "力量": "minecraft:strength",
            "strength": "minecraft:strength",
            "抗性": "minecraft:resistance",
            "resistance": "minecraft:resistance",
            "跳跃提升": "minecraft:jump_boost",
            "jump boost": "minecraft:jump_boost",
            "急迫": "minecraft:haste",
            "haste": "minecraft:haste",
        }
        for token, effect_id in mappings.items():
            haystack = lowered if token.isascii() else request
            if token in haystack:
                return effect_id
        return None

    def _extract_effect_level(self, request: str) -> int:
        lowered = request.lower()
        if any(token in request for token in ("III", "3级", "三级")) or " iii" in lowered:
            return 2
        if any(token in request for token in ("II", "2级", "二级")) or " ii" in lowered:
            return 1
        if any(token in request for token in ("I", "1级", "一级")) or " i" in lowered:
            return 0
        number = self._extract_number(request, patterns=[r"(?:速度|生命恢复|恢复|力量|抗性|跳跃提升|急迫)[^\d-]*(-?\d+(?:\.\d+)?)"], default_value=1)
        return max(0, int(number) - 1)

    def _extract_seconds(self, request: str, *, keywords: list[str], default_seconds: int) -> int:
        for keyword in keywords:
            pattern = rf"{re.escape(keyword)}[^\d-]*(-?\d+(?:\.\d+)?)\s*秒"
            match = re.search(pattern, request, flags=re.IGNORECASE)
            if match:
                return int(float(match.group(1)) * 20)
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*秒", request)
        if match:
            return int(float(match.group(1)) * 20)
        return default_seconds * 20

    def _extract_number(self, request: str, *, patterns: list[str], default_value: float) -> float:
        for pattern in patterns:
            match = re.search(pattern, request, flags=re.IGNORECASE)
            if match:
                return float(match.group(1))
        return default_value

    def _extract_worldgen(self, request: str):
        lowered = request.lower()
        if not any(token in request or token in lowered for token in ["自然生成", "地下生成", "主世界", "worldgen", "overworld"]):
            return None

        min_y, max_y = -64, 32
        range_match = re.search(r"(?:y|高度)?\s*(-?\d+)\s*(?:到|至|-|~)\s*(-?\d+)", request, flags=re.IGNORECASE)
        if range_match:
            min_y = int(range_match.group(1))
            max_y = int(range_match.group(2))

        vein_size = int(self._extract_number(request, patterns=[r"(?:每矿脉|矿脉大小)[^\d-]*(-?\d+(?:\.\d+)?)"], default_value=6))
        count_match = re.search(r"(?:每区块)[^\d-]*(-?\d+(?:\.\d+)?)", request)
        if count_match:
            veins_per_chunk = int(float(count_match.group(1)))
        elif "很稀有" in request:
            veins_per_chunk = 2
        elif "比较稀有" in request:
            veins_per_chunk = 4
        elif "常见" in request:
            veins_per_chunk = 12
        else:
            veins_per_chunk = 8 if "普通" in request else 4

        from .models import WorldgenSpec

        return WorldgenSpec(
            enabled=True,
            dimension="minecraft:overworld",
            min_y=min_y,
            max_y=max_y,
            vein_size=vein_size,
            veins_per_chunk=veins_per_chunk,
        )


def _append_missing(collection: list, feature) -> None:
    if not any(existing.identifier == feature.identifier for existing in collection):
        collection.append(feature)


def _append_missing_recipe(collection: list[RecipeSpec], recipe: RecipeSpec) -> None:
    if not any(existing.identifier == recipe.identifier for existing in collection):
        collection.append(recipe)
