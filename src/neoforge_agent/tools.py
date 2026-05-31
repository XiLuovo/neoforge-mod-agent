from __future__ import annotations

import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .models import ModSpec


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify_mod_id(text: str, fallback: str = "generated_mod") -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    if not slug:
        return fallback
    if not slug[0].isalpha():
        slug = f"mod_{slug}"
    return slug[:64]


def derive_display_name(mod_id: str) -> str:
    words = [word for word in mod_id.replace("_", " ").split(" ") if word]
    if not words:
        return "Generated Mod"
    return " ".join(word.capitalize() for word in words)


def derive_package_name(mod_id: str, base_package: str = "com.generated") -> str:
    return f"{base_package}.{mod_id}"


def pascal_case(text: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", text)
    words = [part for part in parts if part]
    if not words:
        return "Generated"
    return "".join(word[:1].upper() + word[1:] for word in words)


def upper_snake_case(text: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return normalized.upper() if normalized else "VALUE"


def write_json(path: Path, payload: Any) -> Path:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return path


def write_text(path: Path, content: str) -> Path:
    ensure_directory(path.parent)
    path.write_text(content, encoding="utf-8")
    return path


def safe_workspace_name(value: str | None, *, fallback: str | None = None) -> str:
    name = (value or fallback or "").strip()
    if not name:
        raise ValueError("Workspace name is required.")
    if name in {".", ".."}:
        raise ValueError(f"Workspace name must be a simple folder name: {name}")
    if any(separator in name for separator in ("/", "\\")):
        raise ValueError(f"Workspace name must not contain path separators: {name}")
    if Path(name).is_absolute() or ":" in name:
        raise ValueError(f"Workspace name must be relative to the configured workspace root: {name}")
    return name


def resolve_workspace_child(workspace_root: Path, workspace_name: str | None, *, fallback: str | None = None) -> Path:
    root = workspace_root.resolve()
    target = (root / safe_workspace_name(workspace_name, fallback=fallback)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Workspace must be inside {root}: {target}") from exc
    if target == root:
        raise ValueError("Workspace target must not be the workspace root.")
    return target


def resolve_managed_file(workspace: Path, relative_path: str) -> Path:
    root = workspace.resolve()
    raw = Path(str(relative_path))
    if raw.is_absolute():
        raise ValueError(f"Managed file path must be relative: {relative_path}")
    target = (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Managed file path escapes workspace: {relative_path}") from exc
    if target == root:
        raise ValueError("Managed file path must point to a file inside the workspace.")
    return target


def load_template_java_version(template_dir: Path) -> int | None:
    build_file = template_dir / "build.gradle"
    if not build_file.exists():
        return None
    match = re.search(
        r"JavaLanguageVersion\.of\((\d+)\)",
        build_file.read_text(encoding="utf-8"),
    )
    if not match:
        return None
    return int(match.group(1))


def prepare_workspace_dir(
    config: AppConfig,
    mod_id: str,
    workspace_name: str | None = None,
    overwrite: bool = False,
) -> Path:
    ensure_directory(config.workspace_root)
    base_name = safe_workspace_name(workspace_name, fallback=mod_id)
    target = resolve_workspace_child(config.workspace_root, base_name)
    if overwrite and target.exists():
        shutil.rmtree(target)
        return target
    if not target.exists():
        return target
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return resolve_workspace_child(config.workspace_root, f"{base_name}-{stamp}")


def copy_template_tree(template_dir: Path, destination_dir: Path) -> Path:
    if destination_dir.exists():
        raise FileExistsError(f"Destination already exists: {destination_dir}")
    shutil.copytree(template_dir, destination_dir)
    return destination_dir


def write_modspec_snapshot(project_dir: Path, spec: ModSpec, config: AppConfig) -> Path:
    path = config.agent_dir_for(project_dir) / "modspec.json"
    return write_json(path, spec.to_dict())


def write_pending_work_note(
    project_dir: Path,
    config: AppConfig,
    pending_actions: list[str],
) -> Path:
    lines = [
        "# Pending Implementation",
        "",
        "The Python skeleton is ready, but the following project mutations are still intentionally deferred:",
        "",
    ]
    lines.extend(f"- {action}" for action in pending_actions)
    lines.append("")
    lines.append(
        "The copied NeoForge template is still close to the bundled example project until Java/resource generation is implemented."
    )
    lines.append("")
    path = config.agent_dir_for(project_dir) / "PENDING_IMPLEMENTATION.md"
    return write_text(path, "\n".join(lines))


def write_manual_test_checklist(project_dir: Path, config: AppConfig, spec: ModSpec) -> Path:
    lines = [
        "# Manual Test Checklist",
        "",
        "## Startup",
        "",
        "- [ ] Game starts successfully",
        "- [ ] Mod appears in Mods list",
        "- [ ] Creative tab appears",
        "",
        "## Items",
        "",
    ]

    for item in spec.all_item_like():
        lines.append(f"- [ ] `{item.identifier}` has texture and correct language name")
        behavior = getattr(item, "behavior", None)
        if behavior is not None:
            if getattr(behavior, "events", None):
                lines.append(f"- [ ] `{item.identifier}` Behavior DSL triggers are covered in runtime/report: {_behavior_trigger_summary(behavior)}")
            elif behavior.behavior_type == "right_click_heal":
                lines.append(f"- [ ] `{item.identifier}` heals {behavior.amount} health on right click")
            elif behavior.behavior_type == "right_click_effect":
                lines.append(f"- [ ] `{item.identifier}` grants `{behavior.effect}` on right click")

    lines.extend(["", "## Blocks", ""])
    for block in spec.all_block_like():
        lines.append(f"- [ ] `{block.identifier}` can be placed")
        lines.append(f"- [ ] `{block.identifier}` has the expected texture")
        drop_name = getattr(block, "drop", None) or f"{spec.mod_id}:{block.identifier}"
        lines.append(f"- [ ] `{block.identifier}` drops `{drop_name}` as expected")
        if getattr(block, "feature_type", "") == "machine":
            lines.append(f"- [ ] `{block.identifier}` opens its generated menu screen on right click")
            lines.append(f"- [ ] `{block.identifier}` syncs energy and progress values while the menu is open")
            lines.append(f"- [ ] `{block.identifier}` exposes {getattr(block, 'inventory_slots', 0)} container slot(s)")
        behavior = getattr(block, "behavior", None)
        if behavior is not None and getattr(behavior, "events", None):
            triggers = _behavior_trigger_summary(behavior)
            if getattr(block, "feature_type", "") == "machine":
                lines.append(f"- [ ] `{block.identifier}` Behavior DSL semantic triggers are documented in `.agent/behavior-report.json`: {triggers}")
            else:
                lines.append(f"- [ ] `{block.identifier}` Behavior DSL triggers are covered in runtime/report: {triggers}")

    if spec.foods:
        lines.extend(["", "## Food", ""])
        for food in spec.foods:
            lines.append(f"- [ ] `{food.identifier}` is edible")
            lines.append(f"- [ ] `{food.identifier}` restores expected hunger/saturation")
            for effect in food.effects:
                lines.append(f"- [ ] `{food.identifier}` grants `{effect.effect}` for {effect.duration_ticks} ticks")

    if spec.swords:
        lines.extend(["", "## Sword", ""])
        for sword in spec.swords:
            lines.append(f"- [ ] `{sword.identifier}` is held like a tool")
            lines.append(f"- [ ] `{sword.identifier}` has expected combat behavior")
            behavior = getattr(sword, "behavior", None)
            if behavior is not None and getattr(behavior, "events", None):
                lines.append(f"- [ ] `{sword.identifier}` Behavior DSL triggers are covered in runtime/report: {_behavior_trigger_summary(behavior)}")
            if sword.on_hit is not None:
                lines.append(f"- [ ] `{sword.identifier}` triggers `{sword.on_hit.behavior_type}` for {sword.on_hit.seconds} seconds on hit")

    if spec.entities:
        lines.extend(["", "## Entities", ""])
        for entity in spec.entities:
            lines.append(f"- [ ] `{entity.identifier}` can be summoned with `/summon {spec.mod_id}:{entity.identifier}`")
            lines.append(f"- [ ] `{entity.identifier}` has a visible texture and correct language name")
            if entity.attack is not None and entity.attack.attack_type == "melee":
                lines.append(f"- [ ] `{entity.identifier}` uses its generated melee AI goal")
            if entity.drops:
                drop_names = ", ".join(drop.item for drop in entity.drops)
                lines.append(f"- [ ] `{entity.identifier}` drops expected loot: {drop_names}")
            if entity.spawn is not None and entity.spawn.enabled:
                lines.append(f"- [ ] `{entity.identifier}` can spawn from biome modifier `{entity.spawn.biomes}`")
            behavior = getattr(entity, "behavior", None)
            if behavior is not None and getattr(behavior, "events", None):
                lines.append(f"- [ ] `{entity.identifier}` Behavior DSL semantic triggers are documented in `.agent/behavior-report.json`: {_behavior_trigger_summary(behavior)}")

    if spec.all_world_like():
        lines.extend(["", "## World And Structures", ""])
        for dimension in spec.dimensions:
            lines.append(f"- [ ] `{dimension.identifier}` dimension data loads with `/execute in {spec.mod_id}:{dimension.identifier} run tp @s 0 80 0`")
        for biome in spec.biomes:
            lines.append(f"- [ ] `{biome.identifier}` biome JSON is present under `data/{spec.mod_id}/worldgen/biome`")
        for feature in spec.world_features:
            lines.append(f"- [ ] `{feature.identifier}` placed feature is attached to `{feature.biomes}` at step `{feature.step}`")
        for structure in spec.structures:
            lines.append(f"- [ ] `{structure.identifier}` structure data loads and can be checked with `/locate structure {spec.mod_id}:{structure.identifier}`")
        for pool in spec.loot_pools:
            lines.append(f"- [ ] `{pool.identifier}` chest loot table exists under `data/{spec.mod_id}/loot_table/chests`")

    if spec.recipes:
        lines.extend(["", "## Recipes", ""])
        for recipe in spec.recipes:
            lines.append(f"- [ ] `{recipe.identifier}` ({recipe.recipe_type}) works in crafting")

    if spec.java_extensions:
        lines.extend(["", "## Controlled Java Extensions", ""])
        for extension in spec.java_extensions:
            lines.append(f"- [ ] `{extension.class_name}` exists under the generated `extension` package")
            lines.append(f"- [ ] `{extension.class_name}` purpose is explainable from `.agent/java-extension-report.json`")
            for method in extension.methods:
                lines.append(f"- [ ] `{extension.class_name}.{method.name}()` returns the expected string")

    if spec.progressions:
        lines.extend(["", "## Progression", ""])
        for progression in spec.progressions:
            lines.append(f"- [ ] `{progression.identifier}` route is documented in `.agent/progression-report.json`")
            entry = progression.entry_stage or (progression.stages[0].identifier if progression.stages else "")
            end = progression.end_stage or (progression.stages[-1].identifier if progression.stages else "")
            if entry and end:
                lines.append(f"- [ ] `{progression.identifier}` can be played from `{entry}` to `{end}`")
            behavior = getattr(progression, "behavior", None)
            if behavior is not None and getattr(behavior, "events", None):
                lines.append(f"- [ ] `{progression.identifier}` Behavior DSL semantic triggers are documented in `.agent/behavior-report.json`: {_behavior_trigger_summary(behavior)}")
            for stage in progression.stages:
                lines.append(f"- [ ] Progression stage `{stage.identifier}` has matching in-game evidence")

    if spec.balance_plans:
        lines.extend(["", "## Balance Planner", ""])
        for plan in spec.balance_plans:
            lines.append(f"- [ ] `{plan.identifier}` economy plan is documented in `.agent/balance-report.json`")
            if plan.target_progression:
                lines.append(f"- [ ] `{plan.identifier}` recommendations are reviewed against progression `{plan.target_progression}`")

    if spec.quests:
        lines.extend(["", "## Quests And Guidebook", ""])
        for quest in spec.quests:
            lines.append(f"- [ ] `{quest.identifier}` quest chain is documented in `.agent/quest-report.json`")
            lines.append(f"- [ ] `{quest.identifier}` guide text is readable in `.agent/guidebook.md`")
            lines.append(f"- [ ] `{quest.identifier}` advancements exist under `data/{spec.mod_id}/advancement/{quest.identifier}`")
            lines.append(f"- [ ] `{quest.identifier}` Patchouli-style book data exists under `data/{spec.mod_id}/patchouli_books/{quest.guidebook_id}`")
            behavior = getattr(quest, "behavior", None)
            if behavior is not None and getattr(behavior, "events", None):
                lines.append(f"- [ ] `{quest.identifier}` Behavior DSL semantic triggers are documented in `.agent/behavior-report.json`: {_behavior_trigger_summary(behavior)}")

    lines.append("")
    path = config.agent_dir_for(project_dir) / "manual-test-checklist.md"
    return write_text(path, "\n".join(lines))


def _behavior_trigger_summary(behavior: object) -> str:
    labels = []
    for event in getattr(behavior, "events", []):
        triggers = []
        for trigger in [getattr(event, "trigger", ""), *getattr(event, "triggers", [])]:
            trigger_text = str(trigger or "").strip()
            if trigger_text and trigger_text not in triggers:
                triggers.append(trigger_text)
        label = " + ".join(triggers) if triggers else str(getattr(event, "trigger", "") or "").strip()
        mode = getattr(event, "trigger_mode", "any")
        if mode and mode != "any":
            label = f"{label} ({mode})"
        if label:
            labels.append(label)
    return ", ".join(labels)


def write_generation_summary(
    project_dir: Path,
    config: AppConfig,
    payload: dict[str, Any],
) -> Path:
    return write_json(config.agent_dir_for(project_dir) / "generation-summary.json", payload)
