from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class EvidenceRun:
    evidence_id: str
    source_dir: str
    files: tuple[str, ...]
    provider: str
    validation: tuple[str, ...]
    boundary: str


RUNS = (
    EvidenceRun(
        evidence_id="mock-development-e2e-20260627",
        source_dir="workspace/eval-runs/public-polish-decomposed-e2e-20260627/.agent",
        files=("eval-report.json", "eval-report.md"),
        provider="mock",
        validation=("planner", "generator", "audit"),
        boundary="Offline reproducible evidence; no Gradle build or Minecraft runtime validation.",
    ),
    EvidenceRun(
        evidence_id="mock-build-showcase",
        source_dir="workspace/showcase-runs/public-build-smoke-clean/.agent",
        files=("showcase-report.json", "showcase-report.md"),
        provider="mock",
        validation=("doctor", "planner", "generator", "audit", "gradle-build"),
        boundary="Generated workspaces passed the recorded build gate; no Minecraft runtime validation.",
    ),
    EvidenceRun(
        evidence_id="real-provider-13case-historical",
        source_dir="workspace/real-llm-stability-runs/real-llm-13case-runtime-upgrade/.agent",
        files=("real-llm-stability.json", "real-llm-stability.md"),
        provider="real-provider",
        validation=("provider", "schema", "generator", "audit"),
        boundary=(
            "Historical non-decomposed run. It must not be used as evidence for the later "
            "decomposed-planner token or latency claims. No Minecraft runtime validation."
        ),
    ),
    EvidenceRun(
        evidence_id="real-provider-decomposed-5case-20260718",
        source_dir=(
            "workspace/real-llm-stability-runs/"
            "resume-ab-20260718-decomposed-5case/.agent"
        ),
        files=("real-llm-stability.json", "real-llm-stability.md"),
        provider="real-provider",
        validation=("provider", "schema", "generator", "audit"),
        boundary=(
            "Current decomposed batch result: 4/5 strict success. The failed basic_ruby "
            "case is preserved and must not be replaced by the separate retry. No Gradle "
            "build or Minecraft runtime validation."
        ),
    ),
    EvidenceRun(
        evidence_id="real-provider-fullschema-5case-20260718",
        source_dir=(
            "workspace/real-llm-stability-runs/"
            "resume-ab-20260718-fullschema-5case/.agent"
        ),
        files=("real-llm-stability.json", "real-llm-stability.md"),
        provider="real-provider",
        validation=("provider", "schema", "generator", "audit"),
        boundary=(
            "Current full-schema batch result: 5/5 strict success. This is audit-level "
            "evidence with no Gradle build or Minecraft runtime validation."
        ),
    ),
    EvidenceRun(
        evidence_id="real-provider-decomposed-basic-retry-20260718",
        source_dir=(
            "workspace/real-llm-stability-runs/"
            "resume-ab-20260718-decomposed-basic-retry/.agent"
        ),
        files=("real-llm-stability.json", "real-llm-stability.md"),
        provider="real-provider",
        validation=("provider", "schema", "generator", "audit"),
        boundary=(
            "A separate retry of the failed decomposed basic_ruby case passed. It records "
            "sampling variability and does not change the original batch result from 4/5. "
            "No Gradle build or Minecraft runtime validation."
        ),
    ),
    EvidenceRun(
        evidence_id="real-provider-decomposed-5case-fix1-20260718",
        source_dir=(
            "workspace/real-llm-stability-runs/"
            "resume-ab-20260718-decomposed-5case-fix1/.agent"
        ),
        files=("real-llm-stability.json", "real-llm-stability.md"),
        provider="real-provider",
        validation=("provider", "schema", "generator", "audit"),
        boundary=(
            "Post-fix decomposed batch result: 5/5 strict success and audit 5/5. The fix "
            "filters recipes with missing internal dependencies, canonicalizes vanilla "
            "recipe references, and prevents recipe ID collisions. No Gradle build or "
            "Minecraft runtime validation."
        ),
    ),
)

TEXT_EXTENSIONS = {".json", ".md", ".txt", ".html", ".log"}
SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret)(\s*[=:]\s*)[^\s\"']+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)
ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:\\(?:[^\r\n\"']+)", re.IGNORECASE),
    re.compile(r"/(?:home|Users|mnt)/[^\r\n\"']+", re.IGNORECASE),
)


def sanitize_text(text: str, repo_root: Path) -> str:
    variants = {str(repo_root), str(repo_root).replace("\\", "/")}
    for value in sorted(variants, key=len, reverse=True):
        text = text.replace(value, "<repo>")
    text = re.sub(
        r"(?i)\bAuthorization\s*[:=]\s*(?:Bearer\s+)?[^\s\"']+",
        "Authorization: <redacted>",
        text,
    )
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{8,}", "Bearer <redacted>", text)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>" if match.lastindex else "<redacted>", text)
    for pattern in ABSOLUTE_PATH_PATTERNS:
        text = pattern.sub("<absolute-path-redacted>", text)
    return text


