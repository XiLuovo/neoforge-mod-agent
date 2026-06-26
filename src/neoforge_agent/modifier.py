from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import AppConfig
from .feature_catalog import FeatureMergePolicy, iter_feature_kind_definitions
from .llm_client import check_llm_provider_health, create_llm_client
from .llm_planner import LLMPlanningError, PlannerArtifacts, plan_modification_with_decomposed_llm, plan_modification_with_llm, write_planner_artifacts
from .models import (
    BuildResult,
    FoodSpec,
    ModSpec,
    OreSpec,
    ProgressionLinkSpec,
    ProgressionSpec,
    RecipeSpec,
    RequestOverrides,
    SwordSpec,
)
from .planner import ModProjectPlanner
from .planner_resolution import PlannerResolution
from .patch_agent import patch_agent_artifacts, write_patch_agent_plan
from .tools import ensure_directory, write_generation_summary, write_text
from .validator import validate_mod_spec
from .workspace_materializer import WorkspaceMaterializer


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
        self.materializer = WorkspaceMaterializer(self.config)

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
        require_llm: bool = False,
    ) -> PlannerResolution:
        if planner_mode == "rules":
            patch = self._rules_patch(existing, change_request)
            return PlannerResolution(
                spec=patch,
                artifacts=None,
                warnings=[],
                planner_mode_used="rules",
            )

        if planner_mode == "decomposed":
            health = check_llm_provider_health(llm_provider)
            if llm_provider == "openai-compatible" and not health.healthy:
                warnings = [
                    "LLM provider health check failed; decomposed modify planner fell back to rules.",
                    *health.errors,
                    *health.warnings,
                ]
                if require_llm:
                    message = "LLM provider health check failed; decomposed modify planner fallback is disabled by require_llm."
                    artifacts = PlannerArtifacts(
                        planner_mode="modify:decomposed",
                        provider=llm_provider,
                        input_text=change_request,
                        warnings=warnings,
                        error=message,
                        provider_health=health.to_dict(),
                    )
                    raise LLMPlanningError(message, artifacts)
                patch = self._rules_patch(existing, change_request)
                return PlannerResolution(
                    spec=patch,
                    artifacts=None,
                    warnings=warnings,
                    planner_mode_used="decomposed->rules",
                )
            try:
                client = create_llm_client(llm_provider, self.config.project_root)
                patch, artifacts = plan_modification_with_decomposed_llm(existing, change_request, client, config=self.config)
                return PlannerResolution(
                    spec=patch,
                    artifacts=artifacts,
                    warnings=list(artifacts.warnings),
                    planner_mode_used="decomposed",
                )
            except (LLMPlanningError, ValueError, RuntimeError) as exc:
                if require_llm:
                    if isinstance(exc, LLMPlanningError):
                        raise
                    message = f"Decomposed modify planner failed and fallback is disabled by require_llm: {exc}"
                    artifacts = PlannerArtifacts(
                        planner_mode="modify:decomposed",
                        provider=llm_provider,
                        input_text=change_request,
                        warnings=[message],
                        error=message,
                    )
                    raise LLMPlanningError(message, artifacts) from exc
                patch = self._rules_patch(existing, change_request)
                artifacts = exc.artifacts if isinstance(exc, LLMPlanningError) else None
                warnings = [f"Decomposed modify planner failed; fallback to rules: {exc}"]
                if artifacts is not None:
                    warnings.extend(artifacts.warnings)
                return PlannerResolution(
                    spec=patch,
                    artifacts=artifacts,
                    warnings=warnings,
                    planner_mode_used="decomposed->rules",
                )

        if planner_mode == "llm":
            health = check_llm_provider_health(llm_provider)
            if llm_provider == "openai-compatible" and not health.healthy:
                warnings = [
                    "LLM provider health check failed; modify planner fell back to rules.",
                    *health.errors,
                    *health.warnings,
                ]
                if require_llm:
                    message = "LLM provider health check failed; modify planner fallback is disabled by require_llm."
                    artifacts = PlannerArtifacts(
                        planner_mode="modify:llm",
                        provider=llm_provider,
                        input_text=change_request,
                        warnings=warnings,
                        error=message,
                        provider_health=health.to_dict(),
                    )
                    raise LLMPlanningError(message, artifacts)
                patch = self._rules_patch(existing, change_request)
                return PlannerResolution(
                    spec=patch,
                    artifacts=None,
                    warnings=warnings,
                    planner_mode_used="llm->rules",
                )
            try:
                client = create_llm_client(llm_provider, self.config.project_root)
                patch, artifacts = plan_modification_with_llm(existing, change_request, client, config=self.config)
                return PlannerResolution(
                    spec=patch,
                    artifacts=artifacts,
                    warnings=list(artifacts.warnings),
                    planner_mode_used="llm",
                )
            except (LLMPlanningError, ValueError, RuntimeError) as exc:
                if require_llm:
                    if isinstance(exc, LLMPlanningError):
                        raise
                    message = f"LLM modify planner failed and fallback is disabled by require_llm: {exc}"
                    artifacts = PlannerArtifacts(
                        planner_mode="modify:llm",
                        provider=llm_provider,
                        input_text=change_request,
                        warnings=[message],
                        error=message,
                    )
                    raise LLMPlanningError(message, artifacts) from exc
                patch = self._rules_patch(existing, change_request)
                artifacts = exc.artifacts if isinstance(exc, LLMPlanningError) else None
                warnings = [f"LLM modify planner failed; fallback to rules: {exc}"]
                if artifacts is not None:
                    warnings.extend(artifacts.warnings)
                return PlannerResolution(
                    spec=patch,
                    artifacts=artifacts,
                    warnings=warnings,
                    planner_mode_used="llm->rules",
                )

        rules_patch = self._rules_patch(existing, change_request)
        if rules_patch.all_content() or rules_patch.entities or rules_patch.all_world_like() or rules_patch.java_extensions or rules_patch.recipes or rules_patch.progressions or rules_patch.balance_plans or rules_patch.quests:
            return PlannerResolution(
                spec=rules_patch,
                artifacts=None,
                warnings=[],
                planner_mode_used="rules",
            )
        health = check_llm_provider_health(llm_provider)
        if llm_provider == "openai-compatible" and not health.healthy:
            if require_llm:
                message = "LLM provider health check failed; auto modify planner fallback is disabled by require_llm."
                artifacts = PlannerArtifacts(
                    planner_mode="modify:auto",
                    provider=llm_provider,
                    input_text=change_request,
                    warnings=[
                        "Auto planner would fall back to rules because LLM provider health check failed.",
                        *health.errors,
                        *health.warnings,
                    ],
                    error=message,
                    provider_health=health.to_dict(),
                )
                raise LLMPlanningError(message, artifacts)
            return PlannerResolution(
                spec=rules_patch,
                artifacts=None,
                warnings=[
                    "Auto planner fallback to rules because LLM provider health check failed.",
                    *health.errors,
                    *health.warnings,
                ],
                planner_mode_used="auto->rules",
            )
        try:
            client = create_llm_client(llm_provider, self.config.project_root)
            patch, artifacts = plan_modification_with_llm(existing, change_request, client, config=self.config)
            warnings = [*artifacts.warnings, "Auto planner used LLM because rules modification looked empty."]
            return PlannerResolution(
                spec=patch,
                artifacts=artifacts,
                warnings=warnings,
                planner_mode_used="auto->llm",
            )
        except (LLMPlanningError, ValueError) as exc:
            if require_llm:
                if isinstance(exc, LLMPlanningError):
                    raise
                message = f"Auto modify planner failed and fallback is disabled by require_llm: {exc}"
                artifacts = PlannerArtifacts(
                    planner_mode="modify:auto",
                    provider=llm_provider,
                    input_text=change_request,
                    warnings=[message],
                    error=message,
                )
                raise LLMPlanningError(message, artifacts) from exc
            return PlannerResolution(
                spec=rules_patch,
                artifacts=None,
                warnings=[f"Auto planner fallback to rules: {exc}"],
                planner_mode_used="auto->rules",
            )

    def merge_modspec(self, existing: ModSpec, patch: ModSpec) -> MergeResult:
        merged = ModSpec.from_dict(existing.to_dict())
        added: list[str] = []
        updated: list[str] = []
        skipped: list[str] = []
        warnings: list[str] = []

        for definition in iter_feature_kind_definitions():
            if definition.merge_policy == FeatureMergePolicy.REPLACE_RECIPE_BY_IDENTIFIER:
                continue
            existing_list = getattr(merged, definition.collection_name)
            patch_list = getattr(patch, definition.collection_name)
            for feature in patch_list:
                outcome = _merge_feature(existing_list, feature, merged, merge_policy=definition.merge_policy)
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
                if recipe.identifier not in added:
                    added.append(recipe.identifier)
            elif existing_recipe.to_dict() == recipe.to_dict():
                skipped.append(recipe.identifier)
            else:
                index = merged.recipes.index(existing_recipe)
                merged.recipes[index] = recipe
                existing_recipe_ids[recipe.identifier] = recipe
                updated.append(recipe.identifier)

        touched_ruby_equipment_ids = _ruby_equipment_ids(patch)
        for recipe in _missing_ruby_equipment_recipes(merged, only_ids=touched_ruby_equipment_ids):
            merged.recipes.append(recipe)
            existing_recipe_ids[recipe.identifier] = recipe
            if recipe.identifier not in added:
                added.append(recipe.identifier)
            warnings.append(f"Deterministically added ruby equipment recipe '{recipe.identifier}'.")

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
        require_llm: bool = False,
        run_build: bool = False,
        repair: bool = False,
    ) -> ModifyResult:
        workspace = workspace.resolve()
        existing = self.load_existing_modspec(workspace)
        planner_resolution = self.plan_modification(
            existing,
            change_request,
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            require_llm=require_llm,
        )
        patch = planner_resolution.spec
        planner_artifacts = planner_resolution.artifacts
        planner_warnings = planner_resolution.warnings
        planner_mode_used = planner_resolution.planner_mode_used
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

        materialization_result = self.materializer.update_workspace(
            workspace,
            merged_spec,
            run_build=run_build,
            repair=repair,
        )
        modspec_path = materialization_result.metadata_path or self.config.agent_dir_for(workspace) / "modspec.json"
        build_result = materialization_result.build
        warnings = _unique_strings([*planner_warnings, *merge_result.warnings, *materialization_result.warnings])
        fallbacks = [warning for warning in warnings if "fall back" in warning.lower() or "fallback" in warning.lower()]
        materialization_result.warnings = warnings
        materialization_result.fallbacks = fallbacks
        write_generation_summary(workspace, self.config, materialization_result.to_dict())

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
        self.materializer.cleanup_managed_files(workspace)


