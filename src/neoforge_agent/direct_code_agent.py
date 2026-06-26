from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .config import AppConfig
from .evidence_writer import AgentEvidenceWriter
from .models import BuildResult
from .tools import ensure_directory, write_text


DIRECT_CODE_VERSION = "1.0"
SUPPORTED_OPERATIONS = {"write_file", "replace_text"}
SUPPORTED_RISK_LEVELS = {"low", "medium", "high"}
ALLOWED_ROOTS = {
    "src/main/java",
    "src/main/resources",
    "build.gradle",
    "gradle.properties",
    ".agent",
}
FORBIDDEN_PATH_PREFIXES = {
    ".git",
    "gradle/wrapper",
    "build",
    ".gradle",
}
FORBIDDEN_CONTENT_TOKENS = {
    "Runtime.getRuntime",
    "ProcessBuilder",
    "System.exit",
    "ClassLoader",
    "Unsafe",
    "java.lang.reflect",
    "java.io.File",
    "java.nio.file.Files",
    "java.net.",
    "javax.crypto",
    "Thread.sleep",
}


@dataclass(slots=True)
class DirectCodeChange:
    path: str
    operation: str
    reason: str
    risk_level: str
    content: str | None = None
    search: str | None = None
    replace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "path": self.path,
            "operation": self.operation,
            "reason": self.reason,
            "risk_level": self.risk_level,
        }
        if self.content is not None:
            data["content"] = self.content
        if self.search is not None:
            data["search"] = self.search
        if self.replace is not None:
            data["replace"] = self.replace
        return data


