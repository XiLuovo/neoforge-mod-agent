from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .config import AppConfig
from .models import ModSpec
from .tools import write_json, write_text


RUNTIME_BEHAVIOR_HOSTS = {"item", "block", "sword", "ore"}
REPORT_ONLY_BEHAVIOR_HOSTS = {"machine", "entity", "progression", "quest"}


class BehaviorReportGenerator:
    version = "5.1-shared"

    def generate(self, project_dir: Path, spec: ModSpec, config: AppConfig) -> list[Path]:
        payload = behavior_report_payload(spec)
        if not payload["hosts"]:
            return []

        agent_dir = config.agent_dir_for(project_dir)
        report_json = agent_dir / "behavior-report.json"
        report_md = agent_dir / "behavior-report.md"
        write_json(report_json, payload)
        write_text(report_md, render_behavior_report_markdown(payload))
        return [report_json, report_md]


def behavior_report_payload(spec: ModSpec) -> dict[str, Any]:
    hosts = [_behavior_host_payload(feature) for feature in spec.iter_features() if getattr(feature, "behavior", None) is not None]
    totals = Counter()
    host_type_counts: Counter[str] = Counter()
    runtime_surface_counts: Counter[str] = Counter()
    trigger_counts: Counter[str] = Counter()
    condition_type_counts: Counter[str] = Counter()
    action_type_counts: Counter[str] = Counter()

    for host in hosts:
        host_type_counts.update([host["host_type"]])
        runtime_surface_counts.update([host["runtime_surface"]])
        for event in host["behavior"].get("events", []):
            totals["event_count"] += 1

            event_triggers = _event_triggers(event)
            totals["trigger_slot_count"] += len(event_triggers)
            trigger_counts.update(event_triggers)
            if event.get("trigger_mode", "any") != "any" or len(event_triggers) > 1:
                totals["combo_event_count"] += 1
            if event.get("cooldown_ticks", 0):
                totals["cooldown_event_count"] += 1
            if event.get("interval_ticks", 0):
                totals["interval_event_count"] += 1
            if event.get("window_ticks", 0):
                totals["window_event_count"] += 1
            if event.get("state_key") is not None:
                totals["event_state_count"] += 1
            if event.get("resource") is not None:
                totals["event_resource_count"] += 1

            conditions = event.get("conditions", [])
            actions = event.get("actions", [])
            totals["condition_count"] += len(conditions)
            totals["action_count"] += len(actions)

            for condition in conditions:
                condition_type = str(condition.get("type", ""))
                if condition_type:
                    condition_type_counts.update([condition_type])
                if _uses_state_fields(condition):
                    totals["state_condition_count"] += 1
                if _uses_resource_fields(condition):
                    totals["resource_condition_count"] += 1
                if condition_type == "cooldown_ready":
                    totals["cooldown_condition_count"] += 1

            for action in actions:
                action_type = str(action.get("type", ""))
                if action_type:
                    action_type_counts.update([action_type])
                if _uses_state_fields(action):
                    totals["state_action_count"] += 1
                if _uses_resource_fields(action):
                    totals["resource_action_count"] += 1
                if action_type == "chain_event":
                    totals["chain_action_count"] += 1
                if action_type == "cooldown":
                    totals["cooldown_action_count"] += 1

    host_count = len(hosts)
    compiled_host_count = sum(1 for host in hosts if host["runtime_surface"] == "compiled")
    report_only_host_count = host_count - compiled_host_count

    return {
        "version": BehaviorReportGenerator.version,
        "status": "pass",
        "mod_id": spec.mod_id,
        "totals": {
            "host_count": host_count,
            "compiled_host_count": compiled_host_count,
            "report_only_host_count": report_only_host_count,
            "event_count": totals["event_count"],
            "trigger_slot_count": totals["trigger_slot_count"],
            "condition_count": totals["condition_count"],
            "action_count": totals["action_count"],
            "combo_event_count": totals["combo_event_count"],
            "cooldown_event_count": totals["cooldown_event_count"],
            "interval_event_count": totals["interval_event_count"],
            "window_event_count": totals["window_event_count"],
            "event_state_count": totals["event_state_count"],
            "event_resource_count": totals["event_resource_count"],
            "state_condition_count": totals["state_condition_count"],
            "resource_condition_count": totals["resource_condition_count"],
            "cooldown_condition_count": totals["cooldown_condition_count"],
            "state_action_count": totals["state_action_count"],
            "resource_action_count": totals["resource_action_count"],
            "chain_action_count": totals["chain_action_count"],
            "cooldown_action_count": totals["cooldown_action_count"],
            "host_type_counts": dict(sorted(host_type_counts.items())),
            "runtime_surface_counts": dict(sorted(runtime_surface_counts.items())),
            "trigger_counts": dict(sorted(trigger_counts.items())),
            "condition_type_counts": dict(sorted(condition_type_counts.items())),
            "action_type_counts": dict(sorted(action_type_counts.items())),
        },
        "hosts": hosts,
    }


