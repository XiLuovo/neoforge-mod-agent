from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import AppConfig
from .models import ModSpec, ProgressionSpec, QuestSpec, QuestTaskSpec
from .tools import ensure_directory, write_json, write_text


ADVANCEMENT_TRIGGER_BY_TASK = {
    "obtain_item": "minecraft:inventory_changed",
    "craft_item": "minecraft:recipe_crafted",
    "mine_block": "minecraft:inventory_changed",
    "use_machine": "minecraft:inventory_changed",
    "kill_entity": "minecraft:player_killed_entity",
    "enter_dimension": "minecraft:changed_dimension",
    "visit_structure": "minecraft:location",
    "milestone": "minecraft:tick",
}


class QuestGuideGenerator:
    """Write V7.2 quest chains, advancements, and guidebook data."""

    version = "7.2"

    def generate(self, project_dir: Path, resources_dir: Path, spec: ModSpec, config: AppConfig) -> list[Path]:
        if not spec.quests:
            return []
        agent_dir = config.agent_dir_for(project_dir)
        progressions = {progression.identifier: progression for progression in spec.progressions}
        generated: list[Path] = []
        quest_payloads = []
        for quest in spec.quests:
            quest_tasks = _tasks_for_quest(quest, progressions.get(quest.target_progression), spec.mod_id)
            quest_payloads.append(_quest_payload(quest, quest_tasks, spec.mod_id, progressions))
            generated.extend(_write_advancements(resources_dir, spec.mod_id, quest, quest_tasks))
            generated.extend(_write_patchouli_book(resources_dir, spec.mod_id, quest, quest_tasks))

        payload = {
            "version": self.version,
            "status": "pass",
            "mod_id": spec.mod_id,
            "totals": {
                "quest_count": len(quest_payloads),
                "task_count": sum(len(quest["tasks"]) for quest in quest_payloads),
                "advancement_count": sum(len(quest["advancements"]) for quest in quest_payloads),
                "guidebook_count": len({quest["guidebook_id"] for quest in quest_payloads}),
            },
            "quests": quest_payloads,
        }
        report_json = agent_dir / "quest-report.json"
        report_md = agent_dir / "quest-report.md"
        guide_md = agent_dir / "guidebook.md"
        write_json(report_json, payload)
        write_text(report_md, render_quest_report_markdown(payload))
        write_text(guide_md, render_guidebook_markdown(payload))
        generated.extend([report_json, report_md, guide_md])
        return generated


def render_quest_report_markdown(payload: dict[str, Any]) -> str:
    totals = payload.get("totals", {})
    lines = [
        "# V7.2 Quest / Advancement / Guide Report",
        "",
        f"Status: `{payload.get('status', 'unknown')}`",
        f"Mod ID: `{payload.get('mod_id', '')}`",
        f"Quests: `{totals.get('quest_count', 0)}`",
        f"Tasks: `{totals.get('task_count', 0)}`",
        f"Advancements: `{totals.get('advancement_count', 0)}`",
        f"Guidebooks: `{totals.get('guidebook_count', 0)}`",
        "",
    ]
    for quest in payload.get("quests", []):
        lines.extend(
            [
                f"## {quest.get('title', quest.get('id', 'Quest'))}",
                "",
                f"ID: `{quest.get('id', '')}`",
                f"Target progression: `{quest.get('target_progression', '') or 'none'}`",
                f"Guidebook: `{quest.get('guidebook_id', '')}`",
                "",
            ]
        )
        if quest.get("summary"):
            lines.extend([str(quest["summary"]), ""])
        if quest.get("behavior"):
            lines.extend(["### Behavior", ""])
            for event in quest["behavior"].get("events", []):
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
        for task in quest.get("tasks", []):
            lines.append(f"- `{task['id']}` [{task['type']}] {task['title']} -> `{task['target']}`")
            if task.get("guide_text"):
                lines.append(f"  - guide: {task['guide_text']}")
        lines.append("")
    return "\n".join(lines)


def render_guidebook_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Generated Guidebook", ""]
    for quest in payload.get("quests", []):
        lines.extend([f"## {quest.get('title', quest.get('id', 'Quest'))}", ""])
        if quest.get("summary"):
            lines.extend([str(quest["summary"]), ""])
        for index, task in enumerate(quest.get("tasks", []), start=1):
            lines.extend(
                [
                    f"### {index}. {task['title']}",
                    "",
                    task.get("guide_text") or task.get("description") or f"Complete `{task['id']}`.",
                    "",
                ]
            )
    return "\n".join(lines)


