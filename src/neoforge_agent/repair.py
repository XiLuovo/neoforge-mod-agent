from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig
from .models import BuildErrorKind, BuildIssue
from .tools import ensure_directory, write_json


@dataclass(slots=True)
class RepairArtifacts:
    debug_context_path: Path
    fix_request_path: Path
    suspected_errors_path: Path
    issues: list[BuildIssue]


def analyze_gradle_log(log_text: str) -> list[BuildIssue]:
    issues: list[BuildIssue] = []
    lines = [_normalize_log_line(line) for line in log_text.splitlines()]

    for index, line in enumerate(lines):
        stripped = line.strip()

        file_match = re.match(r"^(?P<file>[A-Za-z]:\\.+?):(?P<line>\d+):\s*(?P<message>.+)$", stripped)
        if file_match:
            message = file_match.group("message")
            detail_message = message
            if "找不到符号" in message or "cannot find symbol" in message.lower():
                detail = _find_following_symbol(lines, index)
                if detail:
                    detail_message = f"cannot find symbol: {detail}"
            kind, suggestion = _classify_message(detail_message)
            issues.append(
                BuildIssue(
                    kind=kind,
                    message=detail_message,
                    file=_to_project_relative(file_match.group("file")),
                    line=int(file_match.group("line")),
                    suggestion=suggestion,
                )
            )
            continue

        if "cannot find symbol" in stripped.lower() or "找不到符号" in stripped:
            issues.append(BuildIssue(kind=BuildErrorKind.MISSING_SYMBOL, message=stripped, suggestion="Check imports, class names, and whether the target API exists in NeoForge 26.1."))
            continue

        if ("package " in stripped and " does not exist" in stripped) or ("程序包" in stripped and "不存在" in stripped):
            issues.append(BuildIssue(kind=BuildErrorKind.BAD_IMPORT, message=stripped, suggestion="Fix the import path or remove the dependency on the missing package."))
            continue

        if ("constructor " in stripped and " cannot be applied" in stripped) or ("构造器" in stripped and "无法应用" in stripped):
            issues.append(BuildIssue(kind=BuildErrorKind.CONSTRUCTOR_MISMATCH, message=stripped, suggestion="Check the constructor signature against the current NeoForge 26.1 / Minecraft API."))
            continue

        if "incompatible types" in stripped.lower() or "不兼容的类型" in stripped:
            issues.append(BuildIssue(kind=BuildErrorKind.INCOMPATIBLE_TYPES, message=stripped, suggestion="Adjust the generated types or method overload to match the current API."))
            continue

        if "Could not resolve" in stripped:
            issues.append(BuildIssue(kind=BuildErrorKind.DEPENDENCY_RESOLUTION, message=stripped, suggestion="Check repository availability, dependency coordinates, and TLS / network access."))
            continue

        if "Execution failed for task ':compileJava'" in stripped:
            issues.append(BuildIssue(kind=BuildErrorKind.JAVA_COMPILE, message=stripped, suggestion="Inspect the Java compiler diagnostics around this line and patch the generated Java source with minimal changes."))
            continue

        if ("json" in stripped.lower() and "parse" in stripped.lower()) or "malformed json" in stripped.lower():
            issues.append(BuildIssue(kind=BuildErrorKind.RESOURCE_JSON, message=stripped, suggestion="Validate the generated JSON resource and correct its schema for the current game version."))
            continue

        if "duplicate class" in stripped.lower() or "重复的类" in stripped:
            issues.append(BuildIssue(kind=BuildErrorKind.DUPLICATE_CLASS, message=stripped, suggestion="Remove duplicate generated sources or adjust package/class names."))
            continue

        if "unmappable character" in stripped.lower() or "encoding" in stripped.lower() or "编码" in stripped:
            issues.append(BuildIssue(kind=BuildErrorKind.ENCODING, message=stripped, suggestion="Ensure generated source and resource files use UTF-8 consistently."))
            continue

        if stripped.startswith("* What went wrong:"):
            next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
            if next_line:
                kind, suggestion = _classify_message(next_line)
                issues.append(BuildIssue(kind=kind, message=next_line, suggestion=suggestion))

    return _deduplicate_issues(issues)


