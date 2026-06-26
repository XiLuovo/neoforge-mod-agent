from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig
from .evidence_writer import AgentEvidenceWriter
from .models import BuildResult, ModSpec


PATCH_AGENT_VERSION = "6.2"
PATCH_AGENT_MODE = "managed-file-regeneration"
PATCH_AGENT_MANAGED_ROOTS = ["src/main/java", "src/main/resources", ".agent"]


@dataclass(slots=True, frozen=True)
class PatchAgentArtifacts:
    plan_json: Path
    plan_md: Path
    report_json: Path
    report_md: Path
    rollback_json: Path
    rollback_md: Path


def patch_agent_artifacts(project_dir: Path, config: AppConfig) -> PatchAgentArtifacts:
    paths = AgentEvidenceWriter(config).patch_agent_artifacts(project_dir)
    return PatchAgentArtifacts(
        plan_json=paths["plan_json"],
        plan_md=paths["plan_md"],
        report_json=paths["report_json"],
        report_md=paths["report_md"],
        rollback_json=paths["rollback_json"],
        rollback_md=paths["rollback_md"],
    )


def write_patch_agent_plan(
    project_dir: Path,
    config: AppConfig,
    *,
    workspace: Path,
    existing: ModSpec,
    merged: ModSpec,
    change_request: str,
    planner_mode_used: str,
    llm_provider: str,
    added: list[str],
    updated: list[str],
    skipped: list[str],
    run_build: bool,
    modspec_before_path: Path,
    modspec_after_path: Path,
    warnings: list[str] | None = None,
) -> PatchAgentArtifacts:
    artifacts = patch_agent_artifacts(project_dir, config)
    payload = _patch_plan_payload(
        workspace=workspace,
        existing=existing,
        merged=merged,
        change_request=change_request,
        planner_mode_used=planner_mode_used,
        llm_provider=llm_provider,
        added=added,
        updated=updated,
        skipped=skipped,
        run_build=run_build,
        modspec_before_path=modspec_before_path,
        modspec_after_path=modspec_after_path,
        warnings=warnings or [],
    )
    AgentEvidenceWriter(config).write_patch_agent_plan(artifacts, payload)
    return artifacts


