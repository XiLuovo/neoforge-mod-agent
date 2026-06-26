from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .auditor import WorkspaceAuditor
from .builder import GradleBuilder
from .config import AppConfig
from .evidence_writer import AgentEvidenceWriter
from .models import BuildResult, ModSpec
from .workspace_materializer import WorkspaceMaterializer


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
        self.materializer = WorkspaceMaterializer(self.config)
        self.evidence_writer = AgentEvidenceWriter(self.config)

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
        report_paths = self.evidence_writer.repair_loop_report_paths(workspace)
        result = RepairLoopResult(
            success=success,
            workspace=workspace,
            max_attempts=max_attempts,
            build_enabled=run_build,
            audit_enabled=run_audit,
            repaired=repaired,
            attempts=attempts,
            repair_loop_report_json_path=report_paths["report_json"],
            repair_loop_report_md_path=report_paths["report_md"],
        )
        self.evidence_writer.write_repair_loop_report(result)
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
            validation = self.materializer.validate(spec)
            if not validation.is_valid:
                return {
                    "generated_files": [],
                    "warnings": [issue.message for issue in validation.warnings],
                    "errors": [issue.message for issue in validation.errors],
                }

            result = self.materializer.regenerate_workspace(
                workspace,
                spec,
                summary_extra={
                    "repair_strategy": "regenerate_managed_files",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            generated_files = list(result.generated_files)
            warnings = list(result.warnings)
        except Exception as exc:  # The loop must report repair failures instead of crashing.
            errors.append(f"{type(exc).__name__}: {exc}")
        return {"generated_files": generated_files, "warnings": warnings, "errors": errors}

    def _load_modspec(self, workspace: Path) -> ModSpec:
        modspec_path = self.config.agent_dir_for(workspace) / "modspec.json"
        if not modspec_path.exists():
            raise FileNotFoundError(f"Missing modspec.json: {modspec_path}")
        return ModSpec.from_dict(json.loads(modspec_path.read_text(encoding="utf-8")))

    def _render_markdown(self, result: RepairLoopResult) -> str:
        return self.evidence_writer.render_repair_loop_report_md(result)