def load_existing_modspec(workspace: Path, config: AppConfig | None = None) -> ModSpec:
    return WorkspaceModifier(config).load_existing_modspec(workspace)


def plan_modification(
    existing: ModSpec,
    prompt: str,
    planner: str = "rules",
    llm_provider: str = "mock",
    require_llm: bool = False,
    config: AppConfig | None = None,
) -> ModSpec:
    modifier = WorkspaceModifier(config)
    return modifier.plan_modification(
        existing,
        prompt,
        planner_mode=planner,
        llm_provider=llm_provider,
        require_llm=require_llm,
    ).spec


def merge_modspec(existing: ModSpec, patch: ModSpec, config: AppConfig | None = None) -> MergeResult:
    return WorkspaceModifier(config).merge_modspec(existing, patch)


def _merge_feature(
    existing_list: list,
    feature,
    merged_spec: ModSpec,
    *,
    merge_policy: FeatureMergePolicy = FeatureMergePolicy.REPLACE_BY_IDENTIFIER,
) -> str:
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
    if merge_policy == FeatureMergePolicy.MERGE_PROGRESSION and isinstance(existing, ProgressionSpec) and isinstance(feature, ProgressionSpec):
        feature = _merge_progression_patch(existing, feature)
        if existing.to_dict() == feature.to_dict():
            return "skipped"
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


