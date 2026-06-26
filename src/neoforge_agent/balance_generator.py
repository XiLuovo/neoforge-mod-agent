from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .config import AppConfig
from .models import BalancePlanSpec, ModSpec, ProgressionSpec
from .tools import write_json, write_text


RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]
RARITY_DROP_CHANCE = {
    "common": 1.0,
    "uncommon": 0.65,
    "rare": 0.35,
    "epic": 0.12,
    "legendary": 0.05,
}
RARITY_LOOT_WEIGHT = {
    "common": 6,
    "uncommon": 4,
    "rare": 2,
    "epic": 1,
    "legendary": 1,
}
PROFILE_MULTIPLIER = {
    "easy": 0.8,
    "standard": 1.0,
    "expert": 1.35,
}


class BalancePlanGenerator:
    """Write V7.1 recipe, loot, rarity, and machine-balance reports."""

    version = "7.1"

    def generate(self, project_dir: Path, spec: ModSpec, config: AppConfig) -> list[Path]:
        if not spec.balance_plans:
            return []
        agent_dir = config.agent_dir_for(project_dir)
        payload = balance_report_payload(spec)
        report_json = agent_dir / "balance-report.json"
        report_md = agent_dir / "balance-report.md"
        write_json(report_json, payload)
        write_text(report_md, render_balance_report_markdown(payload))
        return [report_json, report_md]


def balance_report_payload(spec: ModSpec) -> dict[str, Any]:
    lookup = _target_lookup(spec)
    progressions = {progression.identifier: progression for progression in spec.progressions}
    plans = [_balance_plan_payload(plan, spec, lookup, progressions) for plan in spec.balance_plans]

    totals = Counter()
    rarity_counts: Counter[str] = Counter()
    for plan in plans:
        totals["plan_count"] += 1
        totals["recipe_recommendations_count"] += len(plan["recipes"])
        totals["missing_recipe_suggestions_count"] += len(plan["missing_recipes"])
        totals["machine_balance_rules_count"] += len(plan["machines"])
        totals["entity_drop_rules_count"] += len(plan["entity_drops"])
        totals["loot_weight_rules_count"] += len(plan["loot_weights"])
        totals["rarity_assignments_count"] += len(plan["rarities"])
        rarity_counts.update(entry["rarity"] for entry in plan["rarities"])

    return {
        "version": BalancePlanGenerator.version,
        "status": "pass" if all(plan["status"] == "pass" for plan in plans) else "warning",
        "mod_id": spec.mod_id,
        "totals": {
            **dict(totals),
            "rarity_counts": dict(sorted(rarity_counts.items())),
        },
        "plans": plans,
    }


