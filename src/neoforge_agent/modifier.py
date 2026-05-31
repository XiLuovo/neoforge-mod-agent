from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .asset_generator import AssetGenerator
from .balance_generator import BalancePlanGenerator
from .builder import GradleBuilder
from .code_generator import CodeGenerator
from .config import AppConfig
from .llm_client import check_llm_provider_health, create_llm_client
from .llm_planner import LLMPlanningError, PlannerArtifacts, plan_modification_with_llm, write_planner_artifacts
from .models import (
    BuildResult,
    FoodSpec,
    GenerationResult,
    ModSpec,
    OreSpec,
    RecipeSpec,
    RequestOverrides,
    SwordSpec,
)
from .planner import ModProjectPlanner
from .project_generator import ProjectGenerator
from .behavior_report import BehaviorReportGenerator
from .progression_generator import ProgressionGenerator
from .patch_agent import patch_agent_artifacts, write_patch_agent_plan
from .quest_generator import QuestGuideGenerator
from .worldgen_generator import WorldgenGenerator
from .tools import (
    ensure_directory,
    resolve_managed_file,
    write_generation_summary,
    write_manual_test_checklist,
    write_modspec_snapshot,
    write_pending_work_note,
    write_text,
)
from .validator import validate_generated_project, validate_mod_spec


@dataclass(slots=True)
class MergeResult:
    modspec: ModSpec
    added: list[str]
    updated: list[str]
    skipped: list[str]
    warnings: list[str]


@dataclass(slots=True)
class ModifyResult:
    success: bool
    workspace: Path
    modspec_path: Path
    modify_summary_path: Path
    planner_mode_used: str
    planner_artifacts: PlannerArtifacts | None
    patch_spec: ModSpec
    added: list[str]
    updated: list[str]
    skipped: list[str]
    warnings: list[str]
    build: BuildResult


