from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import AppConfig
from .models import BuildResult, JavaExtensionSpec, ModSpec
from .project_generator import ProjectLayout
from .tools import write_json, write_text


JAVA_EXTENSION_CLASS_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*$")
JAVA_EXTENSION_METHOD_PATTERN = re.compile(r"^[a-z][A-Za-z0-9]*$")
SUPPORTED_JAVA_EXTENSION_RETURN_TYPES = {"String"}
SUPPORTED_JAVA_EXTENSION_IMPORTS = {
    "net.minecraft.core.BlockPos",
    "net.minecraft.network.chat.Component",
    "net.minecraft.resources.ResourceLocation",
}
JAVA_EXTENSION_INPUT_FORBIDDEN_TOKENS = {
    "ClassLoader",
    "Files",
    "Path",
    "ProcessBuilder",
    "Runtime",
    "System.exit",
    "Thread",
    "Unsafe",
    "import ",
    "java.io",
    "java.net",
    "java.nio",
    "javax",
    "native ",
    "package ",
    "reflect",
    "sun.",
}
JAVA_EXTENSION_SOURCE_FORBIDDEN_TOKENS = {
    token
    for token in JAVA_EXTENSION_INPUT_FORBIDDEN_TOKENS
    if token not in {"import ", "package "}
}


@dataclass(slots=True)
class JavaExtensionGenerationResult:
    java_files: list[Path] = field(default_factory=list)
    report_files: list[Path] = field(default_factory=list)
    diff_files: list[Path] = field(default_factory=list)
    rollback_files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def artifacts(self) -> list[Path]:
        return [*self.java_files, *self.report_files, *self.diff_files, *self.rollback_files]