def render_balance_report_markdown(payload: dict[str, Any]) -> str:
    totals = payload.get("totals", {})
    lines = [
        "# V7.1 Recipe / Loot / Balance Planner Report",
        "",
        f"Status: `{payload.get('status', 'unknown')}`",
        f"Mod ID: `{payload.get('mod_id', '')}`",
        f"Plans: `{totals.get('plan_count', 0)}`",
        f"Recipe recommendations: `{totals.get('recipe_recommendations_count', 0)}`",
        f"Missing recipe suggestions: `{totals.get('missing_recipe_suggestions_count', 0)}`",
        f"Machine balance rules: `{totals.get('machine_balance_rules_count', 0)}`",
        f"Entity drop rules: `{totals.get('entity_drop_rules_count', 0)}`",
        f"Loot weight rules: `{totals.get('loot_weight_rules_count', 0)}`",
        f"Rarity assignments: `{totals.get('rarity_assignments_count', 0)}`",
        "",
    ]

    for plan in payload.get("plans", []):
        lines.extend(
            [
                f"## {plan.get('title', plan.get('id', 'Balance Plan'))}",
                "",
                f"ID: `{plan.get('id', '')}`",
                f"Profile: `{plan.get('profile', '')}`",
                f"Target progression: `{plan.get('target_progression', '') or 'all'}`",
                "",
            ]
        )
        if plan.get("summary"):
            lines.extend([str(plan["summary"]), ""])

        lines.extend(["### Missing Recipes", ""])
        if plan.get("missing_recipes"):
            for suggestion in plan["missing_recipes"]:
                lines.append(
                    f"- `{suggestion['suggested_id']}` for `{suggestion['target']}` "
                    f"as `{suggestion['recipe_type']}` using {', '.join(f'`{item}`' for item in suggestion['ingredients'])}"
                )
        else:
            lines.append("- none")
        lines.append("")

        lines.extend(["### Machine Balance", ""])
        if plan.get("machines"):
            for machine in plan["machines"]:
                lines.append(
                    f"- `{machine['id']}`: progress `{machine['current_max_progress']}` -> "
                    f"`{machine['suggested_max_progress']}`, energy/t `{machine['current_energy_per_tick']}` -> "
                    f"`{machine['suggested_energy_per_tick']}`"
                )
        else:
            lines.append("- none")
        lines.append("")

        lines.extend(["### Drops And Loot", ""])
        for drop in plan.get("entity_drops", []):
            lines.append(
                f"- entity `{drop['entity']}` drops `{drop['item']}` as `{drop['rarity']}` "
                f"chance `{drop['current_chance']}` -> `{drop['suggested_chance']}`"
            )
        for loot in plan.get("loot_weights", []):
            lines.append(
                f"- loot `{loot['pool']}` entry `{loot['item']}` as `{loot['rarity']}` "
                f"weight `{loot['current_weight']}` -> `{loot['suggested_weight']}`"
            )
        if not plan.get("entity_drops") and not plan.get("loot_weights"):
            lines.append("- none")
        lines.append("")

    return "\n".join(lines)


def _balance_plan_payload(
    plan: BalancePlanSpec,
    spec: ModSpec,
    lookup: dict[str, str],
    progressions: dict[str, ProgressionSpec],
) -> dict[str, Any]:
    progression = progressions.get(plan.target_progression) if plan.target_progression else None
    stage_context = _stage_context(progression, spec.mod_id) if progression is not None else {}
    profile = plan.profile or "standard"
    multiplier = PROFILE_MULTIPLIER.get(profile, 1.0)
    rarities = _rarity_assignments(spec, lookup, stage_context)
    rarity_by_id = {entry["id"]: entry["rarity"] for entry in rarities}

    recipes = [_recipe_recommendation(recipe, spec.mod_id, rarity_by_id, stage_context) for recipe in spec.recipes]
    missing_recipes = _missing_recipe_suggestions(spec, rarity_by_id)
    machines = [_machine_balance(machine, multiplier, stage_context) for machine in spec.machines]
    entity_drops = [
        _entity_drop_rule(entity.identifier, drop, spec.mod_id, rarity_by_id)
        for entity in spec.entities
        for drop in entity.drops
    ]
    loot_weights = [
        _loot_weight_rule(pool.identifier, entry, spec.mod_id, rarity_by_id)
        for pool in spec.loot_pools
        for entry in pool.entries
    ]

    status = "pass"
    warnings: list[str] = []
    if plan.target_progression and plan.target_progression not in progressions:
        status = "warning"
        warnings.append(f"Target progression '{plan.target_progression}' was not found.")
    if not any([recipes, missing_recipes, machines, entity_drops, loot_weights]):
        status = "warning"
        warnings.append("No recipes, machines, drops, or loot pools were available to balance.")

    return {
        "id": plan.identifier,
        "title": plan.title,
        "profile": profile,
        "target_progression": plan.target_progression,
        "summary": plan.summary,
        "status": status,
        "warnings": warnings,
        "progression": _progression_summary(progression),
        "rarities": rarities,
        "recipes": recipes,
        "missing_recipes": missing_recipes,
        "machines": machines,
        "entity_drops": entity_drops,
        "loot_weights": loot_weights,
        "economy_summary": {
            "source_count": len(spec.ores) + len(entity_drops) + len(loot_weights),
            "sink_count": len(spec.recipes) + len(spec.machines),
            "progression_stage_count": len(progression.stages) if progression is not None else 0,
            "bottleneck_items": sorted(
                {
                    _strip_namespace(drop["item"], spec.mod_id)
                    for drop in entity_drops
                    if drop["rarity"] in {"rare", "epic", "legendary"}
                }
            ),
        },
    }


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
    for recipe in spec.recipes:
        add(recipe.identifier, "recipe")
        lookup[f"recipe:{recipe.identifier}"] = "recipe"
    return lookup