class WorkspaceModifier:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()
        self.planner = ModProjectPlanner(self.config)
        self.project_generator = ProjectGenerator(self.config)
        self.code_generator = CodeGenerator()
        self.asset_generator = AssetGenerator()
        self.worldgen_generator = WorldgenGenerator()
        self.progression_generator = ProgressionGenerator()
        self.behavior_report_generator = BehaviorReportGenerator()
        self.balance_plan_generator = BalancePlanGenerator()
        self.quest_guide_generator = QuestGuideGenerator()
        self.builder = GradleBuilder(self.config)

    def load_existing_modspec(self, workspace: Path) -> ModSpec:
        workspace = workspace.resolve()
        modspec_path = self.config.agent_dir_for(workspace) / "modspec.json"
        if not modspec_path.exists():
            raise FileNotFoundError(f"Existing ModSpec not found: {modspec_path}")
        return ModSpec.from_dict(json.loads(modspec_path.read_text(encoding="utf-8")))

    def plan_modification(
        self,
        existing: ModSpec,
        change_request: str,
        *,
        planner_mode: str = "rules",
        llm_provider: str = "mock",
    ) -> tuple[ModSpec, PlannerArtifacts | None, list[str], str]:
        if planner_mode == "rules":
            patch = self._rules_patch(existing, change_request)
            return patch, None, [], "rules"

        if planner_mode == "llm":
            health = check_llm_provider_health(llm_provider)
            if llm_provider == "openai-compatible" and not health.healthy:
                patch = self._rules_patch(existing, change_request)
                warnings = [
                    "LLM provider health check failed; modify planner fell back to rules.",
                    *health.errors,
                    *health.warnings,
                ]
                return patch, None, warnings, "llm->rules"
            try:
                client = create_llm_client(llm_provider, self.config.project_root)
                patch, artifacts = plan_modification_with_llm(existing, change_request, client, config=self.config)
                return patch, artifacts, list(artifacts.warnings), "llm"
            except (LLMPlanningError, ValueError, RuntimeError) as exc:
                patch = self._rules_patch(existing, change_request)
                artifacts = exc.artifacts if isinstance(exc, LLMPlanningError) else None
                warnings = [f"LLM modify planner failed; fallback to rules: {exc}"]
                if artifacts is not None:
                    warnings.extend(artifacts.warnings)
                return patch, artifacts, warnings, "llm->rules"

        rules_patch = self._rules_patch(existing, change_request)
        if rules_patch.all_content() or rules_patch.entities or rules_patch.all_world_like() or rules_patch.java_extensions or rules_patch.recipes or rules_patch.progressions or rules_patch.balance_plans or rules_patch.quests:
            return rules_patch, None, [], "rules"
        health = check_llm_provider_health(llm_provider)
        if llm_provider == "openai-compatible" and not health.healthy:
            return rules_patch, None, [
                "Auto planner fallback to rules because LLM provider health check failed.",
                *health.errors,
                *health.warnings,
            ], "auto->rules"
        try:
            client = create_llm_client(llm_provider, self.config.project_root)
            patch, artifacts = plan_modification_with_llm(existing, change_request, client, config=self.config)
            warnings = [*artifacts.warnings, "Auto planner used LLM because rules modification looked empty."]
            return patch, artifacts, warnings, "auto->llm"
        except (LLMPlanningError, ValueError) as exc:
            return rules_patch, None, [f"Auto planner fallback to rules: {exc}"], "auto->rules"

    def merge_modspec(self, existing: ModSpec, patch: ModSpec) -> MergeResult:
        merged = ModSpec.from_dict(existing.to_dict())
        added: list[str] = []
        updated: list[str] = []
        skipped: list[str] = []
        warnings: list[str] = []

        for collection_name in (
            "items",
            "blocks",
            "machines",
            "entities",
            "dimensions",
            "biomes",
            "world_features",
            "structures",
            "loot_pools",
            "java_extensions",
            "ores",
            "foods",
            "swords",
            "tools",
            "armors",
            "progressions",
            "balance_plans",
            "quests",
        ):
            existing_list = getattr(merged, collection_name)
            patch_list = getattr(patch, collection_name)
            for feature in patch_list:
                outcome = _merge_feature(existing_list, feature, merged)
                if outcome == "added":
                    added.append(feature.identifier)
                elif outcome == "updated":
                    updated.append(feature.identifier)
                elif outcome == "skipped":
                    skipped.append(feature.identifier)
                else:
                    warnings.append(outcome)

        existing_recipe_ids = {recipe.identifier: recipe for recipe in merged.recipes}
        for recipe in patch.recipes:
            existing_recipe = existing_recipe_ids.get(recipe.identifier)
            if existing_recipe is None:
                merged.recipes.append(recipe)
                existing_recipe_ids[recipe.identifier] = recipe
                added.append(recipe.identifier)
            elif existing_recipe.to_dict() == recipe.to_dict():
                skipped.append(recipe.identifier)
            else:
                index = merged.recipes.index(existing_recipe)
                merged.recipes[index] = recipe
                existing_recipe_ids[recipe.identifier] = recipe
                updated.append(recipe.identifier)

        merged.raw_request = f"{existing.raw_request}\n\n# modify\n{patch.raw_request}".strip()
        merged.requested_features = sorted(set(existing.requested_features + patch.requested_features))
        merged.extra_notes = [*existing.extra_notes, *[note for note in patch.extra_notes if note not in existing.extra_notes]]

        report = validate_mod_spec(merged, self.config)
        if not report.is_valid:
            raise ValueError("Merged ModSpec is invalid: " + "; ".join(issue.message for issue in report.errors))
        warnings.extend(issue.message for issue in report.warnings)
        return MergeResult(modspec=merged, added=added, updated=updated, skipped=skipped, warnings=warnings)

    def modify(
        self,
        workspace: Path,
        change_request: str,
        *,
        planner_mode: str = "rules",
        llm_provider: str = "mock",
        run_build: bool = False,
        repair: bool = False,
    ) -> ModifyResult:
        workspace = workspace.resolve()
        existing = self.load_existing_modspec(workspace)
        patch, planner_artifacts, planner_warnings, planner_mode_used = self.plan_modification(
            existing,
            change_request,
            planner_mode=planner_mode,
            llm_provider=llm_provider,
        )
        merge_result = self.merge_modspec(existing, patch)
        merged_spec = merge_result.modspec

        agent_dir = ensure_directory(self.config.agent_dir_for(workspace))
        modspec_before_path = agent_dir / "modspec.before.json"
        modspec_after_path = agent_dir / "modspec.after.json"
        last_request_path = agent_dir / "last-modify-request.txt"
        modify_summary_path = agent_dir / "modify-summary.json"
        modify_history_path = agent_dir / "modify-history.jsonl"
        patch_artifacts = patch_agent_artifacts(workspace, self.config)

        write_text(last_request_path, change_request)
        modspec_before_path.write_text(json.dumps(existing.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        modspec_after_path.write_text(json.dumps(merged_spec.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_patch_agent_plan(
            workspace,
            self.config,
            workspace=workspace,
            existing=existing,
            merged=merged_spec,
            change_request=change_request,
            planner_mode_used=planner_mode_used,
            llm_provider=llm_provider,
            added=merge_result.added,
            updated=merge_result.updated,
            skipped=merge_result.skipped,
            run_build=run_build,
            modspec_before_path=modspec_before_path,
            modspec_after_path=modspec_after_path,
            warnings=[*planner_warnings, *merge_result.warnings],
        )

        self._cleanup_managed_files(workspace)
        layout = self.project_generator.generate(workspace, merged_spec, clean_roots=False)
        java_files, code_warnings = self.code_generator.generate(layout, merged_spec)
        asset_files = self.asset_generator.generate(layout, merged_spec)
        worldgen_files = self.worldgen_generator.generate(layout.resources_dir, merged_spec)
        progression_files = self.progression_generator.generate(workspace, merged_spec, self.config)
        behavior_files = self.behavior_report_generator.generate(workspace, merged_spec, self.config)
        balance_files = self.balance_plan_generator.generate(workspace, merged_spec, self.config)
        quest_files = self.quest_guide_generator.generate(workspace, layout.resources_dir, merged_spec, self.config)
        modspec_path = write_modspec_snapshot(workspace, merged_spec, self.config)
        manual_test_checklist_path = write_manual_test_checklist(workspace, self.config, merged_spec)
        pending_actions = self.planner._derive_pending_actions(merged_spec)
        if pending_actions:
            write_pending_work_note(workspace, self.config, pending_actions)

        pack_mcmeta_path = workspace / "src" / "main" / "resources" / "pack.mcmeta"
        generated_files = [
            str(path.relative_to(workspace))
            for path in [*java_files, *asset_files, *worldgen_files, *progression_files, *behavior_files, *balance_files, *quest_files, pack_mcmeta_path]
        ]
        warnings = [*planner_warnings, *merge_result.warnings, *code_warnings]
        fallbacks = [warning for warning in warnings if "fall back" in warning.lower() or "fallback" in warning.lower()]
        write_generation_summary(
            workspace,
            self.config,
            {
                "stage": "modify-pre-build",
                "spec": merged_spec.to_dict(),
                "features_count": _feature_counts(merged_spec),
                "generated_files": generated_files,
                "warnings": warnings,
                "fallbacks": fallbacks,
                "manual_test_checklist_path": str(manual_test_checklist_path),
            },
        )
        project_warnings = validate_generated_project(workspace, merged_spec)
        warnings.extend(project_warnings)

        build_result = self.builder.build(workspace, repair=repair) if run_build else BuildResult(
            attempted=False,
            success=None,
            summary="Gradle build was not executed.",
        )

        result_payload = GenerationResult(
            spec=merged_spec,
            workspace_dir=workspace,
            steps=[],
            validation=validate_mod_spec(merged_spec, self.config),
            build=build_result,
            metadata_path=modspec_path,
            manual_test_checklist_path=manual_test_checklist_path,
            pending_actions=pending_actions,
            warnings=warnings,
            fallbacks=fallbacks,
            generated_files=generated_files,
        ).to_dict()
        write_generation_summary(workspace, self.config, result_payload)

        summary_payload = {
            "success": build_result.success if run_build else True,
            "request": change_request,
            "planner": planner_mode_used,
            "added": merge_result.added,
            "updated": merge_result.updated,
            "skipped": merge_result.skipped,
            "patch_agent_plan_path": str(patch_artifacts.plan_json),
            "warnings": warnings,
            "before_features_count": len(list(existing.iter_features())),
            "after_features_count": len(list(merged_spec.iter_features())),
            "build": build_result.to_dict(),
            "modspec_path": str(modspec_path),
        }
        modify_summary_path.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        with modify_history_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "request": change_request,
                        "planner": planner_mode_used,
                        "before_features": len(list(existing.iter_features())),
                        "after_features": len(list(merged_spec.iter_features())),
                        "added": merge_result.added,
                        "updated": merge_result.updated,
                        "skipped": merge_result.skipped,
                        "warnings": warnings,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

        if planner_artifacts is not None:
            planner_artifacts.planner_mode = f"modify:{planner_mode_used}"
            write_planner_artifacts(workspace, self.config, planner_artifacts)

        return ModifyResult(
            success=summary_payload["success"],
            workspace=workspace,
            modspec_path=modspec_path,
            modify_summary_path=modify_summary_path,
            planner_mode_used=planner_mode_used,
            planner_artifacts=planner_artifacts,
            patch_spec=patch,
            added=merge_result.added,
            updated=merge_result.updated,
            skipped=merge_result.skipped,
            warnings=warnings,
            build=build_result,
        )

    def _rules_patch(self, existing: ModSpec, change_request: str) -> ModSpec:
        overrides = RequestOverrides(
            mod_id=existing.mod_id,
            display_name=existing.display_name,
            package_name=existing.package_name,
            version=existing.version,
            authors=existing.authors,
            license_name=existing.license_name,
            description=existing.description,
        )
        patch = self.planner.parse_request(change_request, overrides=overrides)

        self._apply_update_rules(existing, patch, change_request)
        patch.raw_request = change_request
        return patch

    def _apply_update_rules(self, existing: ModSpec, patch: ModSpec, change_request: str) -> None:
        lowered = change_request.lower()

        sword = _find_target_sword(existing, change_request)
        if sword is not None and ("攻击力" in change_request or "attack damage" in lowered):
            attack_match = re.search(r"(?:攻击力|attack damage)[^\d-]*(-?\d+(?:\.\d+)?)", change_request, flags=re.IGNORECASE)
            speed_match = re.search(r"(?:攻击速度|attack speed)[^\d-]*(-?\d+(?:\.\d+)?)", change_request, flags=re.IGNORECASE)
            updated = _clone_feature(sword)
            if attack_match:
                updated.attack_damage_bonus = float(attack_match.group(1))
            if speed_match:
                updated.attack_speed = float(speed_match.group(1))
            patch.swords = _replace_or_append(patch.swords, updated)

        food = _find_target_food(existing, change_request)
        if food is not None and ("饱食度" in change_request or "nutrition" in lowered or "饱和" in change_request or "saturation" in lowered):
            nutrition_match = re.search(r"(?:饱食度|nutrition)[^\d-]*(-?\d+(?:\.\d+)?)", change_request, flags=re.IGNORECASE)
            saturation_match = re.search(r"(?:饱和(?:度)?|saturation)[^\d-]*(-?\d+(?:\.\d+)?)", change_request, flags=re.IGNORECASE)
            updated_food = _clone_feature(food)
            if nutrition_match:
                updated_food.nutrition = int(float(nutrition_match.group(1)))
            if saturation_match:
                updated_food.saturation = float(saturation_match.group(1))
            patch.foods = _replace_or_append(patch.foods, updated_food)

        ore = _find_target_ore(existing, change_request)
        if ore is not None and ("掉落" in change_request or "drop" in lowered):
            updated_ore = _clone_feature(ore)
            if "红宝石" in change_request or "ruby" in lowered:
                updated_ore.drop = f"{existing.mod_id}:ruby"
            drop_range = re.search(r"(\d+)\s*[-~到至]\s*(\d+)", change_request)
            if drop_range:
                updated_ore.min_drop = int(drop_range.group(1))
                updated_ore.max_drop = int(drop_range.group(2))
            worldgen = self.planner._extract_worldgen(change_request)
            if worldgen is not None:
                updated_ore.worldgen = worldgen
            patch.ores = _replace_or_append(patch.ores, updated_ore)

    def _cleanup_managed_files(self, workspace: Path) -> None:
        summary_path = self.config.agent_dir_for(workspace) / "generation-summary.json"
        if not summary_path.exists():
            return
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        for relative in summary.get("generated_files", []):
            try:
                path = resolve_managed_file(workspace, str(relative))
            except ValueError:
                continue
            if path.exists() and path.is_file():
                path.unlink()


def load_existing_modspec(workspace: Path, config: AppConfig | None = None) -> ModSpec:
    return WorkspaceModifier(config).load_existing_modspec(workspace)


def plan_modification(
    existing: ModSpec,
    prompt: str,
    planner: str = "rules",
    llm_provider: str = "mock",
    config: AppConfig | None = None,
) -> ModSpec:
    modifier = WorkspaceModifier(config)
    patch, _, _, _ = modifier.plan_modification(existing, prompt, planner_mode=planner, llm_provider=llm_provider)
    return patch


def merge_modspec(existing: ModSpec, patch: ModSpec, config: AppConfig | None = None) -> MergeResult:
    return WorkspaceModifier(config).merge_modspec(existing, patch)


def _merge_feature(existing_list: list, feature, merged_spec: ModSpec) -> str:
    existing = next((item for item in existing_list if item.identifier == feature.identifier), None)
    if existing is None:
        all_existing_ids = {
            item.identifier
            for item in [*merged_spec.all_content(), *merged_spec.entities, *merged_spec.all_world_like(), *merged_spec.java_extensions]
        }
        if feature.identifier in all_existing_ids:
            return f"Feature '{feature.identifier}' already exists in a different category; skipping patch."
        existing_list.append(feature)
        return "added"
    if existing.to_dict() == feature.to_dict():
        return "skipped"
    index = existing_list.index(existing)
    existing_list[index] = feature
    return "updated"


def _replace_or_append(items: list, feature):
    existing = next((item for item in items if item.identifier == feature.identifier), None)
    if existing is None:
        return [*items, feature]
    updated = list(items)
    updated[updated.index(existing)] = feature
    return updated


def _clone_feature(feature):
    values = {name: getattr(feature, name) for name in feature.__dataclass_fields__}
    return type(feature)(**values)


def _find_target_sword(existing: ModSpec, request: str) -> SwordSpec | None:
    if "剑" in request or "sword" in request.lower():
        if "红宝石剑" in request or "ruby sword" in request.lower():
            return next((item for item in existing.swords if item.identifier == "ruby_sword"), None)
        if len(existing.swords) == 1:
            return existing.swords[0]
    return None


def _find_target_food(existing: ModSpec, request: str) -> FoodSpec | None:
    if "苹果" in request or "apple" in request.lower():
        return next((item for item in existing.foods if item.identifier == "ruby_apple"), None)
    if len(existing.foods) == 1 and any(token in request for token in ["饱食度", "饱和"]):
        return existing.foods[0]
    return None


def _find_target_ore(existing: ModSpec, request: str) -> OreSpec | None:
    if "矿石" in request or "ore" in request.lower():
        return next((item for item in existing.ores if item.identifier == "ruby_ore"), None)
    if len(existing.ores) == 1 and ("掉落" in request or "drop" in request.lower()):
        return existing.ores[0]
    return None


def _feature_counts(spec: ModSpec) -> dict[str, int]:
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