class RepairArtifactGenerator:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def generate(
        self,
        *,
        project_dir: Path,
        command: list[str],
        exit_code: int | None,
        log_path: Path,
        stdout_path: Path | None = None,
        stderr_path: Path | None = None,
    ) -> RepairArtifacts:
        project_dir = project_dir.resolve()
        agent_dir = ensure_directory(self.config.agent_dir_for(project_dir))
        log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path and stderr_path.exists() else ""
        issues = analyze_gradle_log(stderr_text or log_text)

        suspected_errors_path = agent_dir / "suspected-errors.json"
        write_json(suspected_errors_path, [issue.to_dict() for issue in issues])

        debug_context_path = self._write_debug_context(
            project_dir=project_dir,
            command=command,
            exit_code=exit_code,
            log_path=log_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            issues=issues,
        )
        fix_request_path = self._write_fix_request(
            project_dir=project_dir,
            command=command,
            exit_code=exit_code,
            log_path=log_path,
            issues=issues,
        )

        return RepairArtifacts(
            debug_context_path=debug_context_path,
            fix_request_path=fix_request_path,
            suspected_errors_path=suspected_errors_path,
            issues=issues,
        )

    def _write_debug_context(
        self,
        *,
        project_dir: Path,
        command: list[str],
        exit_code: int | None,
        log_path: Path,
        stdout_path: Path | None,
        stderr_path: Path | None,
        issues: list[BuildIssue],
    ) -> Path:
        agent_dir = ensure_directory(self.config.agent_dir_for(project_dir))
        debug_path = agent_dir / "debug-context.md"
        modspec = self._load_modspec(project_dir)
        java_files = self._collect_files(project_dir / "src" / "main" / "java", project_dir)
        resource_files = self._collect_files(project_dir / "src" / "main" / "resources", project_dir)
        stderr_tail = self._tail_text(stderr_path)
        stdout_tail = self._tail_text(stdout_path)

        lines = [
            "# Debug Context",
            "",
            f"- mod_id: {modspec.get('mod_id', '(unknown)')}",
            f"- mod_name: {modspec.get('display_name', '(unknown)')}",
            f"- package: {modspec.get('package_name', '(unknown)')}",
            f"- build command: `{' '.join(command)}`",
            f"- exit code: {exit_code}",
            f"- gradle log path: `{log_path}`",
            "",
            "## Suspected Errors",
            "",
            *([f"- `{issue.kind.value}`: {issue.message}" for issue in issues] or ["- (none detected)"]),
            "",
            "## Generated Java Files",
            "",
            *([f"- `{path}`" for path in java_files] or ["- (none)"]),
            "",
            "## Generated Resource Files",
            "",
            *([f"- `{path}`" for path in resource_files] or ["- (none)"]),
            "",
            "## Recent stderr",
            "",
            "```text",
            stderr_tail or "(stderr log is empty)",
            "```",
            "",
            "## Recent stdout",
            "",
            "```text",
            stdout_tail or "(stdout log is empty)",
            "```",
            "",
            "## ModSpec JSON",
            "",
            "```json",
            json.dumps(modspec, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
        debug_path.write_text("\n".join(lines), encoding="utf-8")
        return debug_path

    def _write_fix_request(
        self,
        *,
        project_dir: Path,
        command: list[str],
        exit_code: int | None,
        log_path: Path,
        issues: list[BuildIssue],
    ) -> Path:
        agent_dir = ensure_directory(self.config.agent_dir_for(project_dir))
        fix_request_path = agent_dir / "fix-request.md"
        modspec = self._load_modspec(project_dir)
        relevant_files = self._relevant_files(project_dir, issues)
        issue_lines = [f"- `{issue.kind.value}`: {issue.message}" for issue in issues] or ["- No classified issues yet. See full log."]

        lines = [
            "# Fix Request",
            "",
            "This generated NeoForge 26.1 mod failed to build.",
            "",
            "## Project",
            "",
            f"- mod_id: {modspec.get('mod_id', '(unknown)')}",
            f"- mod_name: {modspec.get('display_name', '(unknown)')}",
            f"- package: {modspec.get('package_name', '(unknown)')}",
            "- NeoForge: 26.1",
            "- Java: 25",
            "",
            "## Constraints",
            "",
            "- Do not switch Minecraft or NeoForge versions.",
            "- Do not change the mod loader.",
            "- Do not remove requested features.",
            "- Preserve existing successful behavior.",
            "- Fix with the minimal patch necessary.",
            "",
            "## Build Command",
            "",
            f"`{' '.join(command)}`",
            "",
            "## Exit Code",
            "",
            str(exit_code),
            "",
            "## Error Summary",
            "",
            *issue_lines,
            "",
            "## Suspected Errors JSON",
            "",
            "```json",
            json.dumps([issue.to_dict() for issue in issues], indent=2, ensure_ascii=False),
            "```",
            "",
            "## Relevant Files",
            "",
        ]

        for path in relevant_files:
            lines.extend(self._render_file_excerpt(project_dir, path))

        lines.extend(
            [
                "",
                "## ModSpec",
                "",
                "```json",
                json.dumps(modspec, indent=2, ensure_ascii=False),
                "```",
                "",
                "## Task",
                "",
                "Please propose a minimal patch that fixes the build while preserving the requested features.",
                "",
                f"Full build log: `{log_path}`",
                "",
            ]
        )
        fix_request_path.write_text("\n".join(lines), encoding="utf-8")
        return fix_request_path

    def _load_modspec(self, project_dir: Path) -> dict:
        modspec_path = self.config.agent_dir_for(project_dir) / "modspec.json"
        if not modspec_path.exists():
            return {}
        try:
            return json.loads(modspec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"error": f"Failed to parse {modspec_path.name}"}

    def _collect_files(self, root: Path, project_dir: Path) -> list[str]:
        if not root.exists():
            return []
        return sorted(str(path.relative_to(project_dir)) for path in root.rglob("*") if path.is_file())

    def _tail_text(self, path: Path | None, lines: int = 80) -> str:
        if path is None or not path.exists():
            return ""
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])

    def _relevant_files(self, project_dir: Path, issues: list[BuildIssue]) -> list[Path]:
        candidates: list[Path] = [
            project_dir / "build.gradle",
            project_dir / "gradle.properties",
            project_dir / "src" / "main" / "templates" / "META-INF" / "neoforge.mods.toml",
        ]
        java_root = project_dir / "src" / "main" / "java"
        if java_root.exists():
            candidates.extend(sorted(java_root.rglob("*.java")))

        for issue in issues:
            if issue.file:
                path = project_dir / issue.file
                if path.exists():
                    candidates.append(path)

        resources_root = project_dir / "src" / "main" / "resources"
        if resources_root.exists():
            resource_candidates = sorted(resources_root.rglob("*.json"))
            candidates.extend(resource_candidates[:10])

        unique: list[Path] = []
        seen: set[Path] = set()
        for path in candidates:
            if path.exists() and path not in seen:
                unique.append(path)
                seen.add(path)
        return unique

    def _render_file_excerpt(self, project_dir: Path, path: Path, max_lines: int = 200) -> list[str]:
        relative = path.relative_to(project_dir)
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        excerpt = "\n".join(content[:max_lines])
        language = _language_from_suffix(path.suffix)
        return [
            f"### `{relative}`",
            "",
            f"```{language}",
            excerpt,
            "```",
            "",
        ]


