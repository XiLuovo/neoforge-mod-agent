from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = "manual-runtime-evidence/v1"
KIND = "manual_minecraft_runtime"
STATUSES = {"passed", "failed", "blocked", "runtime_unverified"}
CHECK_STATUSES = {"passed", "failed", "not_checked", "blocked"}

CASES = (
    {
        "id": "runtime_basic_ruby",
        "title": "Basic Ruby startup smoke",
        "workspace": "workspace/runtime-real-basic-ruby",
        "jar": "build/libs/ruby_mod-0.1.0.jar",
        "checks": (
            ("client_launch", "NeoForge client reaches the main menu without a mod initialization crash."),
            ("mod_loaded", "Ruby Mod appears in the loaded mods list."),
            ("item_registered", "Command /give @s ruby_mod:ruby succeeds."),
            ("item_visual", "Ruby has the expected name and a visible, non-missing texture."),
        ),
    },
    {
        "id": "runtime_speed_crystal_behavior",
        "title": "Speed Crystal behavior",
        "workspace": (
            "workspace/real-llm-stability-runs/real-llm-build-3case-20260604-223533/"
            "runs/03-speed_crystal_behavior-strict"
        ),
        "jar": "build/libs/example_mod-1.0.0.jar",
        "checks": (
            ("client_launch", "NeoForge client reaches a world without a mod initialization crash."),
            ("item_registered", "Command /give @s example_mod:speed_crystal succeeds."),
            ("effect_applied", "Using the crystal applies Speed II for approximately 10 seconds."),
            ("item_not_consumed", "The crystal remains in the inventory after use."),
        ),
    },
    {
        "id": "runtime_modify_worldgen",
        "title": "Modify lane resources, recipes, and worldgen",
        "workspace": (
            "workspace/showcase-runs/public-build-smoke-clean/workspaces/eval-runs/"
            "public-build-smoke-clean-development-e2e/02-modify_add_worldgen_repeat-base"
        ),
        "jar": "build/libs/ruby_mod-0.1.0.jar",
        "checks": (
            ("client_launch", "NeoForge client reaches a newly created world without a mod initialization crash."),
            ("content_registered", "Ruby item, block, ore, apple, and sword are available."),
            ("block_interaction", "Ruby block and ore can be placed and mined with expected drops."),
            ("recipes", "Ruby block compression and decompression recipes work."),
            ("placed_feature", "Command /place feature ruby_mod:ruby_ore succeeds."),
            ("natural_worldgen", "A natural ruby ore vein is observed in a newly generated chunk between Y -64 and 32."),
        ),
    },
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_draft(repo_root: Path) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for definition in CASES:
        workspace = repo_root / definition["workspace"]
        jar = workspace / definition["jar"]
        modspec = workspace / ".agent" / "modspec.json"
        audit = workspace / ".agent" / "audit-report.json"
        build = workspace / ".agent" / "logs" / "gradle-build.json"
        missing = [
            relative
            for relative, path in (
                (definition["jar"], jar),
                (".agent/modspec.json", modspec),
                (".agent/audit-report.json", audit),
                (".agent/logs/gradle-build.json", build),
            )
            if not path.is_file()
        ]
        cases.append(
            {
                "schema_version": SCHEMA,
                "evidence_kind": KIND,
                "id": definition["id"],
                "title": definition["title"],
                "workspace": definition["workspace"],
                "status": "runtime_unverified",
                "passed": False,
                "source": "evidence/runtime/runtime-evidence.json",
                "notes": "Minecraft runtime has not been checked yet.",
                "tested_at": None,
                "environment": {
                    "side": "client",
                    "minecraft": "26.1.2",
                    "neoforge": "26.1.2.30-beta",
                    "java": "25",
                },
                "artifact": {
                    "jar": definition["jar"],
                    "sha256": sha256(jar) if jar.is_file() else None,
                },
                "provenance": {
                    "modspec": ".agent/modspec.json",
                    "modspec_sha256": sha256(modspec) if modspec.is_file() else None,
                    "audit": ".agent/audit-report.json",
                    "build": ".agent/logs/gradle-build.json",
                    "missing": missing,
                },
                "checks": [
                    {"id": check_id, "status": "not_checked", "expected": expected, "observed": ""}
                    for check_id, expected in definition["checks"]
                ],
                "attachments": [],
            }
        )
    return {
        "schema_version": SCHEMA,
        "evidence_kind": KIND,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_evidence_cases": cases,
    }


def validate(payload: dict[str, object], repo_root: Path, *, require_complete: bool = False) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA:
        errors.append("top-level schema_version is invalid")
    if payload.get("evidence_kind") != KIND:
        errors.append("top-level evidence_kind is invalid")
    cases = payload.get("runtime_evidence_cases")
    if not isinstance(cases, list):
        return errors + ["runtime_evidence_cases must be a list"]
    identifiers: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"case[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        identifier = str(case.get("id", "")).strip()
        if not identifier or identifier in identifiers:
            errors.append(f"{prefix} id is empty or duplicated")
        identifiers.add(identifier)
        if case.get("schema_version") != SCHEMA or case.get("evidence_kind") != KIND:
            errors.append(f"{identifier}: schema or evidence kind is invalid")
        status = case.get("status")
        passed = case.get("passed")
        if status not in STATUSES:
            errors.append(f"{identifier}: unsupported status {status!r}")
        if passed is not (status == "passed"):
            errors.append(f"{identifier}: passed flag conflicts with status")
        workspace_value = str(case.get("workspace", ""))
        if not workspace_value or Path(workspace_value).is_absolute() or ".." in Path(workspace_value).parts:
            errors.append(f"{identifier}: workspace must be a safe repository-relative path")
            continue
        workspace = repo_root / workspace_value
        artifact = case.get("artifact", {})
        if not isinstance(artifact, dict):
            errors.append(f"{identifier}: artifact must be an object")
            continue
        jar_value = str(artifact.get("jar", ""))
        jar_path = workspace / jar_value
        if not jar_path.is_file():
            errors.append(f"{identifier}: jar is missing: {jar_value}")
        elif artifact.get("sha256") != sha256(jar_path):
            errors.append(f"{identifier}: jar SHA-256 mismatch")
        checks = case.get("checks")
        if not isinstance(checks, list) or not checks:
            errors.append(f"{identifier}: checks must be a non-empty list")
            checks = []
        for check in checks:
            if not isinstance(check, dict) or check.get("status") not in CHECK_STATUSES:
                errors.append(f"{identifier}: invalid check status")
        if status == "passed" and any(check.get("status") != "passed" for check in checks if isinstance(check, dict)):
            errors.append(f"{identifier}: passed case requires every check to pass")
        if status in {"passed", "failed"}:
            if not case.get("tested_at"):
                errors.append(f"{identifier}: checked case requires tested_at")
            attachments = case.get("attachments")
            if not isinstance(attachments, list) or not attachments:
                errors.append(f"{identifier}: checked case requires at least one attachment")
            else:
                for attachment in attachments:
                    if not isinstance(attachment, dict):
                        errors.append(f"{identifier}: attachment must be an object")
                        continue
                    relative = str(attachment.get("path", ""))
                    path = repo_root / relative
                    if Path(relative).is_absolute() or ".." in Path(relative).parts or not path.is_file():
                        errors.append(f"{identifier}: attachment is missing or unsafe: {relative}")
                    elif attachment.get("sha256") != sha256(path):
                        errors.append(f"{identifier}: attachment SHA-256 mismatch: {relative}")
        if status == "blocked" and not str(case.get("notes", "")).strip():
            errors.append(f"{identifier}: blocked case requires notes")
        if require_complete and status == "runtime_unverified":
            errors.append(f"{identifier}: runtime remains unverified")
    serialized = json.dumps(payload, ensure_ascii=False)
    if re.search(r"[A-Za-z]:\\(?:Users|projects)\\|(?i:api[_-]?key|Bearer\s+[A-Za-z0-9])", serialized):
        errors.append("evidence contains a private absolute path or possible credential")
    return errors


def summary(payload: dict[str, object]) -> dict[str, object]:
    cases = payload.get("runtime_evidence_cases", [])
    counts = {status: 0 for status in STATUSES}
    for case in cases if isinstance(cases, list) else []:
        if isinstance(case, dict) and case.get("status") in counts:
            counts[case["status"]] += 1
    checked = counts["passed"] + counts["failed"]
    total = sum(counts.values())
    return {
        "planned": total,
        "checked": checked,
        "passed": counts["passed"],
        "failed": counts["failed"],
        "blocked": counts["blocked"],
        "runtime_unverified": counts["runtime_unverified"],
        "verification_coverage": checked / total if total else None,
        "checked_pass_rate": counts["passed"] / checked if checked else None,
        "boundary": "Only explicitly checked cases count as Minecraft runtime evidence.",
    }


def write_summary(payload: dict[str, object], output: Path) -> None:
    metrics = summary(payload)
    output.with_suffix(".json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Minecraft Runtime Evidence Summary",
        "",
        f"- Planned: `{metrics['planned']}`",
        f"- Checked: `{metrics['checked']}`",
        f"- Passed: `{metrics['passed']}`",
        f"- Failed: `{metrics['failed']}`",
        f"- Blocked: `{metrics['blocked']}`",
        f"- Runtime unverified: `{metrics['runtime_unverified']}`",
        f"- Verification coverage: `{metrics['verification_coverage']}`",
        f"- Checked pass rate: `{metrics['checked_pass_rate']}`",
        "",
        metrics["boundary"],
    ]
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and validate portfolio Minecraft runtime evidence.")
    parser.add_argument("action", choices=("prepare", "check", "summary"))
    parser.add_argument("--file", default="evidence/runtime/runtime-evidence.json")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    evidence_path = repo_root / args.file
    if args.action == "prepare":
        if evidence_path.exists() and not args.overwrite:
            raise SystemExit(f"Evidence file exists: {evidence_path}; use --overwrite to rebuild the draft.")
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        payload = build_draft(repo_root)
        evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_summary(payload, evidence_path.with_name("runtime-summary"))
    else:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        errors = validate(payload, repo_root, require_complete=args.require_complete)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        if args.action == "summary":
            write_summary(payload, evidence_path.with_name("runtime-summary"))
    print(f"Runtime evidence {args.action} succeeded: {evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