def _stage_context(progression: ProgressionSpec | None, mod_id: str) -> dict[str, dict[str, Any]]:
    if progression is None:
        return {}
    context: dict[str, dict[str, Any]] = {}
    for index, stage in enumerate(progression.stages):
        for reference in [*stage.requires, *stage.provides, *stage.unlocks, *stage.evidence]:
            normalized = _strip_namespace(reference, mod_id)
            context[normalized] = {
                "stage_id": stage.identifier,
                "stage_type": stage.stage_type,
                "stage_index": index,
            }
    return context


def _rarity_assignments(
    spec: ModSpec,
    lookup: dict[str, str],
    stage_context: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    assignments = []
    seen: set[str] = set()
    for identifier, target_type in sorted(lookup.items()):
        if ":" in identifier or identifier.startswith("recipe:"):
            continue
        if identifier in seen:
            continue
        seen.add(identifier)
        context = stage_context.get(identifier, {})
        rarity = _rarity_for(target_type, context.get("stage_type", ""), int(context.get("stage_index", 0)))
        assignments.append(
            {
                "id": identifier,
                "target_type": target_type,
                "rarity": rarity,
                "reason": context.get("stage_id", f"default_{target_type}_rule"),
            }
        )
    return assignments


def _recipe_recommendation(recipe, mod_id: str, rarity_by_id: dict[str, str], stage_context: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result_id = _strip_namespace(recipe.result, mod_id)
    rarity = rarity_by_id.get(result_id, "uncommon")
    ingredient_count = len(recipe.ingredients) if recipe.recipe_type == "shapeless" else len(recipe.keys)
    suggested_count = 2 if rarity == "common" and ingredient_count >= 2 else 1
    context = stage_context.get(result_id, {})
    return {
        "id": recipe.identifier,
        "recipe_type": recipe.recipe_type,
        "result": recipe.result,
        "current_count": recipe.count,
        "suggested_count": suggested_count,
        "ingredient_count": ingredient_count,
        "rarity": rarity,
        "stage_id": context.get("stage_id", ""),
        "status": "ok" if recipe.count == suggested_count else "review",
    }


def _missing_recipe_suggestions(spec: ModSpec, rarity_by_id: dict[str, str]) -> list[dict[str, Any]]:
    recipe_targets = {_strip_namespace(recipe.result, spec.mod_id) for recipe in spec.recipes}
    suggestions: list[dict[str, Any]] = []
    material = "ruby" if any(item.identifier == "ruby" for item in spec.items) else "minecraft:iron_ingot"

    for machine in spec.machines:
        if machine.identifier not in recipe_targets:
            suggestions.append(
                {
                    "target": machine.identifier,
                    "target_type": "machine",
                    "suggested_id": f"craft_{machine.identifier}",
                    "recipe_type": "shaped",
                    "ingredients": [f"{spec.mod_id}:{material}" if ":" not in material else material, "minecraft:iron_ingot", "minecraft:redstone"],
                    "rarity": rarity_by_id.get(machine.identifier, "uncommon"),
                    "reason": "Machine blocks should have an explicit crafting sink in the economy.",
                }
            )

    for equipment in [*spec.swords, *spec.tools, *spec.armors]:
        if equipment.identifier not in recipe_targets:
            suggestions.append(
                {
                    "target": equipment.identifier,
                    "target_type": equipment.feature_type,
                    "suggested_id": f"craft_{equipment.identifier}",
                    "recipe_type": "shaped",
                    "ingredients": [f"{spec.mod_id}:{material}" if ":" not in material else material, "minecraft:stick"],
                    "rarity": rarity_by_id.get(equipment.identifier, "rare"),
                    "reason": "Equipment should consume the main progression material before combat or exploration unlocks.",
                }
            )
    return suggestions


def _machine_balance(machine, multiplier: float, stage_context: dict[str, dict[str, Any]]) -> dict[str, Any]:
    base_progress = {
        "furnace": 100,
        "compressor": 120,
        "upgrade_table": 160,
        "magic_altar": 220,
        "storage": 20,
    }.get(machine.machine_kind, 100)
    base_energy = {
        "furnace": 16,
        "compressor": 24,
        "upgrade_table": 32,
        "magic_altar": 48,
        "storage": 0,
    }.get(machine.machine_kind, 20)
    context = stage_context.get(machine.identifier, {})
    stage_bonus = int(context.get("stage_index", 0)) * 5
    suggested_progress = max(1, int((base_progress + stage_bonus) * multiplier))
    suggested_energy = max(0, int(base_energy * multiplier))
    return {
        "id": machine.identifier,
        "machine_kind": machine.machine_kind,
        "stage_id": context.get("stage_id", ""),
        "current_max_progress": machine.max_progress,
        "current_energy_per_tick": machine.energy_per_tick,
        "current_total_energy": machine.max_progress * machine.energy_per_tick,
        "suggested_max_progress": suggested_progress,
        "suggested_energy_per_tick": suggested_energy,
        "suggested_total_energy": suggested_progress * suggested_energy,
        "status": "ok" if machine.max_progress == suggested_progress and machine.energy_per_tick == suggested_energy else "review",
    }


def _entity_drop_rule(entity_id: str, drop, mod_id: str, rarity_by_id: dict[str, str]) -> dict[str, Any]:
    item_id = _strip_namespace(drop.item, mod_id)
    rarity = rarity_by_id.get(item_id, "rare")
    suggested_chance = RARITY_DROP_CHANCE[rarity]
    return {
        "entity": entity_id,
        "item": drop.item,
        "min_count": drop.min_count,
        "max_count": drop.max_count,
        "rarity": rarity,
        "current_chance": drop.chance,
        "suggested_chance": suggested_chance,
        "status": "ok" if abs(drop.chance - suggested_chance) <= 0.15 else "review",
    }


def _loot_weight_rule(pool_id: str, entry, mod_id: str, rarity_by_id: dict[str, str]) -> dict[str, Any]:
    item_id = _strip_namespace(entry.item, mod_id)
    rarity = rarity_by_id.get(item_id, "uncommon")
    suggested_weight = RARITY_LOOT_WEIGHT[rarity]
    suggested_chance = RARITY_DROP_CHANCE[rarity]
    return {
        "pool": pool_id,
        "item": entry.item,
        "min_count": entry.min_count,
        "max_count": entry.max_count,
        "rarity": rarity,
        "current_weight": entry.weight,
        "suggested_weight": suggested_weight,
        "current_chance": entry.chance,
        "suggested_chance": suggested_chance,
        "status": "ok" if entry.weight == suggested_weight and abs(entry.chance - suggested_chance) <= 0.2 else "review",
    }


def _progression_summary(progression: ProgressionSpec | None) -> dict[str, Any]:
    if progression is None:
        return {}
    return {
        "id": progression.identifier,
        "title": progression.title,
        "stage_count": len(progression.stages),
        "stage_types": [stage.stage_type for stage in progression.stages],
    }


def _rarity_for(target_type: str, stage_type: str, stage_index: int) -> str:
    if stage_type in {"structure", "dimension"} or target_type in {"structure", "dimension"}:
        return "epic"
    if stage_type in {"entity", "equipment"} or target_type in {"sword", "tool", "armor", "entity"}:
        return "rare"
    if stage_type in {"machine", "loot_pool"} or target_type in {"machine", "loot_pool"}:
        return "uncommon" if stage_index < 4 else "rare"
    if stage_type in {"material", "recipe"}:
        return "uncommon"
    return "common"


def _strip_namespace(reference: str, mod_id: str) -> str:
    value = str(reference).strip()
    if value.startswith("recipe:"):
        return value
    if ":" in value:
        namespace, path = value.split(":", 1)
        if namespace == mod_id:
            return path
    return value
