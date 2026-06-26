from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .config import AppConfig
from .models import ModSpec, ProgressionLinkSpec, ProgressionSpec
from .tools import write_json, write_text


class ProgressionGenerator:
    """Write V7 gameplay-loop evidence reports from structured ModSpec data."""

    version = "7.0"

    def generate(self, project_dir: Path, spec: ModSpec, config: AppConfig) -> list[Path]:
        if not spec.progressions:
            return []
        agent_dir = config.agent_dir_for(project_dir)
        payload = progression_report_payload(spec)
        report_json = agent_dir / "progression-report.json"
        report_md = agent_dir / "progression-report.md"
        write_json(report_json, payload)
        write_text(report_md, render_progression_report_markdown(payload))
        return [report_json, report_md]


def progression_report_payload(spec: ModSpec) -> dict[str, Any]:
    lookup = _target_lookup(spec)
    progressions = [_progression_payload(progression, spec.mod_id, lookup) for progression in spec.progressions]
    stage_type_counts: Counter[str] = Counter()
    target_type_counts: Counter[str] = Counter()
    missing_references_total = 0
    stage_count = 0
    link_count = 0

    for progression in progressions:
        stage_count += len(progression["stages"])
        link_count += len(progression["links"])
        missing_references_total += progression["missing_references_count"]
        stage_type_counts.update(progression["coverage"]["stage_type_counts"])
        target_type_counts.update(progression["coverage"]["target_type_counts"])

    return {
        "version": ProgressionGenerator.version,
        "status": "pass" if missing_references_total == 0 else "warning",
        "mod_id": spec.mod_id,
        "totals": {
            "loop_count": len(progressions),
            "stage_count": stage_count,
            "link_count": link_count,
            "missing_references_total": missing_references_total,
            "stage_type_counts": dict(sorted(stage_type_counts.items())),
            "target_type_counts": dict(sorted(target_type_counts.items())),
        },
        "progressions": progressions,
    }


def _progression_payload(
    progression: ProgressionSpec,
    mod_id: str,
    lookup: dict[str, str],
) -> dict[str, Any]:
    stages = []
    missing_references_count = 0
    stage_type_counts: Counter[str] = Counter()
    target_type_counts: Counter[str] = Counter()

    for stage in progression.stages:
        resolved = []
        missing = []
        for category, references in (
            ("requires", stage.requires),
            ("provides", stage.provides),
            ("unlocks", stage.unlocks),
            ("evidence", stage.evidence),
        ):
            for reference in references:
                entry = _resolve_reference(reference, mod_id, lookup)
                entry["category"] = category
                resolved.append(entry)
                target_type_counts.update([entry["target_type"]])
                if entry["status"] == "missing":
                    missing.append({"category": category, "reference": reference})

        missing_references_count += len(missing)
        stage_type_counts.update([stage.stage_type])
        stages.append(
            {
                "id": stage.identifier,
                "type": stage.stage_type,
                "title": stage.title,
                "description": stage.description,
                "requires": list(stage.requires),
                "provides": list(stage.provides),
                "unlocks": list(stage.unlocks),
                "evidence": list(stage.evidence),
                "resolved_references": resolved,
                "missing_references": missing,
            }
        )

    links = [
        {
            "from_stage": link.from_stage,
            "to_stage": link.to_stage,
            "trigger": link.trigger,
            "requirement": link.requirement,
        }
        for link in progression.links
    ]
    entry_stage = progression.entry_stage or (progression.stages[0].identifier if progression.stages else "")
    end_stage = progression.end_stage or (progression.stages[-1].identifier if progression.stages else "")
    reachable = _reachable_stages(entry_stage, progression.links)
    cycles = _cycle_paths({stage.identifier for stage in progression.stages}, progression.links)

    return {
        "id": progression.identifier,
        "title": progression.title,
        "summary": progression.summary,
        "entry_stage": entry_stage,
        "end_stage": end_stage,
        "stages": stages,
        "links": links,
        "graph": {
            "entry_reaches_end": bool(end_stage and end_stage in reachable),
            "reachable_stage_ids": sorted(reachable),
            "cycle_count": len(cycles),
            "cycles": cycles,
        },
        "coverage": {
            "stage_type_counts": dict(sorted(stage_type_counts.items())),
            "target_type_counts": dict(sorted(target_type_counts.items())),
        },
        "missing_references_count": missing_references_count,
        "behavior": progression.behavior.to_dict() if progression.behavior is not None else None,
    }


