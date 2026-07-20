from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SemanticCoverageResult:
    expected_features: list[str]
    matched_expected_features: list[str]
    missing_expected_features: list[str]
    expected_categories: list[str]
    matched_expected_categories: list[str]
    missing_expected_categories: list[str]
    semantic_success: bool
    ignored_feature_warnings: list[str]
    removed_behavior_warnings: list[str]
    semantic_warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_features": list(self.expected_features),
            "matched_expected_features": list(self.matched_expected_features),
            "missing_expected_features": list(self.missing_expected_features),
            "expected_categories": list(self.expected_categories),
            "matched_expected_categories": list(self.matched_expected_categories),
            "missing_expected_categories": list(self.missing_expected_categories),
            "semantic_success": self.semantic_success,
            "ignored_feature_warnings": list(self.ignored_feature_warnings),
            "removed_behavior_warnings": list(self.removed_behavior_warnings),
            "semantic_warnings": list(self.semantic_warnings),
        }


def evaluate_semantic_coverage(
    *,
    expected_features: list[str],
    expected_categories: list[str],
    modspec: dict[str, Any] | None,
    mode: str = "generate",
    process_success: bool = True,
    warnings: list[str] | tuple[str, ...] = (),
) -> SemanticCoverageResult:
    payload = modspec if isinstance(modspec, dict) else {}
    actual_features = feature_ids_from_modspec(payload)
    actual_categories = categories_from_modspec(payload, mode=mode)
    normalized_categories = [normalize_category(category) for category in expected_categories]
    matched_features = [feature for feature in expected_features if feature in actual_features]
    missing_features = [feature for feature in expected_features if feature not in actual_features]
    matched_categories = [category for category in normalized_categories if category in actual_categories]
    missing_categories = [category for category in normalized_categories if category not in actual_categories]
    unique_warnings = _unique_strings(warnings)
    ignored_feature_warnings = [
        warning for warning in unique_warnings if "ignored unsupported feature type:" in warning.lower()
    ]
    removed_behavior_warnings = [
        warning for warning in unique_warnings if "removed behavior" in warning.lower()
    ]
    semantic_warning_markers = (
        "ignored unsupported feature type:",
        "removed behavior",
        "references unknown target",
        "has multiple stages but no links",
        "cannot reach end stage",
        "no quest chain is declared",
    )
    semantic_warnings = [
        warning
        for warning in unique_warnings
        if any(marker in warning.lower() for marker in semantic_warning_markers)
    ]
    return SemanticCoverageResult(
        expected_features=list(expected_features),
        matched_expected_features=matched_features,
        missing_expected_features=missing_features,
        expected_categories=normalized_categories,
        matched_expected_categories=matched_categories,
        missing_expected_categories=missing_categories,
        semantic_success=process_success and not missing_features and not missing_categories,
        ignored_feature_warnings=ignored_feature_warnings,
        removed_behavior_warnings=removed_behavior_warnings,
        semantic_warnings=semantic_warnings,
    )


def feature_ids_from_modspec(data: dict[str, Any]) -> set[str]:
    feature_ids: set[str] = set()
    for feature in _feature_dicts_from_modspec(data):
        identifier = feature.get("id", feature.get("identifier"))
        if identifier:
            feature_ids.add(str(identifier))
    return feature_ids