def _merge_progression_patch(existing: ProgressionSpec, patch: ProgressionSpec) -> ProgressionSpec:
    stage_map = {stage.identifier: stage for stage in existing.stages}
    stage_order = [stage.identifier for stage in existing.stages]
    for stage in patch.stages:
        if stage.identifier not in stage_map:
            stage_order.append(stage.identifier)
        stage_map[stage.identifier] = stage
    stages = [stage_map[identifier] for identifier in stage_order]
    stage_ids = set(stage_order)

    link_map = {(link.from_stage, link.to_stage): link for link in existing.links}
    link_order = [(link.from_stage, link.to_stage) for link in existing.links]
    for link in patch.links:
        if link.from_stage not in stage_ids or link.to_stage not in stage_ids:
            continue
        key = (link.from_stage, link.to_stage)
        if key not in link_map:
            link_order.append(key)
        link_map[key] = link
    links = [link_map[key] for key in link_order]

    entry_stage = existing.entry_stage
    if patch.entry_stage in stage_ids and len(patch.stages) > 1:
        entry_stage = patch.entry_stage
    end_stage = existing.end_stage
    if patch.end_stage in stage_ids:
        end_stage = patch.end_stage
    links = _ensure_progression_end_reachable(existing.entry_stage, existing.end_stage, end_stage, links, stage_ids)

    return ProgressionSpec(
        identifier=existing.identifier,
        title=patch.title or existing.title,
        summary=patch.summary or existing.summary,
        entry_stage=entry_stage,
        end_stage=end_stage,
        stages=stages,
        links=links,
        behavior=patch.behavior or existing.behavior,
    )