def render_behavior_report_markdown(payload: dict[str, Any]) -> str:
    totals = payload.get("totals", {})
    lines = [
        "# V5.1 Shared Behavior Report",
        "",
        f"Status: `{payload.get('status', 'unknown')}`",
        f"Mod ID: `{payload.get('mod_id', '')}`",
        f"Hosts: `{totals.get('host_count', 0)}`",
        f"Events: `{totals.get('event_count', 0)}`",
        f"Combo events: `{totals.get('combo_event_count', 0)}`",
        f"State actions: `{totals.get('state_action_count', 0)}`",
        f"Resource actions: `{totals.get('resource_action_count', 0)}`",
        f"Chain actions: `{totals.get('chain_action_count', 0)}`",
        "",
        "## Host Coverage",
        "",
    ]
    for host in payload.get("hosts", []):
        lines.append(
            f"- `{host.get('host_type', '')}:{host.get('identifier', '')}` "
            f"[{host.get('runtime_surface', 'report_only')}] {host.get('behavior', {}).get('type', '')}"
        )
        if host.get("summary"):
            lines.append(f"  - {host['summary']}")
        for event in host.get("behavior", {}).get("events", []):
            triggers = _event_triggers(event)
            trigger_mode = event.get("trigger_mode", "any")
            details = ", ".join(triggers) if triggers else event.get("trigger", "")
            lines.append(f"  - `{details}` mode=`{trigger_mode}`")
            if event.get("conditions"):
                condition_types = ", ".join(condition.get("type", "") for condition in event["conditions"] if condition.get("type"))
                lines.append(f"    - conditions: {condition_types}")
            if event.get("actions"):
                action_types = ", ".join(action.get("type", "") for action in event["actions"] if action.get("type"))
                lines.append(f"    - actions: {action_types}")
    lines.extend(["", "## Trigger Counts", ""])
    for trigger, count in payload.get("totals", {}).get("trigger_counts", {}).items():
        lines.append(f"- `{trigger}`: {count}")
    return "\n".join(lines)


def _behavior_host_payload(feature: object) -> dict[str, Any]:
    behavior = getattr(feature, "behavior", None)
    host_type = getattr(feature, "feature_type", "content")
    identifier = getattr(feature, "identifier", "")
    title = getattr(feature, "display_name", "") or getattr(feature, "title", "") or identifier
    summary = getattr(feature, "summary", "") or getattr(feature, "description", "")
    runtime_surface = "compiled" if host_type in RUNTIME_BEHAVIOR_HOSTS else "report_only" if host_type in REPORT_ONLY_BEHAVIOR_HOSTS else "report_only"
    return {
        "host_type": host_type,
        "identifier": identifier,
        "title": title,
        "summary": summary,
        "runtime_surface": runtime_surface,
        "behavior": behavior.to_dict() if hasattr(behavior, "to_dict") else {},
    }


def _event_triggers(event: dict[str, Any]) -> list[str]:
    triggers = []
    for trigger in [event.get("trigger"), *event.get("triggers", [])]:
        trigger_text = str(trigger or "").strip()
        if trigger_text and trigger_text not in triggers:
            triggers.append(trigger_text)
    return triggers


def _uses_state_fields(item: dict[str, Any]) -> bool:
    return any(item.get(key) is not None for key in ("state_key", "state_value", "state_delta"))


def _uses_resource_fields(item: dict[str, Any]) -> bool:
    return any(item.get(key) is not None for key in ("resource", "resource_amount"))