def _classify_message(message: str) -> tuple[BuildErrorKind, str]:
    lowered = message.lower()
    if "cannot find symbol" in lowered or "找不到符号" in message:
        return BuildErrorKind.MISSING_SYMBOL, "Check imports, class names, and whether the target API exists in NeoForge 26.1."
    if ("package " in lowered and " does not exist" in lowered) or ("程序包" in message and "不存在" in message):
        return BuildErrorKind.BAD_IMPORT, "Fix the import path or remove the dependency on the missing package."
    if ("constructor " in lowered and " cannot be applied" in lowered) or ("构造器" in message and "无法应用" in message):
        return BuildErrorKind.CONSTRUCTOR_MISMATCH, "Match the constructor signature to the current API."
    if "incompatible types" in lowered or "不兼容的类型" in message:
        return BuildErrorKind.INCOMPATIBLE_TYPES, "Adjust the generated types or overload selection."
    if "could not resolve" in lowered:
        return BuildErrorKind.DEPENDENCY_RESOLUTION, "Check repository access and dependency coordinates."
    if "json" in lowered and ("parse" in lowered or "malformed" in lowered):
        return BuildErrorKind.RESOURCE_JSON, "Fix the generated JSON format for the current version."
    if "duplicate class" in lowered:
        return BuildErrorKind.DUPLICATE_CLASS, "Remove duplicate generated classes or rename the symbol."
    if "encoding" in lowered or "unmappable character" in lowered:
        return BuildErrorKind.ENCODING, "Ensure files are written in UTF-8 without mixed encodings."
    if "compilejava" in lowered:
        return BuildErrorKind.JAVA_COMPILE, "Inspect the compiler diagnostics and patch the generated Java source."
    if "build file" in lowered or "settings file" in lowered or "gradle" in lowered:
        return BuildErrorKind.GRADLE_CONFIG, "Fix the Gradle build script or plugin configuration."
    return BuildErrorKind.UNKNOWN, "Inspect the full log and nearby files to determine the minimal patch."


def _deduplicate_issues(issues: list[BuildIssue]) -> list[BuildIssue]:
    seen: set[tuple[str, str, str | None, int | None]] = set()
    deduped: list[BuildIssue] = []
    for issue in issues:
        key = (issue.kind.value, issue.message, issue.file, issue.line)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def _to_project_relative(path: str) -> str:
    normalized = path.replace("/", "\\")
    marker = "\\src\\"
    index = normalized.lower().find(marker)
    if index >= 0:
        return normalized[index + 1 :]
    return normalized


def _normalize_log_line(line: str) -> str:
    return re.sub(r"^\[(stdout|stderr)\]\s*", "", line)


def _find_following_symbol(lines: list[str], start_index: int) -> str | None:
    for candidate in lines[start_index + 1 : start_index + 5]:
        stripped = candidate.strip()
        english_match = re.search(r"symbol:\s+(?:class|variable)\s+([A-Za-z0-9_$.]+)", stripped, flags=re.IGNORECASE)
        if english_match:
            return english_match.group(1)
        chinese_match = re.search(r"(?:符号|绗﹀彿)\s*:\s*(?:类|鍙橀噺)\s*([A-Za-z0-9_$.]+)", stripped)
        if chinese_match:
            return chinese_match.group(1)
    return None


def _language_from_suffix(suffix: str) -> str:
    return {
        ".java": "java",
        ".json": "json",
        ".gradle": "groovy",
        ".toml": "toml",
        ".md": "markdown",
    }.get(suffix.lower(), "")