class JavaExtensionGenerator:
    def generate(self, layout: ProjectLayout, spec: ModSpec) -> JavaExtensionGenerationResult:
        if not spec.java_extensions:
            return JavaExtensionGenerationResult()

        extension_dir = layout.package_dir / "extension"
        java_files: list[Path] = []
        warnings: list[str] = []
        report_entries: list[dict] = []
        source_by_path: dict[Path, str] = {}

        for extension in spec.java_extensions:
            path = extension_dir / f"{extension.class_name}.java"
            source = self._render_extension(spec, extension)
            write_text(path, source)
            java_files.append(path)
            source_by_path[path] = source
            report_entries.append(
                {
                    "id": extension.identifier,
                    "class_name": extension.class_name,
                    "path": str(path.relative_to(layout.project_dir)),
                    "package": f"{spec.package_name}.extension",
                    "purpose": extension.purpose,
                    "explanation": extension.explanation,
                    "allowed_imports": list(extension.allowed_imports),
                    "methods": [
                        {
                            "name": method.name,
                            "return_type": method.return_type,
                            "explanation": method.explanation,
                        }
                        for method in extension.methods
                    ],
                    "status": "generated",
                }
            )

        report_payload = {
            "version": "6.1",
            "status": "pending-build",
            "sandbox": {
                "mode": "managed-additive-class",
                "managed_package_suffix": "extension",
                "existing_source_edits": False,
                "allowed_return_types": sorted(SUPPORTED_JAVA_EXTENSION_RETURN_TYPES),
                "allowed_imports": sorted(SUPPORTED_JAVA_EXTENSION_IMPORTS),
            },
            "build_gate": _build_gate_payload(BuildResult(attempted=False, success=None, summary="Gradle build was not executed.")),
            "compile_gate": "Run the Gradle build gate for formal V6.1 acceptance; generation and audit only prove structure and sandbox constraints.",
            "rollback": "Use java-extension-rollback-report.json to remove managed extension classes and regenerate from a previous ModSpec snapshot.",
            "proof_artifacts": {
                "diff_report": ".agent/java-extension-diff.md",
                "rollback_report_json": ".agent/java-extension-rollback-report.json",
                "rollback_report_md": ".agent/java-extension-rollback-report.md",
            },
            "extensions": report_entries,
        }
        rollback_payload = self._rollback_payload(spec, report_entries)
        report_json = layout.project_dir / ".agent" / "java-extension-report.json"
        report_md = layout.project_dir / ".agent" / "java-extension-report.md"
        diff_md = layout.project_dir / ".agent" / "java-extension-diff.md"
        rollback_json = layout.project_dir / ".agent" / "java-extension-rollback-report.json"
        rollback_md = layout.project_dir / ".agent" / "java-extension-rollback-report.md"
        write_json(report_json, report_payload)
        write_text(report_md, self._render_report_md(report_payload))
        write_text(diff_md, self._render_diff_md(layout, source_by_path))
        write_json(rollback_json, rollback_payload)
        write_text(rollback_md, self._render_rollback_md(rollback_payload))
        return JavaExtensionGenerationResult(
            java_files=java_files,
            report_files=[report_json, report_md],
            diff_files=[diff_md],
            rollback_files=[rollback_json, rollback_md],
            warnings=warnings,
        )

    def _render_extension(self, spec: ModSpec, extension: JavaExtensionSpec) -> str:
        imports = [
            f"import {import_line};"
            for import_line in sorted(set(extension.allowed_imports))
            if import_line in SUPPORTED_JAVA_EXTENSION_IMPORTS
        ]
        lines = [
            f"package {spec.package_name}.extension;",
            "",
            *imports,
            *([""] if imports else []),
            "/**",
            f" * Controlled Java extension: {self._javadoc_text(extension.purpose)}",
            f" * Explanation: {self._javadoc_text(extension.explanation)}",
            " * This class is generated only from structured ModSpec fields.",
            " */",
            f"public final class {extension.class_name} {{",
            f"    private {extension.class_name}() {{",
            "    }",
            "",
        ]
        method_blocks: list[str] = []
        for method in extension.methods:
            method_blocks.append(
                "\n".join(
                    [
                        "    /**",
                        f"     * {self._javadoc_text(method.explanation or extension.purpose)}",
                        "     */",
                        f"    public static {method.return_type} {method.name}() {{",
                        f'        return "{self._java_string(method.return_value)}";',
                        "    }",
                    ]
                )
            )
        lines.append("\n\n".join(method_blocks))
        lines.extend(["}", ""])
        return "\n".join(lines)

    def _render_report_md(self, payload: dict) -> str:
        lines = [
            "# Java Extension Report",
            "",
            f"Status: `{payload['status']}`",
            "Sandbox: managed additive classes only",
            f"Build gate: `{payload.get('build_gate', {}).get('status', 'unknown')}`",
            "",
            "## Extensions",
            "",
        ]
        for entry in payload["extensions"]:
            lines.extend(
                [
                    f"- `{entry['class_name']}`",
                    f"  - id: `{entry['id']}`",
                    f"  - path: `{entry['path']}`",
                    f"  - purpose: {entry['purpose']}",
                    f"  - explanation: {entry['explanation']}",
                ]
            )
        proof = payload.get("proof_artifacts", {})
        lines.extend(
            [
                "",
                "## Gates",
                "",
                f"- Compile: {payload['compile_gate']}",
                f"- Rollback: {payload['rollback']}",
                f"- Diff report: `{proof.get('diff_report', '.agent/java-extension-diff.md')}`",
                f"- Rollback report: `{proof.get('rollback_report_json', '.agent/java-extension-rollback-report.json')}`",
                "",
            ]
        )
        gate = payload.get("build_gate", {})
        if gate:
            lines.extend(
                [
                    "## Build Gate",
                    "",
                    f"- attempted: `{str(gate.get('attempted')).lower()}`",
                    f"- success: `{gate.get('success')}`",
                    f"- status: `{gate.get('status')}`",
                    f"- summary: {gate.get('summary', '')}",
                    "",
                ]
            )
        return "\n".join(lines)

    def _rollback_payload(self, spec: ModSpec, entries: list[dict]) -> dict:
        managed_files = [entry["path"] for entry in entries]
        return {
            "version": "6.1",
            "status": "standby",
            "rollback_required": False,
            "trigger": "not_run",
            "reason": "No failed V6.1 gate has requested rollback.",
            "managed_files": managed_files,
            "modspec_entries": [extension.identifier for extension in spec.java_extensions],
            "rollback_steps": [
                "Remove the listed java_extension entries from ModSpec.",
                "Regenerate the workspace from the previous .agent/modspec.json snapshot or a clean spec.",
                "Verify that the listed managed extension files are no longer present.",
                "Rerun audit and, for formal acceptance, Gradle build.",
            ],
            "build_gate": _build_gate_payload(BuildResult(attempted=False, success=None, summary="Gradle build was not executed.")),
            "failure": None,
        }

    def _render_diff_md(self, layout: ProjectLayout, source_by_path: dict[Path, str]) -> str:
        lines = [
            "# Java Extension Class Diff",
            "",
            "Generated extension classes are additive managed files. The diff below is rendered as a new-file review artifact.",
            "",
        ]
        for path, source in source_by_path.items():
            relative = str(path.relative_to(layout.project_dir)).replace("\\", "/")
            lines.extend(
                [
                    "```diff",
                    "--- /dev/null",
                    f"+++ b/{relative}",
                ]
            )
            lines.extend(f"+{line}" for line in source.splitlines())
            lines.extend(["```", ""])
        return "\n".join(lines)

    def _render_rollback_md(self, payload: dict) -> str:
        lines = [
            "# Java Extension Rollback Report",
            "",
            f"Status: `{payload['status']}`",
            f"Rollback required: `{str(payload['rollback_required']).lower()}`",
            f"Trigger: `{payload['trigger']}`",
            f"Reason: {payload['reason']}",
            "",
            "## Managed Files",
            "",
        ]
        lines.extend(f"- `{path}`" for path in payload["managed_files"])
        lines.extend(["", "## Rollback Steps", ""])
        lines.extend(f"{index}. {step}" for index, step in enumerate(payload["rollback_steps"], start=1))
        gate = payload.get("build_gate", {})
        if gate:
            lines.extend(
                [
                    "",
                    "## Build Gate",
                    "",
                    f"- attempted: `{str(gate.get('attempted')).lower()}`",
                    f"- success: `{gate.get('success')}`",
                    f"- status: `{gate.get('status')}`",
                    f"- summary: {gate.get('summary', '')}",
                ]
            )
        return "\n".join(lines) + "\n"

    def _java_string(self, value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )

    def _javadoc_text(self, value: str) -> str:
        return value.replace("*/", "* /").replace("\r", " ").replace("\n", " ").strip()