def _quest_payload(
    quest: QuestSpec,
    tasks: list[QuestTaskSpec],
    mod_id: str,
    progressions: dict[str, ProgressionSpec],
) -> dict[str, Any]:
    progression = progressions.get(quest.target_progression) if quest.target_progression else None
    return {
        "id": quest.identifier,
        "title": quest.title,
        "summary": quest.summary,
        "target_progression": quest.target_progression,
        "guidebook_id": quest.guidebook_id,
        "category": quest.category,
        "progression_stage_count": len(progression.stages) if progression is not None else 0,
        "tasks": [
            {
                "id": task.identifier,
                "type": task.task_type,
                "title": task.title,
                "description": task.description,
                "target": task.target,
                "icon": _icon_for_task(task, mod_id),
                "parent": task.parent,
                "guide_text": task.guide_text,
                "reward_xp": task.reward_xp,
            }
            for task in tasks
        ],
        "advancements": [
            {
                "id": task.identifier,
                "path": f"data/{mod_id}/advancement/{quest.identifier}/{task.identifier}.json",
                "trigger": ADVANCEMENT_TRIGGER_BY_TASK.get(task.task_type, "minecraft:tick"),
            }
            for task in tasks
        ],
        "guidebook_paths": {
            "book": f"data/{mod_id}/patchouli_books/{quest.guidebook_id}/book.json",
            "category": f"data/{mod_id}/patchouli_books/{quest.guidebook_id}/en_us/categories/{quest.category}.json",
            "entry": f"data/{mod_id}/patchouli_books/{quest.guidebook_id}/en_us/entries/{quest.identifier}.json",
        },
        "behavior": quest.behavior.to_dict() if quest.behavior is not None else None,
    }


def _tasks_for_quest(quest: QuestSpec, progression: ProgressionSpec | None, mod_id: str) -> list[QuestTaskSpec]:
    if quest.tasks:
        tasks = []
        previous_id = ""
        for task in quest.tasks:
            normalized = _normalize_task(task, previous_id, mod_id)
            tasks.append(normalized)
            previous_id = normalized.identifier
        return tasks
    if progression is None:
        return []
    tasks = []
    previous = ""
    for stage in progression.stages:
        task = QuestTaskSpec(
            identifier=stage.identifier,
            title=stage.title,
            description=stage.description,
            task_type=_task_type_for_stage(stage.stage_type),
            target=_first_reference([*stage.evidence, *stage.provides, *stage.requires]),
            icon=_first_reference([*stage.evidence, *stage.provides, *stage.requires]),
            parent=previous,
            guide_text=stage.description or _guide_text_for_stage(stage.stage_type, stage.title),
            reward_xp=25,
        )
        tasks.append(_normalize_task(task, previous, mod_id))
        previous = task.identifier
    return tasks

def _normalize_task(task: QuestTaskSpec, previous_id: str, mod_id: str) -> QuestTaskSpec:
    parent = task.parent or previous_id
    icon = task.icon or task.target or f"{mod_id}:ruby"
    target = task.target or icon
    guide_text = task.guide_text or task.description or _guide_text_for_stage(task.task_type, task.title)
    return QuestTaskSpec(
        identifier=task.identifier,
        title=task.title,
        description=task.description,
        task_type=task.task_type,
        target=target,
        icon=icon,
        parent=parent if parent != task.identifier else "",
        guide_text=guide_text,
        reward_xp=task.reward_xp,
    )


def _write_advancements(resources_dir: Path, mod_id: str, quest: QuestSpec, tasks: list[QuestTaskSpec]) -> list[Path]:
    paths: list[Path] = []
    root = ensure_directory(resources_dir / "data" / mod_id / "advancement" / quest.identifier)
    for index, task in enumerate(tasks):
        parent = task.parent
        if not parent and index > 0:
            parent = tasks[index - 1].identifier
        payload = _advancement_payload(mod_id, quest, task, parent)
        path = root / f"{task.identifier}.json"
        write_json(path, payload)
        paths.append(path)
    return paths