def write_patch_agent_report(
    project_dir: Path,
    config: AppConfig,
    *,
    workspace: Path,
    artifacts: PatchAgentArtifacts,
    change_request: str,
    planner_mode_used: str,
    llm_provider: str,
    added: list[str],
    updated: list[str],
    skipped: list[str],
    generated_files: list[str],
    build_result: BuildResult,
    audit_payload: dict[str, Any],
    repair_payload: dict[str, Any],
    modify_summary_path: Path,
    modspec_before_path: Path,
    modspec_after_path: Path,
    success: bool,
    warnings: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report_payload = _patch_report_payload(
        workspace=workspace,
        artifacts=artifacts,
        change_request=change_request,
        planner_mode_used=planner_mode_used,
        llm_provider=llm_provider,
        added=added,
        updated=updated,
        skipped=skipped,
        generated_files=generated_files,
        build_result=build_result,
        audit_payload=audit_payload,
        repair_payload=repair_payload,
        modify_summary_path=modify_summary_path,
        modspec_before_path=modspec_before_path,
        modspec_after_path=modspec_after_path,
        success=success,
        warnings=warnings or [],
    )
    rollback_payload = _patch_rollback_payload(report_payload, build_result, audit_payload, repair_payload)
    AgentEvidenceWriter(config).write_patch_agent_report(artifacts, report_payload, rollback_payload)
    return report_payload, rollback_payload


def _patch_plan_payload(
    *,
    workspace: Path,
    existing: ModSpec,
    merged: ModSpec,
    change_request: str,
    planner_mode_used: str,
    llm_provider: str,
    added: list[str],
    updated: list[str],
    skipped: list[str],
    run_build: bool,
    modspec_before_path: Path,
    modspec_after_path: Path,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "version": PATCH_AGENT_VERSION,
        "status": "planned",
        "mode": PATCH_AGENT_MODE,
        "workspace": str(workspace),
        "request": change_request,
        "planner_mode": planner_mode_used,
        "llm_provider": llm_provider,
        "policy": {
            "scope": "managed files only",
            "managed_roots": list(PATCH_AGENT_MANAGED_ROOTS),
            "existing_source_edits": False,
            "raw_repo_edits": False,
            "requires_audit": True,
            "build_requested": bool(run_build),
            "rollback_available": True,
        },
        "snapshot": {
            "before_modspec": str(modspec_before_path),
            "after_modspec": str(modspec_after_path),
        },
        "changes": {
            "added": list(added),
            "updated": list(updated),
            "skipped": list(skipped),
        },
        "counts": {
            "before_features": len(list(existing.iter_features())),
            "after_features": len(list(merged.iter_features())),
        },
        "warnings": list(warnings),
        "rollback": {
            "source_snapshot": str(modspec_before_path),
            "steps": [
                "Restore the previous .agent/modspec.before.json snapshot to .agent/modspec.json if rollback is needed.",
                "Rerun modify so only managed files are regenerated from the restored snapshot.",
                "Recheck audit and build gates before accepting the change.",
            ],
        },
    }


def _patch_report_payload(
    *,
    workspace: Path,
    artifacts: PatchAgentArtifacts,
    change_request: str,
    planner_mode_used: str,
    llm_provider: str,
    added: list[str],
    updated: list[str],
    skipped: list[str],
    generated_files: list[str],
    build_result: BuildResult,
    audit_payload: dict[str, Any],
    repair_payload: dict[str, Any],
    modify_summary_path: Path,
    modspec_before_path: Path,
    modspec_after_path: Path,
    success: bool,
    warnings: list[str],
) -> dict[str, Any]:
    build_gate = _build_gate_payload(build_result)
    audit_gate = _audit_gate_payload(audit_payload)
    repair_gate = _repair_gate_payload(repair_payload)
    status = _patch_status(success, build_gate, audit_gate, repair_gate)
    return {
        "version": PATCH_AGENT_VERSION,
        "status": status,
        "success": success,
        "mode": PATCH_AGENT_MODE,
        "workspace": str(workspace),
        "request": change_request,
        "planner_mode": planner_mode_used,
        "llm_provider": llm_provider,
        "plan_path": str(artifacts.plan_json),
        "plan_markdown_path": str(artifacts.plan_md),
        "summary_path": str(modify_summary_path),
        "policy": {
            "scope": "managed files only",
            "managed_roots": list(PATCH_AGENT_MANAGED_ROOTS),
            "existing_source_edits": False,
            "raw_repo_edits": False,
        },
        "snapshot": {
            "before_modspec": str(modspec_before_path),
            "after_modspec": str(modspec_after_path),
        },
        "changes": {
            "added": list(added),
            "updated": list(updated),
            "skipped": list(skipped),
        },
        "managed_files": list(generated_files),
        "managed_file_count": len(generated_files),
        "build_gate": build_gate,
        "audit_gate": audit_gate,
        "repair_gate": repair_gate,
        "warnings": list(warnings),
    }


def _patch_rollback_payload(
    report_payload: dict[str, Any],
    build_result: BuildResult,
    audit_payload: dict[str, Any],
    repair_payload: dict[str, Any],
) -> dict[str, Any]:
    build_gate = report_payload.get("build_gate", {})
    audit_gate = report_payload.get("audit_gate", {})
    repair_gate = report_payload.get("repair_gate", {})
    rollback_required = False
    trigger = "not_run"
    reason = "No failed patch-agent gate requested rollback."
    status = "standby"

    if not audit_gate.get("attempted"):
        status = "standby"
    elif audit_gate.get("success") is False:
        rollback_required = True
        trigger = "audit_fail"
        reason = "Audit failed after regenerating managed files."
        status = "recommended"
    elif build_gate.get("status") == "fail":
        rollback_required = True
        trigger = "build_fail"
        reason = "Gradle build failed after regenerating managed files."
        status = "recommended"
    elif repair_gate.get("repair_needed") and not repair_gate.get("repair_success"):
        rollback_required = True
        trigger = "repair_fail"
        reason = "Repair was required but did not succeed."
        status = "recommended"
    elif build_gate.get("status") == "pass":
        status = "not_needed"
        reason = "The managed-file patch passed the build gate."

    return {
        "version": PATCH_AGENT_VERSION,
        "status": status,
        "rollback_required": rollback_required,
        "trigger": trigger,
        "reason": reason,
        "managed_files": list(report_payload.get("managed_files", [])),
        "managed_file_count": report_payload.get("managed_file_count", 0),
        "source_snapshot": report_payload.get("snapshot", {}).get("before_modspec", ""),
        "build_gate": build_gate,
        "audit_gate": audit_gate,
        "repair_gate": repair_gate,
        "rollback_steps": [
            "Restore .agent/modspec.before.json to .agent/modspec.json.",
            "Rerun modify so the generator rewrites only managed files from the restored snapshot.",
            "Re-run audit and, if requested, the Gradle build gate.",
        ],
        "failure": _failure_payload(build_result, audit_payload, repair_payload) if rollback_required else None,
    }


def _build_gate_payload(build_result: BuildResult) -> dict[str, Any]:
    if not build_result.attempted:
        status = "not_run"
    elif build_result.success:
        status = "pass"
    else:
        status = "fail"
    return {
        "required_for_formal_acceptance": True,
        "attempted": build_result.attempted,
        "success": build_result.success,
        "status": status,
        "command": list(build_result.command),
        "return_code": build_result.return_code,
        "jar_path": str(build_result.jar_path) if build_result.jar_path else None,
        "log_path": str(build_result.log_path) if build_result.log_path else None,
        "summary": build_result.summary,
    }


def _audit_gate_payload(audit_payload: dict[str, Any]) -> dict[str, Any]:
    errors = audit_payload.get("errors", []) if isinstance(audit_payload, dict) else []
    warnings = audit_payload.get("warnings", []) if isinstance(audit_payload, dict) else []
    return {
        "attempted": bool(audit_payload.get("attempted")) if isinstance(audit_payload, dict) else False,
        "success": audit_payload.get("success") if isinstance(audit_payload, dict) else None,
        "checked_features": int(audit_payload.get("checked_features", 0)) if isinstance(audit_payload, dict) else 0,
        "error_count": len(errors) if isinstance(errors, list) else 0,
        "warning_count": len(warnings) if isinstance(warnings, list) else 0,
        "report_path": str(audit_payload.get("audit_report_path", "")) if isinstance(audit_payload, dict) else "",
    }


def _repair_gate_payload(repair_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempted": bool(repair_payload.get("attempted")) if isinstance(repair_payload, dict) else False,
        "repair_needed": bool(repair_payload.get("repair_needed")) if isinstance(repair_payload, dict) else False,
        "repair_success": repair_payload.get("repair_success") if isinstance(repair_payload, dict) else None,
        "report_path": str(repair_payload.get("repair_loop_report_json_path", "")) if isinstance(repair_payload, dict) else "",
    }


def _patch_status(success: bool, build_gate: dict[str, Any], audit_gate: dict[str, Any], repair_gate: dict[str, Any]) -> str:
    if not success:
        if audit_gate.get("attempted") and audit_gate.get("success") is False:
            return "failed-audit"
        if build_gate.get("status") == "fail":
            return "failed-build"
        if repair_gate.get("repair_needed") and not repair_gate.get("repair_success"):
            return "failed-repair"
        return "failed"
    if build_gate.get("status") == "pass":
        return "pass"
    if audit_gate.get("attempted") and audit_gate.get("success") is False:
        return "warning"
    return "pass"


def _failure_payload(build_result: BuildResult, audit_payload: dict[str, Any], repair_payload: dict[str, Any]) -> dict[str, Any] | None:
    if build_result.attempted and build_result.success is False:
        return {
            "stage": "build",
            "return_code": build_result.return_code,
            "summary": build_result.summary,
        }
    if isinstance(audit_payload, dict) and audit_payload.get("attempted") and audit_payload.get("success") is False:
        return {
            "stage": "audit",
            "summary": "Managed-file patch failed audit.",
            "errors": list(audit_payload.get("errors", [])),
        }
    if isinstance(repair_payload, dict) and repair_payload.get("repair_needed") and not repair_payload.get("repair_success"):
        return {
            "stage": "repair",
            "summary": "Repair was needed but did not succeed.",
        }
    return None

