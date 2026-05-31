from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .llm_client import check_llm_provider_health
from .tools import ensure_directory, load_template_java_version, write_json, write_text


@dataclass(slots=True)
class DoctorCheck:
    id: str
    status: str
    message: str
    path: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "message": self.message,
            "path": self.path,
            "details": self.details or {},
        }


@dataclass(slots=True)
class DoctorResult:
    success: bool
    run_id: str
    report_dir: Path
    checks: list[DoctorCheck]
    doctor_report_json_path: Path
    doctor_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for check in self.checks if check.status == "pass")
        warnings = sum(1 for check in self.checks if check.status == "warning")
        failed = sum(1 for check in self.checks if check.status == "fail")
        skipped = sum(1 for check in self.checks if check.status == "skip")
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "checks": [check.to_dict() for check in self.checks],
            "passed_count": passed,
            "warnings_count": warnings,
            "failed_count": failed,
            "skipped_count": skipped,
            "checks_count": len(self.checks),
            "doctor_report_json_path": str(self.doctor_report_json_path),
            "doctor_report_md_path": str(self.doctor_report_md_path),
        }


class EnvironmentDoctor:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        check_java: bool = True,
        strict: bool = False,
    ) -> DoctorResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        report_dir = ensure_directory(self.config.workspace_root / "doctor-runs" / run_id / ".agent")

        checks: list[DoctorCheck] = []
        checks.extend(self._check_python())
        checks.extend(self._check_project_layout())
        checks.extend(self._check_template())
        checks.extend(self._check_workspace())
        checks.extend(self._check_pythonpath())
        checks.extend(self._check_optional_docs())
        checks.append(self._check_llm_provider_config())
        checks.append(self._check_java() if check_java else self._skip("java.version", "Java check disabled."))

        success = not any(check.status == "fail" for check in checks)
        if strict and any(check.status == "warning" for check in checks):
            success = False

        report_json = report_dir / "doctor-report.json"
        report_md = report_dir / "doctor-report.md"
        result = DoctorResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            checks=checks,
            doctor_report_json_path=report_json,
            doctor_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_report_md(result, strict=strict))
        return result

    def _check_python(self) -> list[DoctorCheck]:
        version = sys.version_info
        version_text = f"{version.major}.{version.minor}.{version.micro}"
        status = "pass" if (version.major, version.minor) >= (3, 11) else "fail"
        return [
            DoctorCheck(
                id="python.version",
                status=status,
                message=f"Python {version_text} detected.",
                details={
                    "executable": sys.executable,
                    "required": ">=3.11",
                    "version": version_text,
                },
            )
        ]

    def _check_project_layout(self) -> list[DoctorCheck]:
        required_paths = [
            ("project.root", self.config.project_root, "Project root exists."),
            ("src.neoforge_agent", self.config.project_root / "src" / "neoforge_agent", "Main package exists."),
            ("src.agent_cli", self.config.project_root / "src" / "agent" / "cli.py", "Compatibility CLI entrypoint exists."),
            ("pyproject", self.config.project_root / "pyproject.toml", "pyproject.toml exists."),
            ("readme", self.config.project_root / "README.md", "README.md exists."),
        ]
        return [self._path_check(check_id, path, message) for check_id, path, message in required_paths]

    def _check_template(self) -> list[DoctorCheck]:
        checks = [
            self._path_check("template.root", self.config.template_dir, "NeoForge template directory exists."),
            self._path_check("template.build_gradle", self.config.template_dir / "build.gradle", "Template build.gradle exists."),
            self._path_check("template.settings_gradle", self.config.template_dir / "settings.gradle", "Template settings.gradle exists."),
            self._path_check("template.gradlew_bat", self.config.template_dir / "gradlew.bat", "Template Windows Gradle wrapper exists."),
            self._path_check("template.gradle_wrapper", self.config.template_dir / "gradle" / "wrapper" / "gradle-wrapper.properties", "Template Gradle wrapper properties exist."),
            self._path_check("template.src_main", self.config.template_dir / "src" / "main", "Template src/main exists."),
        ]

        template_java = load_template_java_version(self.config.template_dir)
        if template_java is None:
            checks.append(
                DoctorCheck(
                    id="template.java_version",
                    status="warning",
                    message="Could not detect Java toolchain version from template build.gradle.",
                    path=str(self.config.template_dir / "build.gradle"),
                )
            )
        elif template_java == self.config.java_version:
            checks.append(
                DoctorCheck(
                    id="template.java_version",
                    status="pass",
                    message=f"Template Java toolchain matches config target {self.config.java_version}.",
                    path=str(self.config.template_dir / "build.gradle"),
                    details={"template_java_version": template_java, "config_java_version": self.config.java_version},
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    id="template.java_version",
                    status="warning",
                    message=f"Template Java toolchain is {template_java}, config target is {self.config.java_version}.",
                    path=str(self.config.template_dir / "build.gradle"),
                    details={"template_java_version": template_java, "config_java_version": self.config.java_version},
                )
            )
        return checks

    def _check_workspace(self) -> list[DoctorCheck]:
        workspace = self.config.workspace_root
        if workspace.exists():
            status = "pass" if workspace.is_dir() else "fail"
            message = "Workspace root exists." if workspace.is_dir() else "Workspace root exists but is not a directory."
        else:
            status = "warning"
            message = "Workspace root does not exist yet; generation will create it."

        parent = workspace.parent
        writable = parent.exists() and os.access(parent, os.W_OK)
        checks = [
            DoctorCheck(
                id="workspace.root",
                status=status,
                message=message,
                path=str(workspace),
            ),
            DoctorCheck(
                id="workspace.parent_writable",
                status="pass" if writable else "fail",
                message="Workspace parent is writable." if writable else "Workspace parent is not writable or does not exist.",
                path=str(parent),
            ),
        ]
        return checks

    def _check_pythonpath(self) -> list[DoctorCheck]:
        src_path = str((self.config.project_root / "src").resolve())
        entries = [str(Path(entry).resolve()) for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep) if entry]
        if src_path in entries:
            return [
                DoctorCheck(
                    id="pythonpath.src",
                    status="pass",
                    message="PYTHONPATH includes project src directory.",
                    path=src_path,
                )
            ]
        return [
            DoctorCheck(
                id="pythonpath.src",
                status="warning",
                message="PYTHONPATH does not include project src directory. Local `py -m agent.cli` commands may need `$env:PYTHONPATH = (Resolve-Path .\\src)`.",
                path=src_path,
                details={"pythonpath": os.environ.get("PYTHONPATH", "")},
            )
        ]

    def _check_optional_docs(self) -> list[DoctorCheck]:
        docs = [
            ("docs.modspec", self.config.project_root / "docs" / "modspec.md", "ModSpec docs exist."),
            ("docs.test_matrix", self.config.project_root / "docs" / "test-matrix.md", "Test matrix docs exist."),
            ("docs.quality_gate", self.config.project_root / "docs" / "quality-gate.md", "Quality gate docs exist."),
            ("docs.ci", self.config.project_root / "docs" / "ci.md", "CI docs exist."),
            ("github.workflow", self.config.project_root / ".github" / "workflows" / "quality-gate.yml", "GitHub Actions quality gate workflow exists."),
        ]
        return [self._path_check(check_id, path, message, missing_status="warning") for check_id, path, message in docs]

    def _check_llm_provider_config(self) -> DoctorCheck:
        health = check_llm_provider_health("openai-compatible")
        details = health.to_dict()
        if health.healthy:
            return DoctorCheck(
                id="llm.openai_compatible",
                status="pass",
                message="OpenAI-compatible provider health check passed.",
                details=details,
            )
        return DoctorCheck(
            id="llm.openai_compatible",
            status="warning",
            message="OpenAI-compatible provider health check recommends fallback; mock LLM and rules fallback remain available.",
            details=details,
        )

    def _check_java(self) -> DoctorCheck:
        java_exe = shutil.which("java")
        if not java_exe:
            return DoctorCheck(
                id="java.version",
                status="fail",
                message="Java executable was not found on PATH.",
                details={"required_target": self.config.java_version},
            )

        try:
            completed = subprocess.run(
                [java_exe, "-version"],
                cwd=self.config.project_root,
                text=True,
                capture_output=True,
                timeout=15,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return DoctorCheck(
                id="java.version",
                status="fail",
                message=f"Could not execute java -version: {exc}",
                path=java_exe,
                details={"required_target": self.config.java_version},
            )

        output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
        major = _parse_java_major(output)
        if completed.returncode != 0:
            return DoctorCheck(
                id="java.version",
                status="fail",
                message="java -version returned a non-zero exit code.",
                path=java_exe,
                details={"return_code": completed.returncode, "output": output, "required_target": self.config.java_version},
            )
        if major is None:
            return DoctorCheck(
                id="java.version",
                status="warning",
                message="Java is available, but the version could not be parsed.",
                path=java_exe,
                details={"output": output, "required_target": self.config.java_version},
            )
        if major < self.config.java_version:
            return DoctorCheck(
                id="java.version",
                status="warning",
                message=f"java -version reports Java {major}, while the template target is Java {self.config.java_version}. Gradle toolchains may still provide the required JDK.",
                path=java_exe,
                details={"java_major": major, "required_target": self.config.java_version, "output": output},
            )
        return DoctorCheck(
            id="java.version",
            status="pass",
            message=f"Java {major} is available.",
            path=java_exe,
            details={"java_major": major, "required_target": self.config.java_version, "output": output},
        )

    def _path_check(
        self,
        check_id: str,
        path: Path,
        message: str,
        *,
        missing_status: str = "fail",
    ) -> DoctorCheck:
        if path.exists():
            return DoctorCheck(id=check_id, status="pass", message=message, path=str(path))
        return DoctorCheck(
            id=check_id,
            status=missing_status,
            message=f"Missing: {path}",
            path=str(path),
        )

    def _skip(self, check_id: str, message: str) -> DoctorCheck:
        return DoctorCheck(id=check_id, status="skip", message=message)

    def _render_report_md(self, result: DoctorResult, *, strict: bool) -> str:
        payload = result.to_dict()
        lines = [
            "# Doctor Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Run ID: `{result.run_id}`",
            f"Strict: {str(strict).lower()}",
            f"Passed: {payload['passed_count']}",
            f"Warnings: {payload['warnings_count']}",
            f"Failed: {payload['failed_count']}",
            f"Skipped: {payload['skipped_count']}",
            "",
            "## Checks",
            "",
        ]
        for check in result.checks:
            lines.append(f"- `{check.id}` `{check.status}`: {check.message}")
            if check.path:
                lines.append(f"  - path: `{check.path}`")
        lines.append("")
        return "\n".join(lines)


def _parse_java_major(output: str) -> int | None:
    match = re.search(r'version\s+"([^"]+)"', output)
    if not match:
        match = re.search(r"openjdk\s+(\d+(?:\.\d+)*)", output, flags=re.IGNORECASE)
    if not match:
        return None
    version = match.group(1)
    parts = version.split(".")
    if not parts:
        return None
    if parts[0] == "1" and len(parts) > 1 and parts[1].isdigit():
        return int(parts[1])
    return int(parts[0]) if parts[0].isdigit() else None