@dataclass(slots=True)
class DirectCodePlan:
    request: str
    mode: str = "direct_code"
    summary: str = ""
    changes: list[DirectCodeChange] = field(default_factory=list)
    requires_direct_code: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, request: str = "") -> "DirectCodePlan":
        plan_data = data.get("direct_code_plan") if isinstance(data.get("direct_code_plan"), dict) else data
        changes = []
        for raw_change in plan_data.get("changes", []):
            if not isinstance(raw_change, dict):
                continue
            changes.append(
                DirectCodeChange(
                    path=str(raw_change.get("path", "")),
                    operation=str(raw_change.get("operation", "")),
                    reason=str(raw_change.get("reason", "")),
                    risk_level=str(raw_change.get("risk_level", "medium")).lower(),
                    content=str(raw_change["content"]) if raw_change.get("content") is not None else None,
                    search=str(raw_change["search"]) if raw_change.get("search") is not None else None,
                    replace=str(raw_change["replace"]) if raw_change.get("replace") is not None else None,
                )
            )
        return cls(
            request=str(plan_data.get("request", request)),
            mode=str(plan_data.get("mode", "direct_code")),
            summary=str(plan_data.get("summary", "")),
            changes=changes,
            requires_direct_code=bool(plan_data.get("requires_direct_code", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": DIRECT_CODE_VERSION,
            "mode": self.mode,
            "request": self.request,
            "summary": self.summary,
            "requires_direct_code": self.requires_direct_code,
            "changes": [change.to_dict() for change in self.changes],
        }


@dataclass(slots=True)
class DirectCodeReviewResult:
    approved: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "checks": list(self.checks),
            "affected_files": list(self.affected_files),
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
        }


@dataclass(slots=True)
class DirectCodeApplyResult:
    success: bool
    plan: DirectCodePlan
    review: DirectCodeReviewResult
    changed_files: list[str]
    snapshot_files: list[str]
    artifacts: dict[str, Path]
    diff_text: str
    build: BuildResult = field(default_factory=BuildResult)
    audit_payload: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "version": DIRECT_CODE_VERSION,
            "plan": self.plan.to_dict(),
            "review": self.review.to_dict(),
            "changed_files": list(self.changed_files),
            "snapshot_files": list(self.snapshot_files),
            "artifacts": {key: str(value) for key, value in self.artifacts.items()},
            "build": self.build.to_dict(),
            "audit": dict(self.audit_payload),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


class DirectCodeAgent:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()
        self.evidence_writer = AgentEvidenceWriter(self.config)

    def review_plan(self, workspace: Path, plan: DirectCodePlan) -> DirectCodeReviewResult:
        workspace = workspace.resolve()
        errors: list[str] = []
        warnings: list[str] = []
        checks: list[dict[str, Any]] = []
        affected_files: list[str] = []

        if not plan.changes:
            errors.append("Direct Code plan must contain at least one change.")
            checks.append(_check("changes_present", "fail", "No changes were declared."))

        for index, change in enumerate(plan.changes, start=1):
            path_errors = self._validate_relative_path(change.path)
            operation_errors = self._validate_operation(change)
            content_errors = self._validate_content(change)
            change_errors = [*path_errors, *operation_errors, *content_errors]
            status = "fail" if change_errors else "pass"
            checks.append(
                _check(
                    f"change_{index}",
                    status,
                    f"{change.operation or '(missing operation)'} {change.path or '(missing path)'}",
                    errors=change_errors,
                )
            )
            errors.extend(change_errors)
            if not change_errors:
                affected_files.append(change.path)
            if change.risk_level == "high":
                warnings.append(f"High-risk direct-code change declared for {change.path}.")
            if not path_errors and normalize_direct_code_path(change.path) in {"build.gradle", "gradle.properties"}:
                warnings.append(f"Gradle-related Direct Code change requires extra build scrutiny: {change.path}.")

        snapshot_check_status = "pass" if affected_files else "fail"
        checks.append(
            _check(
                "rollback_snapshot",
                snapshot_check_status,
                "Affected files will be snapshotted before applying the Direct Code plan."
                if affected_files
                else "No affected files are available for rollback snapshot.",
            )
        )
        return DirectCodeReviewResult(
            approved=not errors,
            errors=errors,
            warnings=warnings,
            checks=checks,
            affected_files=_unique(affected_files),
        )

    def apply_plan(
        self,
        workspace: Path,
        plan: DirectCodePlan,
        *,
        build: BuildResult | None = None,
        audit_payload: dict[str, Any] | None = None,
    ) -> DirectCodeApplyResult:
        workspace = workspace.resolve()
        artifacts = self.evidence_writer.direct_code_artifacts(workspace)
        review = self.review_plan(workspace, plan)
        self.evidence_writer.write_direct_code_plan(artifacts, plan, review)

        changed_files: list[str] = []
        snapshot_files: list[str] = []
        errors: list[str] = []
        diff_text = ""
        if review.approved:
            before_text_by_path: dict[str, str] = {}
            after_text_by_path: dict[str, str] = {}
            for change in plan.changes:
                target = self.resolve_change_path(workspace, change.path)
                before = target.read_text(encoding="utf-8") if target.exists() else ""
                before_text_by_path[change.path] = before
                snapshot_path = self._snapshot_file(workspace, change.path, target)
                snapshot_files.append(str(snapshot_path.relative_to(workspace)))
                try:
                    after = self._apply_change(target, change, before)
                except ValueError as exc:
                    errors.append(str(exc))
                    break
                after_text_by_path[change.path] = after
                changed_files.append(change.path)
            diff_text = self.evidence_writer.render_direct_code_diff(before_text_by_path, after_text_by_path)
        else:
            errors.extend(review.errors)

        self.evidence_writer.write_direct_code_diff(artifacts, diff_text)
        build_result = build or BuildResult(attempted=False, success=None, summary="Gradle build was not executed.")
        audit = audit_payload or {"attempted": False, "success": None}
        success = review.approved and not errors
        report_payload = direct_code_report_payload(
            workspace=workspace,
            plan=plan,
            review=review,
            changed_files=changed_files,
            snapshot_files=snapshot_files,
            build=build_result,
            audit_payload=audit,
            success=success,
            errors=errors,
        )
        rollback_payload = direct_code_rollback_payload(report_payload, build_result, audit)
        self.evidence_writer.write_direct_code_report(artifacts, report_payload, rollback_payload)
        return DirectCodeApplyResult(
            success=success,
            plan=plan,
            review=review,
            changed_files=changed_files,
            snapshot_files=snapshot_files,
            artifacts=artifacts,
            diff_text=diff_text,
            build=build_result,
            audit_payload=audit,
            errors=errors,
            warnings=list(review.warnings),
        )

    def finalize_report(
        self,
        workspace: Path,
        result: DirectCodeApplyResult,
        *,
        build: BuildResult,
        audit_payload: dict[str, Any],
        success: bool,
    ) -> DirectCodeApplyResult:
        artifacts = result.artifacts
        report_payload = direct_code_report_payload(
            workspace=workspace.resolve(),
            plan=result.plan,
            review=result.review,
            changed_files=result.changed_files,
            snapshot_files=result.snapshot_files,
            build=build,
            audit_payload=audit_payload,
            success=success,
            errors=result.errors,
        )
        rollback_payload = direct_code_rollback_payload(report_payload, build, audit_payload)
        self.evidence_writer.write_direct_code_report(artifacts, report_payload, rollback_payload)
        result.build = build
        result.audit_payload = dict(audit_payload)
        result.success = success
        return result

    def resolve_change_path(self, workspace: Path, relative_path: str) -> Path:
        normalized = normalize_direct_code_path(relative_path)
        target = (workspace / normalized).resolve()
        workspace = workspace.resolve()
        if target != workspace and workspace not in target.parents:
            raise ValueError(f"Direct Code path escapes workspace: {relative_path}")
        return target

    def _validate_relative_path(self, relative_path: str) -> list[str]:
        errors: list[str] = []
        try:
            normalized = normalize_direct_code_path(relative_path)
        except ValueError as exc:
            return [str(exc)]
        lowered = normalized.lower()
        if not _is_allowed_path(lowered):
            errors.append(f"Direct Code path is outside allowed roots: {normalized}")
        if any(lowered == prefix or lowered.startswith(f"{prefix}/") for prefix in FORBIDDEN_PATH_PREFIXES):
            errors.append(f"Direct Code path is forbidden: {normalized}")
        if lowered.endswith(".jar") or lowered.endswith(".class"):
            errors.append(f"Direct Code cannot modify binary artifacts: {normalized}")
        return errors

    def _validate_operation(self, change: DirectCodeChange) -> list[str]:
        errors: list[str] = []
        if change.operation not in SUPPORTED_OPERATIONS:
            errors.append(f"Unsupported Direct Code operation for {change.path}: {change.operation}")
        if change.risk_level not in SUPPORTED_RISK_LEVELS:
            errors.append(f"Unsupported Direct Code risk level for {change.path}: {change.risk_level}")
        if change.operation == "write_file" and change.content is None:
            errors.append(f"write_file requires content for {change.path}.")
        if change.operation == "replace_text":
            if change.search is None or change.search == "":
                errors.append(f"replace_text requires non-empty search text for {change.path}.")
            if change.replace is None:
                errors.append(f"replace_text requires replace text for {change.path}.")
        if not change.reason.strip():
            errors.append(f"Direct Code change must include a reason for {change.path}.")
        return errors

    def _validate_content(self, change: DirectCodeChange) -> list[str]:
        text = "\n".join(part for part in (change.content, change.search, change.replace) if part)
        errors: list[str] = []
        for token in sorted(FORBIDDEN_CONTENT_TOKENS):
            if token in text:
                errors.append(f"Direct Code change for {change.path} contains forbidden token: {token}")
        if change.path.endswith(".java") and change.content:
            package_match = re.search(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_.]*);", change.content, flags=re.MULTILINE)
            if package_match is None:
                errors.append(f"Java write_file change must include a package declaration: {change.path}")
            else:
                expected_prefix = "src/main/java/"
                try:
                    normalized = normalize_direct_code_path(change.path)
                except ValueError:
                    return errors
                package_path = "/".join(package_match.group(1).split("."))
                if normalized.startswith(expected_prefix):
                    expected_package_path = normalized.removeprefix(expected_prefix).rsplit("/", 1)[0]
                    if package_path != expected_package_path:
                        errors.append(
                            f"Java package declaration does not match path for {change.path}: "
                            f"{package_match.group(1)}"
                        )
        return errors

    def _snapshot_file(self, workspace: Path, relative_path: str, target: Path) -> Path:
        snapshot_root = ensure_directory(self.config.agent_dir_for(workspace) / "direct-code-snapshots")
        normalized = normalize_direct_code_path(relative_path)
        snapshot_path = snapshot_root / normalized
        ensure_directory(snapshot_path.parent)
        if target.exists():
            shutil.copy2(target, snapshot_path)
        else:
            write_text(snapshot_path, "")
        return snapshot_path

    def _apply_change(self, target: Path, change: DirectCodeChange, before: str) -> str:
        ensure_directory(target.parent)
        if change.operation == "write_file":
            content = change.content or ""
            write_text(target, content)
            return content
        if change.operation == "replace_text":
            search = change.search or ""
            count = before.count(search)
            if count != 1:
                raise ValueError(f"replace_text expected exactly one match in {change.path}, found {count}.")
            after = before.replace(search, change.replace or "", 1)
            write_text(target, after)
            return after
        raise ValueError(f"Unsupported Direct Code operation: {change.operation}")