def render_progression_report_markdown(payload: dict[str, Any]) -> str:
    totals = payload.get("totals", {})
    lines = [
        "# V7 Progression / Gameplay Loop Report",
        "",
        f"Status: `{payload.get('status', 'unknown')}`",
        f"Mod ID: `{payload.get('mod_id', '')}`",
        f"Loops: `{totals.get('loop_count', 0)}`",
        f"Stages: `{totals.get('stage_count', 0)}`",
        f"Links: `{totals.get('link_count', 0)}`",
        f"Missing references: `{totals.get('missing_references_total', 0)}`",
        "",
    ]

    for progression in payload.get("progressions", []):
        lines.extend(
            [
                f"## {progression.get('title', progression.get('id', 'Progression'))}",
                "",
                f"ID: `{progression.get('id', '')}`",
                f"Entry: `{progression.get('entry_stage', '')}`",
                f"End: `{progression.get('end_stage', '')}`",
                f"Entry reaches end: `{str(progression.get('graph', {}).get('entry_reaches_end', False)).lower()}`",
                "",
            ]
        )
        if progression.get("summary"):
            lines.extend([str(progression["summary"]), ""])

        if progression.get("behavior"):
            lines.extend(["### Behavior", ""])
            for event in progression["behavior"].get("events", []):
                triggers = [
                    str(trigger)
                    for trigger in [event.get("trigger"), *event.get("triggers", [])]
                    if str(trigger or "").strip()
                ]
                mode = event.get("trigger_mode", "any")
                lines.append(f"- `{', '.join(triggers) if triggers else event.get('trigger', '')}` mode=`{mode}`")
                if event.get("conditions"):
                    condition_types = ", ".join(condition.get("type", "") for condition in event["conditions"] if condition.get("type"))
                    lines.append(f"  - conditions: {condition_types}")
                if event.get("actions"):
                    action_types = ", ".join(action.get("type", "") for action in event["actions"] if action.get("type"))
                    lines.append(f"  - actions: {action_types}")
            lines.append("")

        lines.extend(["### Stages", ""])
        for stage in progression.get("stages", []):
            missing = stage.get("missing_references", [])
            missing_text = ", ".join(item["reference"] for item in missing) if missing else "none"
            lines.append(f"- `{stage.get('id')}` [{stage.get('type')}] {stage.get('title')}")
            if stage.get("description"):
                lines.append(f"  - description: {stage.get('description')}")
            for key in ("requires", "provides", "unlocks", "evidence"):
                values = stage.get(key, [])
                if values:
                    lines.append(f"  - {key}: {', '.join(f'`{value}`' for value in values)}")
            lines.append(f"  - missing: {missing_text}")
        lines.append("")

        if progression.get("links"):
            lines.extend(["### Links", ""])
            for link in progression.get("links", []):
                trigger = f" via {link.get('trigger')}" if link.get("trigger") else ""
                requirement = f" requiring {link.get('requirement')}" if link.get("requirement") else ""
                lines.append(f"- `{link.get('from_stage')}` -> `{link.get('to_stage')}`{trigger}{requirement}")
            lines.append("")

    return "\n".join(lines)


def _target_lookup(spec: ModSpec) -> dict[str, str]:
    lookup: dict[str, str] = {}

    def add(identifier: str, target_type: str) -> None:
        if not identifier:
            return
        lookup[identifier] = target_type
        lookup[f"{spec.mod_id}:{identifier}"] = target_type

    for item in spec.items:
        add(item.identifier, "item")
    for food in spec.foods:
        add(food.identifier, "food")
    for sword in spec.swords:
        add(sword.identifier, "sword")
    for tool in spec.tools:
        add(tool.identifier, "tool")
    for armor in spec.armors:
        add(armor.identifier, "armor")
    for block in spec.blocks:
        add(block.identifier, "block")
    for machine in spec.machines:
        add(machine.identifier, "machine")
    for ore in spec.ores:
        add(ore.identifier, "ore")
    for entity in spec.entities:
        add(entity.identifier, "entity")
    for dimension in spec.dimensions:
        add(dimension.identifier, "dimension")
    for biome in spec.biomes:
        add(biome.identifier, "biome")
    for feature in spec.world_features:
        add(feature.identifier, "world_feature")
    for structure in spec.structures:
        add(structure.identifier, "structure")
    for pool in spec.loot_pools:
        add(pool.identifier, "loot_pool")
        lookup[f"chests/{pool.identifier}"] = "loot_pool"
        lookup[f"{spec.mod_id}:chests/{pool.identifier}"] = "loot_pool"
    for extension in spec.java_extensions:
        add(extension.identifier, "java_extension")
    for recipe in spec.recipes:
        add(recipe.identifier, "recipe")
        lookup[f"recipe:{recipe.identifier}"] = "recipe"
    return lookup


def _resolve_reference(reference: str, mod_id: str, lookup: dict[str, str]) -> dict[str, str]:
    value = reference.strip()
    if value in lookup:
        return {"reference": reference, "normalized": value, "target_type": lookup[value], "status": "resolved"}
    if value.startswith("#") and ":" in value[1:]:
        return {"reference": reference, "normalized": value, "target_type": "external_tag", "status": "external"}
    if ":" in value and not value.startswith("recipe:"):
        namespace, path = value.split(":", 1)
        if namespace != mod_id:
            return {"reference": reference, "normalized": value, "target_type": "external_resource", "status": "external"}
        if path in lookup:
            return {"reference": reference, "normalized": path, "target_type": lookup[path], "status": "resolved"}
    return {"reference": reference, "normalized": value, "target_type": "unknown", "status": "missing"}


def _reachable_stages(entry_stage: str, links: list[ProgressionLinkSpec]) -> set[str]:
    if not entry_stage:
        return set()
    adjacency: dict[str, list[str]] = {}
    for link in links:
        adjacency.setdefault(link.from_stage, []).append(link.to_stage)
    seen = {entry_stage}
    stack = [entry_stage]
    while stack:
        current = stack.pop()
        for child in adjacency.get(current, []):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return seen


def _cycle_paths(stage_ids: set[str], links: list[ProgressionLinkSpec]) -> list[list[str]]:
    adjacency: dict[str, list[str]] = {stage_id: [] for stage_id in stage_ids}
    for link in links:
        if link.from_stage in adjacency and link.to_stage in stage_ids:
            adjacency[link.from_stage].append(link.to_stage)

    cycles: list[list[str]] = []
    stack: list[str] = []
    visited: set[str] = set()

    def visit(stage_id: str) -> None:
        if stage_id in stack:
            start = stack.index(stage_id)
            cycles.append([*stack[start:], stage_id])
            return
        if stage_id in visited:
            return
        stack.append(stage_id)
        for child in adjacency.get(stage_id, []):
            visit(child)
        stack.pop()
        visited.add(stage_id)

    for stage_id in stage_ids:
        visit(stage_id)
    return cycles
