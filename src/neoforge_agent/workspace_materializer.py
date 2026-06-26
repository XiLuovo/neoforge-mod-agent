from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from .asset_generator import AssetGenerator
from .balance_generator import BalancePlanGenerator
from .behavior_report import BehaviorReportGenerator
from .builder import GradleBuilder
from .code_generator import CodeGenerator
from .config import AppConfig
from .java_extension_generator import finalize_java_extension_acceptance
from .models import BuildResult, GenerationResult, ModSpec, PlanStep, StepStatus, ValidationReport
from .project_generator import ProjectGenerator
from .progression_generator import ProgressionGenerator
from .quest_generator import QuestGuideGenerator
from .tools import (
    copy_template_tree,
    prepare_workspace_dir,
    resolve_managed_file,
    write_generation_summary,
    write_manual_test_checklist,
    write_modspec_snapshot,
    write_pending_work_note,
)
from .validator import validate_generated_project, validate_mod_spec
from .worldgen_generator import WorldgenGenerator


class WorkspaceMaterializer:
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

    def create_workspace(
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

        result = self._materialize_into_workspace(
            workspace_dir,
            spec,
            validation=validation,
            steps=steps,
            run_build=run_build,
            build_repair=False,
            clean_roots=True,
            initial_summary_stage="pre-build",
            finalize_java_extensions=True,
        )
        return result

    def update_workspace(
        self,
        workspace: Path,
        spec: ModSpec,
        *,
        run_build: bool = False,
        repair: bool = False,
    ) -> GenerationResult:
        workspace = workspace.resolve()
        self.cleanup_managed_files(workspace)
        validation = self.validate(spec)
        return self._materialize_into_workspace(
            workspace,
            spec,
            validation=validation,
            steps=[],
            run_build=run_build,
            build_repair=repair,
            clean_roots=False,
            initial_summary_stage="modify-pre-build",
            finalize_java_extensions=False,
        )

    def regenerate_workspace(
        self,
        workspace: Path,
        spec: ModSpec,
        *,
        summary_stage: str = "auto-repair-regenerate",
        summary_extra: dict[str, object] | None = None,
        clean_managed_files: bool = False,
    ) -> GenerationResult:
        workspace = workspace.resolve()
        if clean_managed_files:
            self.cleanup_managed_files(workspace)
        validation = self.validate(spec)
        if not validation.is_valid:
            return GenerationResult(
                spec=spec,
                workspace_dir=workspace,
                steps=[],
                validation=validation,
                warnings=[issue.message for issue in validation.warnings],
            )
        return self._materialize_into_workspace(
            workspace,
            spec,
            validation=validation,
            steps=[],
            run_build=False,
            build_repair=False,
            clean_roots=False,
            initial_summary_stage=summary_stage,
            finalize_java_extensions=False,
            final_summary_extra={
                "stage": summary_stage,
                **(summary_extra or {}),
            },
        )

    def cleanup_managed_files(self, workspace: Path) -> None:
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

    def derive_pending_actions(self, spec: ModSpec) -> list[str]:
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

    def _materialize_into_workspace(
        self,
        workspace: Path,
        spec: ModSpec,
        *,
        validation: ValidationReport,
        steps: list[PlanStep],
        run_build: bool,
        build_repair: bool,
        clean_roots: bool,
        initial_summary_stage: str,
        finalize_java_extensions: bool,
        final_summary_extra: dict[str, object] | None = None,
    ) -> GenerationResult:
        layout = self.project_generator.generate(workspace, spec, clean_roots=clean_roots)
        if steps:
            steps[3] = replace(
                steps[3],
                status=StepStatus.COMPLETED,
                detail="Updated package layout, gradle properties, mixin config, and mod metadata.",
            )

        java_files, code_warnings = self.code_generator.generate(layout, spec)
        if steps:
            java_source_count = sum(1 for path in java_files if path.suffix == ".java")
            steps[4] = replace(steps[4], status=StepStatus.COMPLETED, detail=f"Generated {java_source_count} Java source file(s).")

        asset_files = self.asset_generator.generate(layout, spec)
        worldgen_files = self.worldgen_generator.generate(layout.resources_dir, spec)
        progression_files = self.progression_generator.generate(workspace, spec, self.config)
        behavior_files = self.behavior_report_generator.generate(workspace, spec, self.config)
        balance_files = self.balance_plan_generator.generate(workspace, spec, self.config)
        quest_files = self.quest_guide_generator.generate(workspace, layout.resources_dir, spec, self.config)
        if steps:
            steps[5] = replace(
                steps[5],
                status=StepStatus.COMPLETED,
                detail=f"Generated {len(asset_files) + len(worldgen_files) + len(progression_files) + len(behavior_files) + len(balance_files) + len(quest_files)} asset/data/report file(s).",
            )

        metadata_path = write_modspec_snapshot(workspace, spec, self.config)
        manual_test_checklist_path = write_manual_test_checklist(workspace, self.config, spec)
        pending_actions = self.derive_pending_actions(spec)
        placeholder_note_path = write_pending_work_note(workspace, self.config, pending_actions) if pending_actions else None
        fallbacks = [warning for warning in code_warnings if "falling back" in warning.lower()]
        pack_mcmeta_path = workspace / "src" / "main" / "resources" / "pack.mcmeta"
        generated_files = [
            str(path.relative_to(workspace))
            for path in [*java_files, *asset_files, *worldgen_files, *progression_files, *behavior_files, *balance_files, *quest_files, pack_mcmeta_path]
        ]
        write_generation_summary(
            workspace,
            self.config,
            {
                "stage": initial_summary_stage,
                "spec": spec.to_dict(),
                "features_count": feature_counts(spec),
                "generated_files": generated_files,
                "warnings": list(code_warnings),
                "fallbacks": list(fallbacks),
                "manual_test_checklist_path": str(manual_test_checklist_path),
            },
        )
        if steps:
            steps[6] = replace(
                steps[6],
                status=StepStatus.COMPLETED,
                detail=f"Saved ModSpec snapshot to {metadata_path}.",
            )

        project_warnings = validate_generated_project(workspace, spec)
        if steps:
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

        if run_build:
            build_result = self.builder.build(workspace, repair=build_repair) if build_repair else self.builder.build(workspace)
        else:
            build_result = BuildResult(attempted=False, success=None, summary="Gradle build was not executed.")

        if steps:
            if run_build:
                status = StepStatus.COMPLETED if build_result.success else StepStatus.FAILED
                steps[8] = replace(steps[8], status=status, detail=build_result.summary)
            else:
                steps[8] = replace(steps[8], status=StepStatus.SKIPPED, detail="Build disabled for this run.")

        if finalize_java_extensions:
            acceptance_files = finalize_java_extension_acceptance(workspace, self.config, spec, build_result)
            for path in acceptance_files:
                relative = str(path.relative_to(workspace))
                if relative not in generated_files:
                    generated_files.append(relative)

        result = GenerationResult(
            spec=spec,
            workspace_dir=workspace,
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
        final_summary = result.to_dict()
        if final_summary_extra:
            final_summary.update(final_summary_extra)
        write_generation_summary(workspace, self.config, final_summary)
        return result


def feature_counts(spec: ModSpec) -> dict[str, int]:
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
