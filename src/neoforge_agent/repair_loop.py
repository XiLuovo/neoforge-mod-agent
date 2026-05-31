from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .asset_generator import AssetGenerator
from .auditor import WorkspaceAuditor
from .builder import GradleBuilder
from .code_generator import CodeGenerator
from .config import AppConfig
from .models import BuildResult, ModSpec
from .planner import ModProjectPlanner
from .project_generator import ProjectGenerator
from .tools import (
    ensure_directory,
    write_generation_summary,
    write_json,
    write_manual_test_checklist,
    write_modspec_snapshot,
    write_pending_work_note,
    write_text,
)
from .validator import validate_generated_project, validate_mod_spec
from .worldgen_generator import WorldgenGenerator


@dataclass(slots=True)
class RepairLoopAttempt:
    index: int
    phase: str
    action: str
    success: bool
    audit: dict[str, Any] = field(default_factory=dict)
    build: dict[str, Any] = field(default_factory=dict)
    generated_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "phase": self.phase,
            "action": self.action,
            "success": self.success,
            "audit": self.audit,
            "build": self.build,
            "generated_files": list(self.generated_files),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class RepairLoopResult:
    success: bool
    workspace: Path
    max_attempts: int
    build_enabled: bool
    audit_enabled: bool
    repaired: bool
    attempts: list[RepairLoopAttempt]
    repair_loop_report_json_path: Path
    repair_loop_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "workspace": str(self.workspace),
            "max_attempts": self.max_attempts,
            "build_enabled": self.build_enabled,
            "audit_enabled": self.audit_enabled,
            "repaired": self.repaired,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "attempts_count": len(self.attempts),
            "repair_loop_report_json_path": str(self.repair_loop_report_json_path),
            "repair_loop_report_md_path": str(self.repair_loop_report_md_path),
        }


class AutoRepairRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()
        self.auditor = WorkspaceAuditor(self.config)
        self.builder = GradleBuilder(self.config)
        self.project_generator = ProjectGenerator(self.config)
        self.code_generator = CodeGenerator()
        self.asset_generator = AssetGenerator()
        self.worldgen_generator = WorldgenGenerator()
        self.planner = ModProjectPlanner(self.config)

    def run(
        self,
        workspace: Path,
        *,
        max_attempts: int = 1,
        run_build: bool = False,
        run_audit: bool = True,
    ) -> RepairLoopResult:
        workspace = workspace.resolve()
        max_attempts = max(0, max_attempts)
        attempts: list[RepairLoopAttempt] = []

        first = self._check(workspace, index=0, phase="initial_check", action="check", run_build=run_build, run_audit=run_audit)
        attempts.append(first)
        repaired = False

        current = first
        for attempt_index in range(1, max_attempts + 1):
            if current.success:
                break
            repair = self._regenerate_managed_files(workspace)
            repaired = True
            current = self._check(
                workspace,
                index=attempt_index,
                phase="repair_attempt",
                action="regenerate_managed_files",
                run_build=run_build,
                run_audit=run_audit,
                generated_files=repair["generated_files"],
                warnings=repair["warnings"],
                errors=repair["errors"],
            )
            attempts.append(current)

        success = attempts[-1].success if attempts else False
        agent_dir = ensure_directory(self.config.agent_dir_for(workspace))
        report_json = agent_dir / "repair-loop-report.json"
        report_md = agent_dir / "repair-loop-report.md"
        result = RepairLoopResult(
            success=success,
            workspace=workspace,
            max_attempts=max_attempts,
            build_enabled=run_build,
            audit_enabled=run_audit,
            repaired=repaired,
            attempts=attempts,
            repair_loop_report_json_path=report_json,
            repair_loop_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_markdown(result))
        return result

    def _check(
        self,
        workspace: Path,
        *,
        index: int,
        phase: str,
        action: str,
        run_build: bool,
        run_audit: bool,
        generated_files: list[str] | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> RepairLoopAttempt:
        audit_payload = self._audit(workspace) if run_audit else {"attempted": False, "success": None}
        build = self.builder.build(workspace) if run_build else BuildResult(
            attempted=False,
            success=None,
            summary="Gradle build was not executed.",
        )
        build_payload = build.to_dict()
        success = True
        if run_audit:
            success = success and audit_payload.get("success") is True
        if run_build:
            success = success and build.success is True

        collected_errors = list(errors or [])
        if run_audit and audit_payload.get("success") is False:
            collected_errors.extend(str(issue.get("message", "Audit failed.")) for issue in audit_payload.get("errors", []))
            if audit_payload.get("error"):
                collected_errors.append(str(audit_payload["error"]))
        if run_build and build.success is False:
            collected_errors.extend(str(issue.get("message", "Build failed.")) for issue in build_payload.get("issues", []))
            if not build_payload.get("issues"):
                collected_errors.append(build.summary or "Build failed.")

        return RepairLoopAttempt(
            index=index,
            phase=phase,
            action=action,
            success=success,
            audit=audit_payload,
            build=build_payload,
            generated_files=list(generated_files or []),
            warnings=list(warnings or []),
            errors=collected_errors,
        )

    def _audit(self, workspace: Path) -> dict[str, Any]:
        try:
            result = self.auditor.audit_workspace(workspace)
        except FileNotFoundError as exc:
            return {
                "attempted": True,
                "success": False,
                "error": str(exc),
                "errors": [{"message": str(exc)}],
                "warnings": [],
                "checks": [],
            }
        payload = result.to_dict()
        payload["attempted"] = True
        return payload

    def _regenerate_managed_files(self, workspace: Path) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        generated_files: list[str] = []
        try:
            spec = self._load_modspec(workspace)
            validation = validate_mod_spec(spec, self.config)
            if not validation.is_valid:
                return {
                    "generated_files": [],
                    "warnings": [issue.message for issue in validation.warnings],
                    "errors": [issue.message for issue in validation.errors],
                }

            layout = self.project_generator.generate(workspace, spec, clean_roots=False)
            java_files, code_warnings = self.code_generator.generate(layout, spec)
            asset_files = self.asset_generator.generate(layout, spec)
            worldgen_files = self.worldgen_generator.generate(layout.resources_dir, spec)
            metadata_path = write_modspec_snapshot(workspace, spec, self.config)
            manual_test_checklist_path = write_manual_test_checklist(workspace, self.config, spec)
            pending_actions = self.planner._derive_pending_actions(spec)
            if pending_actions:
                write_pending_work_note(workspace, self.config, pending_actions)

            pack_mcmeta_path = workspace / "src" / "main" / "resources" / "pack.mcmeta"
            generated_files = [
                str(path.relative_to(workspace))
                for path in [*java_files, *asset_files, *worldgen_files, pack_mcmeta_path]
            ]
            warnings.extend(code_warnings)
            warnings.extend(validate_generated_project(workspace, spec))
            fallbacks = [warning for warning in warnings if "fall back" in warning.lower() or "fallback" in warning.lower()]
            write_generation_summary(
                workspace,
                self.config,
                {
                    "stage": "auto-repair-regenerate",
                    "timestamp": datetime.now().isoformat(),
                    "spec": spec.to_dict(),
                    "features_count": _feature_counts(spec),
                    "generated_files": generated_files,
                    "warnings": warnings,
                    "fallbacks": fallbacks,
                    "metadata_path": str(metadata_path),
                    "manual_test_checklist_path": str(manual_test_checklist_path),
                    "repair_strategy": "regenerate_managed_files",
                },
            )
        except Exception as exc:  # The loop must report repair failures instead of crashing.
            errors.append(f"{type(exc).__name__}: {exc}")
        return {"generated_files": generated_files, "warnings": warnings, "errors": errors}

    def _load_modspec(self, workspace: Path) -> ModSpec:
        modspec_path = self.config.agent_dir_for(workspace) / "modspec.json"
        if not modspec_path.exists():
            raise FileNotFoundError(f"Missing modspec.json: {modspec_path}")
        return ModSpec.from_dict(json.loads(modspec_path.read_text(encoding="utf-8")))

    def _render_markdown(self, result: RepairLoopResult) -> str:
        lines = [
            "# Repair Loop Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Workspace: `{result.workspace}`",
            f"Max repair attempts: {result.max_attempts}",
            f"Audit enabled: {str(result.audit_enabled).lower()}",
            f"Build enabled: {str(result.build_enabled).lower()}",
            f"Repaired: {str(result.repaired).lower()}",
            "",
            "## Attempts",
            "",
        ]
        for attempt in result.attempts:
            lines.append(f"### {attempt.index}. {attempt.phase}")
            lines.append("")
            lines.append(f"- action: `{attempt.action}`")
            lines.append(f"- success: {str(attempt.success).lower()}")
            if attempt.generated_files:
                lines.append(f"- regenerated files: {len(attempt.generated_files)}")
            if attempt.audit.get("attempted"):
                lines.append(f"- audit success: {attempt.audit.get('success')}")
                lines.append(f"- audit errors: {len(attempt.audit.get('errors', []))}")
            if attempt.build.get("attempted"):
                lines.append(f"- build success: {attempt.build.get('success')}")
                lines.append(f"- build summary: {attempt.build.get('summary')}")
            for warning in attempt.warnings:
                lines.append(f"- warning: {warning}")
            for error in attempt.errors:
                lines.append(f"- error: {error}")
            lines.append("")
        return "\n".join(lines)


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
    }