def evaluate_stability_report_semantics(
    stability_report: dict[str, Any],
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    expectations = {
        str(case.get("id", case.get("identifier", ""))): case
        for case in cases
        if isinstance(case, dict)
    }
    results: list[dict[str, Any]] = []
    for raw_case in stability_report.get("cases", []):
        if not isinstance(raw_case, dict):
            continue
        identifier = str(raw_case.get("id", raw_case.get("identifier", "")))
        expected = expectations.get(identifier, {})
        coverage = evaluate_semantic_coverage(
            expected_features=[str(item) for item in expected.get("expected_features", [])],
            expected_categories=[str(item) for item in expected.get("expected_categories", [])],
            modspec=_load_workspace_modspec(raw_case.get("workspace")),
            mode=str(expected.get("mode", "generate")),
            process_success=bool(raw_case.get("strict_success")),
            warnings=[str(item) for item in raw_case.get("warnings", [])],
        )
        results.append(
            {
                "id": identifier,
                "strict_success": bool(raw_case.get("strict_success")),
                "workspace": raw_case.get("workspace"),
                **coverage.to_dict(),
            }
        )

    total = len(results)
    semantic_success_count = sum(1 for result in results if result["semantic_success"])
    expected_features_total = sum(len(result["expected_features"]) for result in results)
    expected_features_matched = sum(len(result["matched_expected_features"]) for result in results)
    expected_categories_total = sum(len(result["expected_categories"]) for result in results)
    expected_categories_matched = sum(len(result["matched_expected_categories"]) for result in results)
    return {
        "schema_version": "semantic-coverage/v1",
        "source_run_id": stability_report.get("run_id"),
        "cases": results,
        "metrics": {
            "total_cases": total,
            "semantic_success_count": semantic_success_count,
            "semantic_success_rate": _rate(semantic_success_count, total),
            "expected_features_total": expected_features_total,
            "expected_features_matched": expected_features_matched,
            "expected_feature_match_rate": _rate(expected_features_matched, expected_features_total),
            "expected_categories_total": expected_categories_total,
            "expected_categories_matched": expected_categories_matched,
            "expected_category_match_rate": _rate(expected_categories_matched, expected_categories_total),
            "ignored_feature_warning_count": sum(len(result["ignored_feature_warnings"]) for result in results),
            "removed_behavior_warning_count": sum(len(result["removed_behavior_warnings"]) for result in results),
            "semantic_warning_count": sum(len(result["semantic_warnings"]) for result in results),
        },
        "boundary": (
            "Semantic coverage compares expected features/categories with the generated ModSpec. "
            "It does not prove Gradle build or Minecraft runtime behavior."
        ),
    }


def write_stability_semantic_report(
    stability_report_path: Path,
    cases_path: Path,
    *,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    stability_report = json.loads(stability_report_path.read_text(encoding="utf-8"))
    cases_payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = cases_payload.get("cases", []) if isinstance(cases_payload, dict) else cases_payload
    if not isinstance(stability_report, dict):
        raise ValueError("Stability report must be a JSON object.")
    if not isinstance(cases, list):
        raise ValueError("Cases file must contain a list or an object with a 'cases' list.")

    semantic_report = evaluate_stability_report_semantics(
        stability_report,
        [case for case in cases if isinstance(case, dict)],
    )
    target_dir = output_dir or stability_report_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    json_path = target_dir / "semantic-coverage.json"
    markdown_path = target_dir / "semantic-coverage.md"
    json_path.write_text(
        json.dumps(semantic_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(
        _render_semantic_coverage_markdown(semantic_report),
        encoding="utf-8",
        newline="\n",
    )
    return json_path, markdown_path


def categories_from_modspec(data: dict[str, Any], *, mode: str) -> set[str]:
    categories: set[str] = set()
    if mode == "modify":
        categories.add("modify")

    for feature in _feature_dicts_from_modspec(data):
        feature_type = normalize_category(str(feature.get("type", "")))
        if feature_type in _FEATURE_CATEGORY_TYPES:
            categories.add(feature_type)
        if feature_type == "world_feature":
            categories.add("worldgen")
        if feature_type == "loot_pool":
            categories.add("loot")
        if feature_type == "machine":
            categories.update({"block", "block_entity"})
            if feature.get("menu_title") or feature.get("inventory_slots"):
                categories.add("gui")
            machine_kind = normalize_category(str(feature.get("machine_kind", "")))
            if machine_kind:
                categories.add(machine_kind)
        if feature_type == "progression":
            categories.add("progression_report")
        if feature_type == "balance_plan":
            categories.update({"balance", "balance_report"})
        if feature_type == "quest":
            categories.update({"advancement", "guidebook"})

        behavior = feature.get("behavior")
        if isinstance(behavior, dict):
            behavior_type = normalize_category(str(behavior.get("type", "")))
            categories.add("behavior")
            if behavior_type:
                categories.add(behavior_type)

        effects = feature.get("effects")
        if isinstance(effects, list) and effects:
            categories.update({"behavior", "food_effect"})

        on_hit = feature.get("on_hit")
        if isinstance(on_hit, dict):
            categories.add("behavior")
            raw_on_hit_type = normalize_category(str(on_hit.get("type", "")))
            if raw_on_hit_type == "ignite":
                categories.add("sword_ignite")
            elif raw_on_hit_type:
                categories.add(f"sword_{raw_on_hit_type}")

        worldgen = feature.get("worldgen")
        if isinstance(worldgen, dict) and worldgen.get("enabled"):
            categories.update({"worldgen", "ore_worldgen"})

        block_kind = str(feature.get("block_kind", "cube")).strip().lower()
        if feature_type == "block" and block_kind and block_kind != "cube":
            categories.add("block_variants")
            if block_kind in {"button", "pressure_plate", "fence_gate", "door", "trapdoor"}:
                categories.add("interactive_blocks")

    return categories


def normalize_category(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "food_effects": "food_effect",
        "on_hit_ignite": "sword_ignite",
        "ignite": "sword_ignite",
        "ore_natural_generation": "worldgen",
        "overworld_ore": "worldgen",
        "overworld_worldgen": "worldgen",
        "balance": "balance_plan",
        "balance_planner": "balance_plan",
        "progression_reports": "progression_report",
        "questline": "quest",
        "quests": "quest",
        "advancements": "advancement",
        "guide_book": "guidebook",
    }
    return aliases.get(normalized, normalized)


def _feature_dicts_from_modspec(data: dict[str, Any]) -> list[dict[str, Any]]:
    features = data.get("features")
    if isinstance(features, list) and features:
        return [feature for feature in features if isinstance(feature, dict)]

    result: list[dict[str, Any]] = []
    for key, feature_type in _FEATURE_COLLECTION_TYPES:
        entries = data.get(key, [])
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    feature = dict(entry)
                    feature.setdefault("type", feature_type)
                    result.append(feature)
    return result


_FEATURE_COLLECTION_TYPES = (
    ("items", "item"),
    ("blocks", "block"),
    ("machines", "machine"),
    ("entities", "entity"),
    ("dimensions", "dimension"),
    ("biomes", "biome"),
    ("world_features", "world_feature"),
    ("structures", "structure"),
    ("loot_pools", "loot_pool"),
    ("java_extensions", "java_extension"),
    ("ores", "ore"),
    ("foods", "food"),
    ("swords", "sword"),
    ("tools", "tool"),
    ("armors", "armor"),
    ("recipes", "recipe"),
    ("progressions", "progression"),
    ("balance_plans", "balance_plan"),
    ("quests", "quest"),
)

_FEATURE_CATEGORY_TYPES = {feature_type for _, feature_type in _FEATURE_COLLECTION_TYPES}


def _unique_strings(values: list[str] | tuple[str, ...]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _render_semantic_coverage_markdown(report: dict[str, Any]) -> str:
    metrics = report.get("metrics", {})
    total = int(metrics.get("total_cases", 0) or 0)
    lines = [
        "# Real LLM Semantic Coverage",
        "",
        f"Source run: `{report.get('source_run_id')}`",
        "",
        "## Metrics",
        "",
        f"- semantic success: `{metrics.get('semantic_success_count')}/{total}`",
        f"- expected feature match: `{metrics.get('expected_features_matched')}/{metrics.get('expected_features_total')}`",
        f"- expected category match: `{metrics.get('expected_categories_matched')}/{metrics.get('expected_categories_total')}`",
        f"- ignored feature warning messages: `{metrics.get('ignored_feature_warning_count')}`",
        f"- removed behavior warning messages: `{metrics.get('removed_behavior_warning_count')}`",
        f"- semantic warning messages: `{metrics.get('semantic_warning_count')}`",
        "",
        "## Cases",
        "",
    ]
    for case in report.get("cases", []):
        lines.append(
            f"- `{case.get('id')}`: strict={str(bool(case.get('strict_success'))).lower()} "
            f"semantic={str(bool(case.get('semantic_success'))).lower()}"
        )
        if case.get("missing_expected_features"):
            lines.append(
                "  - missing expected features: "
                + ", ".join(str(item) for item in case["missing_expected_features"])
            )
        if case.get("missing_expected_categories"):
            lines.append(
                "  - missing expected categories: "
                + ", ".join(str(item) for item in case["missing_expected_categories"])
            )
        if case.get("semantic_warnings"):
            lines.append(
                f"  - semantic warnings: {len(case['semantic_warnings'])} unique message(s)"
            )
    lines.extend(["", "## Boundary", "", str(report.get("boundary", "")), ""])
    return "\n".join(lines)


def _load_workspace_modspec(workspace: object) -> dict[str, Any] | None:
    if not workspace:
        return None
    path = Path(str(workspace)) / ".agent" / "modspec.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)