def direct_code_artifacts(project_dir: Path, config: AppConfig) -> dict[str, Path]:
    return AgentEvidenceWriter(config).direct_code_artifacts(project_dir)


def normalize_direct_code_path(path: str) -> str:
    if not path or not path.strip():
        raise ValueError("Direct Code path must not be empty.")
    raw = path.replace("\\", "/").strip()
    pure = PurePosixPath(raw)
    if pure.is_absolute() or re.match(r"^[A-Za-z]:", raw):
        raise ValueError(f"Direct Code path must be relative: {path}")
    parts = pure.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Direct Code path must not contain traversal segments: {path}")
    return pure.as_posix()


def direct_code_report_payload(
    *,
    workspace: Path,
    plan: DirectCodePlan,
    review: DirectCodeReviewResult,
    changed_files: list[str],
    snapshot_files: list[str],
    build: BuildResult,
    audit_payload: dict[str, Any],
    success: bool,
    errors: list[str],
) -> dict[str, Any]:
    return {
        "version": DIRECT_CODE_VERSION,
        "status": "accepted" if success else "failed",
        "success": success,
        "workspace": str(workspace),
        "mode": "direct-code-lane",
        "request": plan.request,
        "summary": plan.summary,
        "policy": {
            "patch_format": "structured-json",
            "supported_operations": sorted(SUPPORTED_OPERATIONS),
            "allowed_roots": sorted(ALLOWED_ROOTS),
            "audit_required": True,
            "build_required": True,
            "rollback_available": True,
        },
        "review": review.to_dict(),
        "changed_files": list(changed_files),
        "snapshot_files": list(snapshot_files),
        "build_gate": _build_gate_payload(build),
        "audit_gate": _audit_gate_payload(audit_payload),
        "errors": list(errors),
    }