def sanitize_json(value: object, repo_root: Path) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            normalized = key.lower().replace("-", "_")
            if normalized in {"api_key", "authorization", "access_token", "secret"}:
                sanitized[key] = "<redacted>"
            elif normalized == "base_url":
                sanitized[key] = "<provider-endpoint-redacted>"
            else:
                sanitized[key] = sanitize_json(item, repo_root)
        return sanitized
    if isinstance(value, list):
        return [sanitize_json(item, repo_root) for item in value]
    if isinstance(value, str):
        if ".env.local" in value:
            return "<local-config-source-redacted>"
        return sanitize_text(value, repo_root)
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_public_safety_violations(root: Path) -> list[str]:
    violations: list[str] = []
    checks = (
        (re.compile(r"(?i)\bBearer\s+(?!<redacted>)[A-Za-z0-9._~+/-]{8,}"), "bearer token"),
        (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "API key"),
        (re.compile(r"(?i)\.env\.local"), "local config source"),
        (re.compile(r"[A-Za-z]:\\(?:Users|projects)\\"), "Windows absolute path"),
        (re.compile(r"/(?:home|Users)/[^\s\"']+"), "Unix absolute path"),
    )
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, label in checks:
            if pattern.search(text):
                violations.append(f"{path.relative_to(root).as_posix()}: {label}")
    return violations


def verify_portfolio(output_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest.json is invalid: {exc}"]
    for entry in manifest.get("entries", []):
        evidence_id = entry.get("evidence_id", "<unknown>")
        if entry.get("status") != "complete":
            errors.append(f"{evidence_id}: status is not complete")
        for item in entry.get("files", []):
            relative = item.get("path", "")
            path = output_dir / relative
            if not path.is_file():
                errors.append(f"{evidence_id}: missing file {relative}")
                continue
            if path.stat().st_size != item.get("bytes"):
                errors.append(f"{evidence_id}: byte size mismatch for {relative}")
            if sha256(path) != item.get("sha256"):
                errors.append(f"{evidence_id}: SHA-256 mismatch for {relative}")
    errors.extend(find_public_safety_violations(output_dir))
    return errors


def build_portfolio(repo_root: Path, output_dir: Path, overwrite: bool = False) -> dict[str, object]:
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Output already exists: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    entries: list[dict[str, object]] = []
    for run in RUNS:
        source_dir = repo_root / run.source_dir
        target_dir = output_dir / run.evidence_id
        copied_files: list[dict[str, object]] = []
        missing_files: list[str] = []
        for filename in run.files:
            source = source_dir / filename
            if not source.is_file():
                missing_files.append(filename)
                continue
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / filename
            if source.suffix.lower() == ".json":
                payload = json.loads(source.read_text(encoding="utf-8"))
                target.write_text(
                    json.dumps(sanitize_json(payload, repo_root), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            elif source.suffix.lower() in TEXT_EXTENSIONS:
                content = sanitize_text(source.read_text(encoding="utf-8"), repo_root)
                target.write_text(content, encoding="utf-8", newline="\n")
            else:
                shutil.copy2(source, target)
            copied_files.append(
                {
                    "path": target.relative_to(output_dir).as_posix(),
                    "bytes": target.stat().st_size,
                    "sha256": sha256(target),
                }
            )
        entries.append(
            {
                "evidence_id": run.evidence_id,
                "source_run": run.source_dir,
                "provider": run.provider,
                "validation": list(run.validation),
                "boundary": run.boundary,
                "status": "complete" if copied_files and not missing_files else "incomplete",
                "files": copied_files,
                "missing_files": missing_files,
            }
        )

    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": (
            "This directory contains sanitized snapshots of existing local run reports. "
            "It does not upgrade audit/build evidence to Minecraft runtime evidence."
        ),
        "entries": entries,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Portfolio Evidence Manifest",
        "",
        "该目录只保存经过脱敏的冻结报告，用于让 README 中的公开结论可以复验。",
        "audit/build 证据不等于 Minecraft 客户端或服务端 runtime 验收。",
        "",
    ]
    for entry in entries:
        lines.extend(
            [
                f"## {entry['evidence_id']}",
                "",
                f"- Status: `{entry['status']}`",
                f"- Provider: `{entry['provider']}`",
                f"- Source run: `{entry['source_run']}`",
                f"- Validation: `{', '.join(entry['validation'])}`",
                f"- Boundary: {entry['boundary']}",
                "",
            ]
        )
        for item in entry["files"]:
            lines.append(f"- `{item['path']}` — SHA-256 `{item['sha256']}`")
        if entry["missing_files"]:
            lines.append(f"- Missing: `{', '.join(entry['missing_files'])}`")
        lines.append("")
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    violations = find_public_safety_violations(output_dir)
    if violations:
        raise ValueError("Public-safety scan failed:\n" + "\n".join(violations))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a sanitized portfolio evidence snapshot.")
    parser.add_argument("--output", default="evidence/portfolio")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true", help="Verify an existing snapshot without changing it.")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output = (repo_root / args.output).resolve()
    if repo_root not in output.parents:
        raise SystemExit("Output must stay inside the repository.")
    if args.check:
        errors = verify_portfolio(output)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"Portfolio evidence verified: {output}")
        return 0
    manifest = build_portfolio(repo_root, output, overwrite=args.overwrite)
    incomplete = [entry["evidence_id"] for entry in manifest["entries"] if entry["status"] != "complete"]
    print(f"Portfolio evidence: {output}")
    if incomplete:
        print(f"Incomplete entries: {', '.join(incomplete)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
