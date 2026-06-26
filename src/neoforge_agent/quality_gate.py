from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class QualityGateCheck:
    name: str
    command: list[str] = field(default_factory=list)
    status: str = "pending"
    duration_seconds: float = 0.0
    return_code: int | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": list(self.command),
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "return_code": self.return_code,
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "summary": self.summary,
        }


@dataclass(slots=True)
class QualityGateResult:
    success: bool
    run_id: str
    report_dir: Path
    checks: list[QualityGateCheck]
    quality_gate_report_json_path: Path
    quality_gate_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for check in self.checks if check.status == "pass")
        failed = sum(1 for check in self.checks if check.status == "fail")
        skipped = sum(1 for check in self.checks if check.status == "skip")
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "checks": [check.to_dict() for check in self.checks],
            "passed_count": passed,
            "failed_count": failed,
            "skipped_count": skipped,
            "checks_count": len(self.checks),
            "quality_gate_report_json_path": str(self.quality_gate_report_json_path),
            "quality_gate_report_md_path": str(self.quality_gate_report_md_path),
        }


class QualityGateRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        eval_limit: int = 10,
        run_doctor: bool = True,
        run_doctor_java: bool = False,
        doctor_strict: bool = False,
        run_compile: bool = True,
        run_unittest: bool = True,
        run_schema: bool = True,
        run_examples: bool = True,
        run_eval: bool = True,
        run_golden: bool = True,
        run_failure_lab: bool = True,
        run_repair_eval: bool = True,
        run_build_smoke: bool = False,
        timeout_seconds: int = 900,
    ) -> QualityGateResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        report_dir = ensure_directory(self.config.workspace_root / "quality-gate-runs" / run_id / ".agent")
        logs_dir = ensure_directory(report_dir / "logs")

        checks: list[QualityGateCheck] = []
        if run_doctor:
            doctor_command = [
                sys.executable,
                "-m",
                "agent.cli",
                "doctor",
                "--run-name",
                f"{run_id}-doctor",
                "--json",
            ]
            if not run_doctor_java:
                doctor_command.insert(-1, "--no-java")
            if doctor_strict:
                doctor_command.insert(-1, "--strict")
            checks.append(
                self._run_command(
                    "doctor_environment",
                    doctor_command,
                    logs_dir=logs_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
        else:
            checks.append(self._skipped("doctor_environment", "Environment doctor disabled."))

        if run_compile:
            checks.append(
                self._run_command(
                    "python_compileall",
                    [sys.executable, "-m", "compileall", "-q", "src", "tests"],
                    logs_dir=logs_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
        else:
            checks.append(self._skipped("python_compileall", "Compile check disabled."))

        if run_unittest:
            checks.append(
                self._run_command(
                    "unittest",
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                    logs_dir=logs_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
        else:
            checks.append(self._skipped("unittest", "Unit tests disabled."))

        if run_schema:
            checks.append(
                self._run_command(
                    "print_schema",
                    [sys.executable, "-m", "agent.cli", "print-schema", "--json"],
                    logs_dir=logs_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
        else:
            checks.append(self._skipped("print_schema", "Schema check disabled."))

        if run_examples:
            checks.append(
                self._run_command(
                    "test_examples",
                    [sys.executable, "-m", "agent.cli", "test-examples", "--no-build", "--json"],
                    logs_dir=logs_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
        else:
            checks.append(self._skipped("test_examples", "Example spec regression disabled."))

        if run_eval:
            checks.append(
                self._run_command(
                    "eval_smoke",
                    [
                        sys.executable,
                        "-m",
                        "agent.cli",
                        "eval",
                        "--planner",
                        "llm",
                        "--llm-provider",
                        "mock",
                        "--no-build",
                        "--audit",
                        "--limit",
                        str(max(0, eval_limit)),
                        "--run-name",
                        f"{run_id}-eval",
                        "--json",
                    ],
                    logs_dir=logs_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
        else:
            checks.append(self._skipped("eval_smoke", "Eval smoke disabled."))

        if run_golden:
            checks.append(
                self._run_command(
                    "golden_tests",
                    [
                        sys.executable,
                        "-m",
                        "agent.cli",
                        "golden-test",
                        "--run-name",
                        f"{run_id}-golden",
                        "--json",
                    ],
                    logs_dir=logs_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
        else:
            checks.append(self._skipped("golden_tests", "Golden snapshot tests disabled."))

        if run_failure_lab:
            checks.append(
                self._run_command(
                    "failure_lab",
                    [
                        sys.executable,
                        "-m",
                        "agent.cli",
                        "failure-lab",
                        "--run-name",
                        f"{run_id}-failure-lab",
                        "--json",
                    ],
                    logs_dir=logs_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
        else:
            checks.append(self._skipped("failure_lab", "Failure injection lab disabled."))

        if run_repair_eval:
            checks.append(
                self._run_command(
                    "repair_eval",
                    [
                        sys.executable,
                        "-m",
                        "agent.cli",
                        "repair-eval",
                        "--run-name",
                        f"{run_id}-repair-eval",
                        "--json",
                    ],
                    logs_dir=logs_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
        else:
            checks.append(self._skipped("repair_eval", "Repair evaluation disabled."))

        if run_build_smoke:
            checks.append(
                self._run_command(
                    "build_smoke",
                    [
                        sys.executable,
                        "-m",
                        "agent.cli",
                        "generate",
                        "--build",
                        "--audit",
                        "Create a ruby mod with ruby.",
                        "--workspace-name",
                        f"{run_id}-build-smoke",
                        "--overwrite",
                        "--json",
                    ],
                    logs_dir=logs_dir,
                    timeout_seconds=timeout_seconds,
                )
            )
        else:
            checks.append(self._skipped("build_smoke", "Build smoke disabled. Pass --build-smoke to enable it."))

        success = all(check.status in {"pass", "skip"} for check in checks)
        report_json = report_dir / "quality-gate-report.json"
        report_md = report_dir / "quality-gate-report.md"
        result = QualityGateResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            checks=checks,
            quality_gate_report_json_path=report_json,
            quality_gate_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_report_md(result))
        return result

    def _run_command(
        self,
        name: str,
        command: list[str],
        *,
        logs_dir: Path,
        timeout_seconds: int,
    ) -> QualityGateCheck:
        start = time.perf_counter()
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        env = self._subprocess_env()
        try:
            completed = subprocess.run(
                command,
                cwd=self.config.project_root,
                env=env,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
            stdout_path.write_text(completed.stdout, encoding="utf-8")
            stderr_path.write_text(completed.stderr, encoding="utf-8")
            status = "pass" if completed.returncode == 0 else "fail"
            summary = "Command completed successfully." if status == "pass" else "Command failed."
            return QualityGateCheck(
                name=name,
                command=command,
                status=status,
                duration_seconds=round(time.perf_counter() - start, 3),
                return_code=completed.returncode,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                summary=summary,
            )
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(_timeout_text(exc.stdout), encoding="utf-8")
            stderr_path.write_text(_timeout_text(exc.stderr), encoding="utf-8")
            return QualityGateCheck(
                name=name,
                command=command,
                status="fail",
                duration_seconds=round(time.perf_counter() - start, 3),
                return_code=None,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                summary=f"Command timed out after {timeout_seconds} seconds.",
            )

    def _subprocess_env(self) -> dict[str, str]:
        env = os.environ.copy()
        src_path = str(self.config.project_root / "src")
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"
        env["NEOFORGE_AGENT_ROOT"] = str(self.config.project_root)
        env["NEOFORGE_AGENT_TEMPLATES_ROOT"] = str(self.config.templates_root)
        env["NEOFORGE_AGENT_WORKSPACE_ROOT"] = str(self.config.workspace_root)
        return env

    def _skipped(self, name: str, summary: str) -> QualityGateCheck:
        return QualityGateCheck(name=name, status="skip", summary=summary)

    def _render_report_md(self, result: QualityGateResult) -> str:
        payload = result.to_dict()
        lines = [
            "# Quality Gate Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Run ID: `{result.run_id}`",
            f"Passed: {payload['passed_count']}",
            f"Failed: {payload['failed_count']}",
            f"Skipped: {payload['skipped_count']}",
            "",
            "## Checks",
            "",
        ]
        for check in result.checks:
            lines.append(f"- `{check.name}` `{check.status}`: {check.summary}")
            if check.command:
                lines.append(f"  - command: `{' '.join(check.command)}`")
            if check.stdout_path:
                lines.append(f"  - stdout: `{check.stdout_path}`")
            if check.stderr_path:
                lines.append(f"  - stderr: `{check.stderr_path}`")
        lines.append("")
        return "\n".join(lines)


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