def _ensure_progression_end_reachable(
    entry_stage: str,
    previous_end_stage: str,
    end_stage: str,
    links: list[ProgressionLinkSpec],
    stage_ids: set[str],
) -> list[ProgressionLinkSpec]:
    if not entry_stage or not end_stage or end_stage in _reachable_stage_ids(entry_stage, links):
        return links
    if previous_end_stage not in stage_ids or previous_end_stage == end_stage:
        return links
    inferred = ProgressionLinkSpec(
        from_stage=previous_end_stage,
        to_stage=end_stage,
        trigger="progression_update",
        requirement="Inferred final milestone transition.",
    )
    return [*links, inferred]


def _reachable_stage_ids(entry_stage: str, links: list[ProgressionLinkSpec]) -> set[str]:
    reachable = {entry_stage}
    changed = True
    while changed:
        changed = False
        for link in links:
            if link.from_stage in reachable and link.to_stage not in reachable:
                reachable.add(link.to_stage)
                changed = True
    return reachable


def _missing_ruby_equipment_recipes(spec: ModSpec, *, only_ids: set[str] | None = None) -> list[RecipeSpec]:
    if not any(item.identifier == "ruby" for item in spec.items):
        return []

    existing_recipe_ids = {recipe.identifier for recipe in spec.recipes}
    limited_ids = set(only_ids) if only_ids is not None else None
    material = f"{spec.mod_id}:ruby"
    stick = "minecraft:stick"
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
    equipment_ids = _ruby_equipment_ids(spec)
    if limited_ids is not None:
        equipment_ids &= limited_ids
    recipes: list[RecipeSpec] = []
    for identifier in sorted(equipment_ids):
        if identifier in existing_recipe_ids or identifier not in patterns:
            continue
        pattern, keys = patterns[identifier]
        recipes.append(
            RecipeSpec(
                identifier=identifier,
                recipe_type="shaped",
                pattern=list(pattern),
                keys=dict(keys),
                result=f"{spec.mod_id}:{identifier}",
                count=1,
                category="equipment",
                group="ruby_equipment",
            )
        )
    return recipes


def _ruby_equipment_ids(spec: ModSpec) -> set[str]:
    return {
        *(sword.identifier for sword in spec.swords if sword.tool_material.lower() == "ruby"),
        *(tool.identifier for tool in spec.tools if tool.tool_material.lower() == "ruby"),
        *(armor.identifier for armor in spec.armors if armor.armor_material.lower() == "ruby"),
    }


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


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
