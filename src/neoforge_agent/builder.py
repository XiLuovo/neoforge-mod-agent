from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from typing import TextIO

from .config import AppConfig
from .models import BuildResult
from .repair import RepairArtifactGenerator
from .tools import ensure_directory, write_json


class GradleBuilder:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()
        self.repair_generator = RepairArtifactGenerator(self.config)

    def build(self, project_dir: Path, task: str | None = None, *, repair: bool = False) -> BuildResult:
        project_dir = project_dir.resolve()
        gradle_task = task or self.config.gradle_task
        logs_dir = ensure_directory(self.config.logs_dir_for(project_dir))
        gradle_user_home = ensure_directory(self.config.gradle_user_home)
        stdout_path = logs_dir / f"gradle-{gradle_task}.stdout.log"
        stderr_path = logs_dir / f"gradle-{gradle_task}.stderr.log"
        log_path = logs_dir / f"gradle-{gradle_task}.log"
        metadata_path = logs_dir / f"gradle-{gradle_task}.json"

        try:
            command = self._gradle_command(project_dir, gradle_task)
        except FileNotFoundError as exc:
            result = BuildResult(
                attempted=True,
                success=False,
                summary=str(exc),
            )
            write_json(metadata_path, result.to_dict())
            return result

        before_jars = self._snapshot_jars(project_dir)
        timed_out = False

        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle, log_path.open("w", encoding="utf-8") as log_handle:
            log_handle.write(f"$ {' '.join(command)}\n")
            log_handle.write(f"$ GRADLE_USER_HOME={gradle_user_home}\n")
            log_handle.flush()
            env = os.environ.copy()
            env["GRADLE_USER_HOME"] = str(gradle_user_home)

            try:
                process = subprocess.Popen(
                    command,
                    cwd=project_dir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
            except OSError as exc:
                result = BuildResult(
                    attempted=True,
                    success=False,
                    command=command,
                    log_path=log_path,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    summary=f"Failed to start Gradle: {exc}",
                )
                log_handle.write(f"\n[launcher] {exc}\n")
                write_json(metadata_path, result.to_dict())
                return result

            lock = threading.Lock()
            stdout_thread = threading.Thread(
                target=self._pump_stream,
                args=(process.stdout, stdout_handle, log_handle, "stdout", lock),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._pump_stream,
                args=(process.stderr, stderr_handle, log_handle, "stderr", lock),
                daemon=True,
            )
            stdout_thread.start()
            stderr_thread.start()

            try:
                return_code = process.wait(timeout=self.config.build_timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                return_code = process.wait()
                with lock:
                    log_handle.write(
                        f"\n[builder] Gradle build timed out after {self.config.build_timeout_seconds} seconds.\n"
                    )
                    log_handle.flush()

            stdout_thread.join()
            stderr_thread.join()

        jar_path = self._detect_jar(project_dir, before_jars) if return_code == 0 else None
        if timed_out:
            summary = f"Gradle build timed out after {self.config.build_timeout_seconds} seconds."
            success = False
        elif return_code == 0:
            success = True
            summary = "Gradle build completed successfully."
            if jar_path is None:
                summary = "Gradle build completed successfully, but no output jar was detected."
        else:
            success = False
            summary = "Gradle build failed."

        repair_artifacts = None
        if not success:
            repair_artifacts = self.repair_generator.generate(
                project_dir=project_dir,
                command=command,
                exit_code=return_code,
                log_path=log_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
        result = BuildResult(
            attempted=True,
            success=success,
            command=command,
            return_code=return_code,
            jar_path=jar_path,
            log_path=log_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            debug_context_path=repair_artifacts.debug_context_path if repair_artifacts else None,
            fix_request_path=repair_artifacts.fix_request_path if repair_artifacts else None,
            suspected_errors_path=repair_artifacts.suspected_errors_path if repair_artifacts else None,
            issues=repair_artifacts.issues if repair_artifacts else [],
            summary=summary,
        )
        write_json(metadata_path, result.to_dict())
        return result

    def _gradle_command(self, project_dir: Path, task: str) -> list[str]:
        if os.name == "nt":
            wrapper = project_dir / "gradlew.bat"
            if not wrapper.exists():
                raise FileNotFoundError(f"Gradle wrapper not found: {wrapper}")
            return [
                os.environ.get("COMSPEC", "cmd.exe"),
                "/c",
                "gradlew.bat",
                task,
                "--console=plain",
                "--no-configuration-cache",
            ]

        wrapper = project_dir / "gradlew"
        if not wrapper.exists():
            raise FileNotFoundError(f"Gradle wrapper not found: {wrapper}")
        return [str(wrapper), task, "--console=plain", "--no-configuration-cache"]

    def _pump_stream(
        self,
        stream: TextIO | None,
        destination: TextIO,
        combined_log: TextIO,
        label: str,
        lock: threading.Lock,
    ) -> None:
        if stream is None:
            return

        try:
            for line in iter(stream.readline, ""):
                destination.write(line)
                destination.flush()
                with lock:
                    combined_log.write(f"[{label}] {line}")
                    combined_log.flush()
        finally:
            stream.close()

    def _snapshot_jars(self, project_dir: Path) -> dict[Path, int]:
        libs_dir = project_dir / "build" / "libs"
        if not libs_dir.exists():
            return {}
        snapshot: dict[Path, int] = {}
        for jar in libs_dir.glob("*.jar"):
            if jar.name.endswith("-sources.jar") or jar.name.endswith("-javadoc.jar"):
                continue
            snapshot[jar] = jar.stat().st_mtime_ns
        return snapshot

    def _detect_jar(self, project_dir: Path, before_jars: dict[Path, int]) -> Path | None:
        libs_dir = project_dir / "build" / "libs"
        if not libs_dir.exists():
            return None

        candidates: list[Path] = []
        changed: list[Path] = []
        for jar in libs_dir.glob("*.jar"):
            if jar.name.endswith("-sources.jar") or jar.name.endswith("-javadoc.jar"):
                continue
            candidates.append(jar)
            previous = before_jars.get(jar)
            current = jar.stat().st_mtime_ns
            if previous is None or current != previous:
                changed.append(jar)

        if changed:
            return max(changed, key=lambda item: item.stat().st_mtime_ns)
        if candidates:
            return max(candidates, key=lambda item: item.stat().st_mtime_ns)
        return None