def direct_code_rollback_payload(report_payload: dict[str, Any], build: BuildResult, audit_payload: dict[str, Any]) -> dict[str, Any]:
    build_failed = build.attempted and build.success is False
    audit_failed = audit_payload.get("attempted") and audit_payload.get("success") is False
    plan_failed = not report_payload.get("success")
    rollback_required = bool(plan_failed or build_failed or audit_failed)
    trigger = "not_run"
    reason = "No failed direct-code gate requested rollback."
    status = "standby"
    if rollback_required:
        status = "recommended"
        if audit_failed:
            trigger = "audit_fail"
            reason = "Audit failed after applying Direct Code changes."
        elif build_failed:
            trigger = "build_fail"
            reason = "Gradle build failed after applying Direct Code changes."
        else:
            trigger = "direct_code_apply_fail"
            reason = "Direct Code plan review or apply failed."
    elif build.attempted and build.success:
        status = "not_needed"
        reason = "Direct Code changes passed audit and build gates."
    return {
        "version": DIRECT_CODE_VERSION,
        "status": status,
        "rollback_required": rollback_required,
        "trigger": trigger,
        "reason": reason,
        "changed_files": list(report_payload.get("changed_files", [])),
        "snapshot_files": list(report_payload.get("snapshot_files", [])),
        "rollback_steps": [
            "Restore each changed file from the matching .agent/direct-code-snapshots entry.",
            "Re-run workspace audit.",
            "Re-run Gradle build before accepting the workspace.",
        ],
        "build_gate": _build_gate_payload(build),
        "audit_gate": _audit_gate_payload(audit_payload),
    }


def _is_allowed_path(path: str) -> bool:
    for root in ALLOWED_ROOTS:
        lowered = root.lower()
        if path == lowered or path.startswith(f"{lowered}/"):
            return True
    return False


def _check(identifier: str, status: str, summary: str, *, errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": identifier,
        "status": status,
        "summary": summary,
        "errors": list(errors or []),
    }


def _build_gate_payload(build: BuildResult) -> dict[str, Any]:
    if not build.attempted:
        status = "not_run"
    elif build.success:
        status = "pass"
    else:
        status = "fail"
    return {
        "required": True,
        "attempted": build.attempted,
        "success": build.success,
        "status": status,
        "summary": build.summary,
        "command": list(build.command),
        "return_code": build.return_code,
        "log_path": str(build.log_path) if build.log_path else None,
    }


def _audit_gate_payload(audit_payload: dict[str, Any]) -> dict[str, Any]:
    if not audit_payload.get("attempted"):
        status = "not_run"
    elif audit_payload.get("success") is True:
        status = "pass"
    else:
        status = "fail"
    return {
        "required": True,
        "attempted": bool(audit_payload.get("attempted")),
        "success": audit_payload.get("success"),
        "status": status,
        "audit_report_path": audit_payload.get("audit_report_path"),
        "errors_count": audit_payload.get("errors_count", len(audit_payload.get("errors", []) or [])),
        "warnings_count": audit_payload.get("warnings_count", len(audit_payload.get("warnings", []) or [])),
    }


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