def _advancement_payload(mod_id: str, quest: QuestSpec, task: QuestTaskSpec, parent: str) -> dict[str, Any]:
    display: dict[str, Any] = {
        "icon": {"id": _resource(task.icon, mod_id)},
        "title": task.title,
        "description": task.description or task.guide_text,
        "frame": "task",
        "show_toast": True,
        "announce_to_chat": False,
        "hidden": False,
    }
    if not parent:
        display["background"] = "minecraft:gui/advancements/backgrounds/stone"
    payload: dict[str, Any] = {
        "display": display,
        "criteria": {
            task.identifier: _criterion(task, mod_id),
        },
        "requirements": [[task.identifier]],
    }
    if parent:
        payload["parent"] = f"{mod_id}:{quest.identifier}/{parent}"
    if task.reward_xp > 0:
        payload["rewards"] = {"experience": task.reward_xp}
    return payload


def _criterion(task: QuestTaskSpec, mod_id: str) -> dict[str, Any]:
    trigger = ADVANCEMENT_TRIGGER_BY_TASK.get(task.task_type, "minecraft:tick")
    item = _resource(task.target or task.icon, mod_id)
    if task.task_type in {"obtain_item", "mine_block", "use_machine"}:
        return {"trigger": trigger, "conditions": {"items": [{"items": item}]}}
    if task.task_type == "craft_item":
        return {"trigger": trigger, "conditions": {"recipe_id": item}}
    if task.task_type == "kill_entity":
        return {"trigger": trigger, "conditions": {"entity": {"type": item}}}
    if task.task_type == "enter_dimension":
        return {"trigger": trigger, "conditions": {"to": item}}
    if task.task_type == "visit_structure":
        return {"trigger": trigger, "conditions": {"player": {"located": {"structures": item}}}}
    return {"trigger": trigger}


def _write_patchouli_book(resources_dir: Path, mod_id: str, quest: QuestSpec, tasks: list[QuestTaskSpec]) -> list[Path]:
    book_root = resources_dir / "data" / mod_id / "patchouli_books" / quest.guidebook_id
    category_dir = ensure_directory(book_root / "en_us" / "categories")
    entry_dir = ensure_directory(book_root / "en_us" / "entries")
    book_path = book_root / "book.json"
    category_path = category_dir / f"{quest.category}.json"
    entry_path = entry_dir / f"{quest.identifier}.json"
    write_json(
        book_path,
        {
            "name": quest.title,
            "landing_text": quest.summary or "Follow the generated quest chain.",
            "version": 1,
            "book_texture": "patchouli:textures/gui/book_blue.png",
            "model": "patchouli:book_blue",
        },
    )
    write_json(
        category_path,
        {
            "name": quest.title,
            "description": quest.summary or "Generated guide category.",
            "icon": _resource(tasks[0].icon if tasks else f"{mod_id}:ruby", mod_id),
        },
    )
    write_json(
        entry_path,
        {
            "name": quest.title,
            "category": quest.category,
            "icon": _resource(tasks[0].icon if tasks else f"{mod_id}:ruby", mod_id),
            "pages": [
                {
                    "type": "patchouli:text",
                    "title": task.title,
                    "text": task.guide_text or task.description or f"Complete {task.title}.",
                }
                for task in tasks
            ],
        },
    )
    return [book_path, category_path, entry_path]


def _task_type_for_stage(stage_type: str) -> str:
    return {
        "ore": "mine_block",
        "material": "obtain_item",
        "recipe": "craft_item",
        "machine": "use_machine",
        "equipment": "craft_item",
        "entity": "kill_entity",
        "structure": "visit_structure",
        "loot_pool": "obtain_item",
        "dimension": "enter_dimension",
    }.get(stage_type, "milestone")


def _guide_text_for_stage(stage_type: str, title: str) -> str:
    return {
        "ore": f"Start by finding and mining the resource for {title}.",
        "material": f"Turn early resources into the material needed for {title}.",
        "machine": f"Build and use the machine step for {title}.",
        "equipment": f"Craft the equipment needed for {title}.",
        "entity": f"Prepare for combat and complete {title}.",
        "structure": f"Explore the generated structure for {title}.",
        "loot_pool": f"Open the reward source for {title}.",
        "dimension": f"Use the unlocked route to reach {title}.",
    }.get(stage_type, f"Complete {title}.")


def _first_reference(values: list[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


def _icon_for_task(task: QuestTaskSpec, mod_id: str) -> str:
    return _resource(task.icon or task.target or f"{mod_id}:ruby", mod_id)


def _resource(value: str, mod_id: str) -> str:
    value = str(value).strip()
    if value.startswith("recipe:"):
        value = value.removeprefix("recipe:")
    if not value:
        return f"{mod_id}:ruby"
    if ":" in value or value.startswith("#"):
        return value
    return f"{mod_id}:{value}"