def finalize_java_extension_acceptance(
    project_dir: Path,
    config: AppConfig,
    spec: ModSpec,
    build_result: BuildResult,
) -> list[Path]:
    if not spec.java_extensions:
        return []

    agent_dir = config.agent_dir_for(project_dir)
    report_json = agent_dir / "java-extension-report.json"
    report_md = agent_dir / "java-extension-report.md"
    rollback_json = agent_dir / "java-extension-rollback-report.json"
    rollback_md = agent_dir / "java-extension-rollback-report.md"

    report_payload = _load_json(report_json)
    rollback_payload = _load_json(rollback_json)
    build_gate = _build_gate_payload(build_result)

    report_payload["version"] = "6.1"
    report_payload["build_gate"] = build_gate
    report_payload["status"] = _acceptance_status(build_gate)
    report_payload.setdefault(
        "proof_artifacts",
        {
            "diff_report": ".agent/java-extension-diff.md",
            "rollback_report_json": ".agent/java-extension-rollback-report.json",
            "rollback_report_md": ".agent/java-extension-rollback-report.md",
        },
    )

    rollback_payload["version"] = "6.1"
    rollback_payload["build_gate"] = build_gate
    rollback_payload["status"] = _rollback_status(build_gate)
    rollback_payload["rollback_required"] = bool(build_result.attempted and build_result.success is False)
    rollback_payload["trigger"] = build_gate["status"]
    rollback_payload["reason"] = _rollback_reason(build_gate)
    rollback_payload["failure"] = (
        {
            "summary": build_result.summary,
            "return_code": build_result.return_code,
            "log_path": str(build_result.log_path) if build_result.log_path else None,
            "stdout_path": str(build_result.stdout_path) if build_result.stdout_path else None,
            "stderr_path": str(build_result.stderr_path) if build_result.stderr_path else None,
        }
        if build_result.attempted and build_result.success is False
        else None
    )

    generator = JavaExtensionGenerator()
    write_json(report_json, report_payload)
    write_text(report_md, generator._render_report_md(report_payload))
    write_json(rollback_json, rollback_payload)
    write_text(rollback_md, generator._render_rollback_md(rollback_payload))
    return [report_json, report_md, rollback_json, rollback_md]


def _build_gate_payload(build_result: BuildResult) -> dict:
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


def _acceptance_status(build_gate: dict) -> str:
    if build_gate["status"] == "pass":
        return "pass"
    if build_gate["status"] == "fail":
        return "failed-build"
    return "pending-build"


def _rollback_status(build_gate: dict) -> str:
    if build_gate["status"] == "pass":
        return "not_needed"
    if build_gate["status"] == "fail":
        return "recommended"
    return "standby"


def _rollback_reason(build_gate: dict) -> str:
    if build_gate["status"] == "pass":
        return "The V6.1 Gradle build gate passed; rollback is not needed."
    if build_gate["status"] == "fail":
        return "The V6.1 Gradle build gate failed; remove managed extension entries or restore the previous ModSpec snapshot before regenerating."
    return "Gradle build has not run; rollback instructions are ready if a later gate fails."


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
