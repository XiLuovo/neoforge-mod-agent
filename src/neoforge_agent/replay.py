from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

from .config import AppConfig
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class ReplayEvent:
    index: int
    kind: str
    title: str
    summary: str
    status: str = "recorded"
    role: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "kind": self.kind,
            "title": self.title,
            "summary": self.summary,
            "status": self.status,
            "role": self.role,
            "details": dict(self.details),
            "artifacts": dict(self.artifacts),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class AgentReplayResult:
    success: bool
    source_path: Path
    workspace: Path | None
    mode: str
    request: str
    planner_mode: str
    llm_provider: str
    replay_events: list[ReplayEvent]
    metrics: dict[str, Any]
    replay_report_json_path: Path
    replay_report_md_path: Path
    replay_report_html_path: Path
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "source_path": str(self.source_path),
            "workspace": str(self.workspace) if self.workspace else None,
            "mode": self.mode,
            "request": self.request,
            "planner_mode": self.planner_mode,
            "llm_provider": self.llm_provider,
            "replay_events": [event.to_dict() for event in self.replay_events],
            "events_count": len(self.replay_events),
            "metrics": dict(self.metrics),
            "replay_report_json_path": str(self.replay_report_json_path),
            "replay_report_md_path": str(self.replay_report_md_path),
            "replay_report_html_path": str(self.replay_report_html_path),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "warnings_count": len(self.warnings),
            "errors_count": len(self.errors),
        }


class AgentRunReplayer:
    """Create a deterministic replay report from a saved .agent/agent-run.json file."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def replay(self, target: str | Path) -> AgentReplayResult:
        source_path = self._resolve_agent_run_path(target)
        payload = self._load_agent_run(source_path)
        workspace = self._workspace_from_payload(payload, source_path)
        agent_dir = ensure_directory(source_path.parent)

        events = self._events(payload)
        metrics = self._metrics(payload, events)
        warnings = self._warnings(payload, events)
        errors = self._errors(payload, events)
        result = AgentReplayResult(
            success=True,
            source_path=source_path,
            workspace=workspace,
            mode=str(payload.get("mode", "")),
            request=str(payload.get("request", "")),
            planner_mode=str(payload.get("planner_mode", "")),
            llm_provider=str(payload.get("llm_provider", "")),
            replay_events=events,
            metrics=metrics,
            replay_report_json_path=agent_dir / "agent-run-replay.json",
            replay_report_md_path=agent_dir / "agent-run-replay.md",
            replay_report_html_path=agent_dir / "agent-run-replay.html",
            warnings=warnings,
            errors=errors,
        )
        write_json(result.replay_report_json_path, result.to_dict())
        write_text(result.replay_report_md_path, self._render_markdown(result))
        write_text(result.replay_report_html_path, self._render_html(result))
        return result

    def _resolve_agent_run_path(self, target: str | Path) -> Path:
        raw = Path(target)
        candidates: list[Path] = []
        if raw.exists():
            candidates.append(raw)
        if not raw.is_absolute():
            candidates.append(self.config.workspace_root / raw)

        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_file():
                return resolved
            if (resolved / ".agent" / "agent-run.json").exists():
                return (resolved / ".agent" / "agent-run.json").resolve()
            if (resolved / "agent-run.json").exists():
                return (resolved / "agent-run.json").resolve()

        raise FileNotFoundError(f"Agent run artifact not found for target: {target}")

    def _load_agent_run(self, source_path: Path) -> dict[str, Any]:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Agent run artifact must be a JSON object: {source_path}")
        required = {"success", "mode", "request", "steps"}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"Not an agent-run.json artifact, missing: {', '.join(missing)}")
        return payload

    def _workspace_from_payload(self, payload: dict[str, Any], source_path: Path) -> Path | None:
        workspace_value = payload.get("workspace")
        if workspace_value:
            return Path(str(workspace_value))
        if source_path.parent.name == ".agent":
            return source_path.parent.parent
        return None

    def _events(self, payload: dict[str, Any]) -> list[ReplayEvent]:
        events: list[ReplayEvent] = []

        def append(event: ReplayEvent) -> None:
            event.index = len(events) + 1
            events.append(event)

        append(
            ReplayEvent(
                index=0,
                kind="run_start",
                title="Run Started",
                summary="读取历史 agent-run.json，开始生成只读回放时间线。",
                status="pass" if payload.get("success") else "fail",
                details={
                    "mode": payload.get("mode", ""),
                    "planner_mode": payload.get("planner_mode", ""),
                    "llm_provider": payload.get("llm_provider", ""),
                    "workspace": payload.get("workspace", ""),
                },
            )
        )

        for step in payload.get("steps", []):
            if not isinstance(step, dict):
                continue
            append(
                ReplayEvent(
                    index=0,
                    kind="role_step",
                    title=str(step.get("role", "agent_step")),
                    summary=str(step.get("summary", "")),
                    status=str(step.get("status", "recorded")),
                    role=str(step.get("role", "")),
                    details=self._step_details(step),
                    warnings=[str(item) for item in step.get("warnings", [])],
                    errors=[str(item) for item in step.get("errors", [])],
                )
            )

        for decision in payload.get("decisions", []):
            if not isinstance(decision, dict):
                continue
            append(
                ReplayEvent(
                    index=0,
                    kind="decision",
                    title=str(decision.get("decision", "decision")),
                    summary=str(decision.get("rationale", "")),
                    status=str(decision.get("status", "recorded")),
                    role=str(decision.get("role", "")),
                    details={
                        "inputs": list(decision.get("inputs", [])),
                        "outputs": list(decision.get("outputs", [])),
                        "knowledge_ids": list(decision.get("knowledge_ids", [])),
                        "knowledge_refs_count": len(decision.get("knowledge_refs", []) or []),
                    },
                )
            )

        for trace in payload.get("prompt_traces", []):
            if not isinstance(trace, dict):
                continue
            provider_metadata = trace.get("provider_metadata") if isinstance(trace.get("provider_metadata"), dict) else {}
            completion_usage = trace.get("completion_usage") if isinstance(trace.get("completion_usage"), dict) else {}
            usage = completion_usage.get("usage") if isinstance(completion_usage.get("usage"), dict) else {}
            capabilities = provider_metadata.get("capabilities") if isinstance(provider_metadata.get("capabilities"), dict) else {}
            append(
                ReplayEvent(
                    index=0,
                    kind="prompt_trace",
                    title=f"{trace.get('role', 'planner')} {trace.get('prompt_kind', 'prompt')}",
                    summary="记录 planner 输入、provider、模型能力、token/cost telemetry、RAG 命中、JSON 修复和规范化输出摘要。",
                    status="fail" if trace.get("error") else "pass",
                    role=str(trace.get("role", "")),
                    details={
                        "planner_mode": trace.get("planner_mode", ""),
                        "provider": trace.get("provider", ""),
                        "prompt_kind": trace.get("prompt_kind", ""),
                        "input_text": trace.get("input_text", ""),
                        "model": provider_metadata.get("model") or completion_usage.get("model", ""),
                        "provider_capabilities": {
                            "json_mode": capabilities.get("supports_json_mode"),
                            "streaming": capabilities.get("supports_streaming"),
                            "streaming_mode": capabilities.get("streaming_mode", ""),
                        },
                        "llm_usage": usage,
                        "estimated_cost_usd": completion_usage.get("estimated_cost_usd"),
                        "completion_attempts_count": len(trace.get("completion_attempts", []) or []),
                        "rag_hits_count": len(trace.get("rag_hits", []) or []),
                        "used_knowledge_count": len(trace.get("used_knowledge", []) or []),
                        "parse_attempts_count": len(trace.get("parse_attempts", []) or []),
                        "retry_attempts": trace.get("retry_attempts", 0),
                        "json_repair_applied": bool(trace.get("json_repair_applied")),
                        "provider_metadata": provider_metadata,
                    },
                    warnings=[str(item) for item in trace.get("warnings", [])],
                    errors=[str(trace["error"])] if trace.get("error") else [],
                )
            )

        repair = self._repair_payload(payload)
        repair_rag = repair.get("repair_rag") if isinstance(repair.get("repair_rag"), dict) else {}
        if repair_rag:
            root_causes = repair.get("root_causes") if isinstance(repair.get("root_causes"), list) else []
            repair_plan = repair.get("repair_plan") if isinstance(repair.get("repair_plan"), list) else []
            hits = repair_rag.get("hits") if isinstance(repair_rag.get("hits"), list) else []
            repair_artifacts = {}
            if repair_rag.get("report_json_path"):
                repair_artifacts["repair_rag_context_json"] = str(repair_rag.get("report_json_path"))
            if repair_rag.get("report_md_path"):
                repair_artifacts["repair_rag_context_md"] = str(repair_rag.get("report_md_path"))
            append(
                ReplayEvent(
                    index=0,
                    kind="repair_rag",
                    title="Repair RAG Evidence",
                    summary="回放 repair agent 在失败上下文中检索到的本地 NeoForge 知识，用来解释为什么选择这些修复动作。",
                    status="pass" if repair_rag.get("success", True) else "fail",
                    role="repair_agent",
                    details={
                        "attempted": repair_rag.get("attempted"),
                        "query": repair_rag.get("query", ""),
                        "hits_count": int(repair_rag.get("hits_count", len(hits)) or 0),
                        "categories": repair_rag.get("categories", {}),
                        "capabilities": repair_rag.get("capabilities", {}),
                        "root_causes": [str(item) for item in root_causes],
                        "repair_actions": [
                            {
                                "id": str(action.get("id", "action")),
                                "summary": str(action.get("summary", "")),
                            }
                            for action in repair_plan
                            if isinstance(action, dict)
                        ],
                        "knowledge_ids": [str(hit.get("id", "")) for hit in hits if isinstance(hit, dict) and hit.get("id")],
                    },
                    artifacts=repair_artifacts,
                )
            )

        artifacts = self._artifact_paths(payload)
        if artifacts:
            append(
                ReplayEvent(
                    index=0,
                    kind="artifacts",
                    title="Replay Artifacts",
                    summary="汇总本次历史运行留下的关键 artifact 路径，方便复盘或调试时逐个打开。",
                    status="pass",
                    artifacts=artifacts,
                    details={"artifacts_count": len(artifacts)},
                )
            )
        return events

    def _step_details(self, step: dict[str, Any]) -> dict[str, Any]:
        details = step.get("details") if isinstance(step.get("details"), dict) else {}
        compact: dict[str, Any] = {}
        for key, value in details.items():
            if key == "spec" and isinstance(value, dict):
                compact["spec_features_count"] = len(value.get("features", [])) if isinstance(value.get("features"), list) else 0
                compact["mod_id"] = value.get("mod_id", "")
                continue
            if key == "generated_files" and isinstance(value, list):
                compact["generated_files_count"] = len(value)
                continue
            if key == "validation" and isinstance(value, dict):
                compact["validation_errors_count"] = len(value.get("errors", []) or [])
                compact["validation_warnings_count"] = len(value.get("warnings", []) or [])
                continue
            compact[key] = value
        return compact

    def _artifact_paths(self, payload: dict[str, Any]) -> dict[str, str]:
        artifacts: dict[str, str] = {}

        def visit(value: Any, prefix: str = "") -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    next_prefix = f"{prefix}.{key}" if prefix else str(key)
                    if isinstance(item, str) and self._looks_like_artifact_key(str(key)):
                        artifacts.setdefault(next_prefix, item)
                    else:
                        visit(item, next_prefix)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    visit(item, f"{prefix}[{index}]")

        visit(payload)
        return artifacts

    def _looks_like_artifact_key(self, key: str) -> bool:
        lowered = key.lower()
        return lowered.endswith("_path") or lowered.endswith("_json_path") or lowered.endswith("_md_path") or lowered.endswith("_html_path")

    def _metrics(self, payload: dict[str, Any], events: list[ReplayEvent]) -> dict[str, Any]:
        steps = [step for step in payload.get("steps", []) if isinstance(step, dict)]
        decisions = [decision for decision in payload.get("decisions", []) if isinstance(decision, dict)]
        traces = [trace for trace in payload.get("prompt_traces", []) if isinstance(trace, dict)]
        trace_usages = [self._trace_usage(trace) for trace in traces]
        estimated_costs = [
            float(trace.get("completion_usage", {}).get("estimated_cost_usd"))
            for trace in traces
            if isinstance(trace.get("completion_usage"), dict)
            and isinstance(trace.get("completion_usage", {}).get("estimated_cost_usd"), (int, float))
        ]
        provider_models = sorted(
            {
                str(metadata.get("model") or usage.get("model") or "")
                for trace in traces
                if isinstance(trace.get("provider_metadata"), dict) or isinstance(trace.get("completion_usage"), dict)
                for metadata in [trace.get("provider_metadata") if isinstance(trace.get("provider_metadata"), dict) else {}]
                for usage in [trace.get("completion_usage") if isinstance(trace.get("completion_usage"), dict) else {}]
                if str(metadata.get("model") or usage.get("model") or "").strip()
            }
        )
        repair_rag = self._repair_payload(payload).get("repair_rag")
        repair_rag = repair_rag if isinstance(repair_rag, dict) else {}
        return {
            "original_run_success": bool(payload.get("success")),
            "steps_count": len(steps),
            "passed_steps": sum(1 for step in steps if step.get("status") == "pass"),
            "failed_steps": sum(1 for step in steps if step.get("status") == "fail"),
            "skipped_steps": sum(1 for step in steps if step.get("status") == "skip"),
            "decisions_count": len(decisions),
            "decision_knowledge_refs_count": sum(len(decision.get("knowledge_refs", []) or []) for decision in decisions),
            "prompt_traces_count": len(traces),
            "rag_hits_count": sum(len(trace.get("rag_hits", []) or []) for trace in traces),
            "used_knowledge_count": sum(len(trace.get("used_knowledge", []) or []) for trace in traces),
            "repair_rag_events_count": sum(1 for event in events if event.kind == "repair_rag"),
            "repair_rag_hits_count": int(repair_rag.get("hits_count", 0) or 0),
            "json_repairs_count": sum(1 for trace in traces if trace.get("json_repair_applied")),
            "retry_attempts_count": sum(int(trace.get("retry_attempts", 0) or 0) for trace in traces),
            "llm_usage_events_count": sum(1 for usage in trace_usages if usage),
            "llm_input_tokens": sum(int(usage.get("input_tokens", 0) or 0) for usage in trace_usages),
            "llm_output_tokens": sum(int(usage.get("output_tokens", 0) or 0) for usage in trace_usages),
            "llm_total_tokens": sum(int(usage.get("total_tokens", 0) or 0) for usage in trace_usages),
            "llm_estimated_cost_usd": round(sum(estimated_costs), 8) if estimated_costs else None,
            "provider_models": provider_models,
            "artifacts_count": sum(1 for event in events for value in event.artifacts.values() if value),
            "events_count": len(events),
        }

    def _trace_usage(self, trace: dict[str, Any]) -> dict[str, Any]:
        completion_usage = trace.get("completion_usage")
        if not isinstance(completion_usage, dict):
            return {}
        usage = completion_usage.get("usage")
        return usage if isinstance(usage, dict) else {}

    def _warnings(self, payload: dict[str, Any], events: list[ReplayEvent]) -> list[str]:
        warnings = [warning for event in events for warning in event.warnings]
        payload_warnings = payload.get("warnings")
        if isinstance(payload_warnings, list):
            warnings.extend(str(item) for item in payload_warnings)
        return warnings

    def _errors(self, payload: dict[str, Any], events: list[ReplayEvent]) -> list[str]:
        errors = [error for event in events for error in event.errors]
        payload_errors = payload.get("errors")
        if isinstance(payload_errors, list):
            errors.extend(str(item) for item in payload_errors)
        return errors

    def _repair_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        nested = payload.get("payload") if isinstance(payload, dict) else {}
        repair = nested.get("repair") if isinstance(nested, dict) else {}
        return repair if isinstance(repair, dict) else {}

    def _render_markdown(self, result: AgentReplayResult) -> str:
        lines = [
            "# Agent Run Replay",
            "",
            f"成功: `{str(result.success).lower()}`",
            f"来源: `{result.source_path}`",
            f"workspace: `{result.workspace or ''}`",
            f"模式: `{result.mode}`",
            f"planner: `{result.planner_mode}`",
            f"LLM provider: `{result.llm_provider}`",
            f"HTML viewer: `{result.replay_report_html_path}`",
            "",
            "## 说明",
            "",
            "这份报告只读取历史 `.agent/agent-run.json` 和其中记录的 artifact 路径，不会重新调用 LLM，不会重新生成 Java / JSON / PNG，也不会执行 build。",
            "",
            "## 原始请求",
            "",
            "```text",
            result.request,
            "```",
            "",
            "## 指标",
            "",
        ]
        for key, value in result.metrics.items():
            lines.append(f"- `{key}`: {value}")
        lines.extend(["", "## 回放时间线", ""])
        for event in result.replay_events:
            lines.append(f"### {event.index}. {event.kind} - {event.title} `{event.status}`")
            lines.append("")
            if event.role:
                lines.append(f"- role: `{event.role}`")
            lines.append(event.summary)
            if event.details:
                lines.append("")
                lines.append("details:")
                for key, value in event.details.items():
                    lines.append(f"- `{key}`: {value}")
            if event.artifacts:
                lines.append("")
                lines.append("artifacts:")
                for key, value in event.artifacts.items():
                    lines.append(f"- `{key}`: `{value}`")
            if event.warnings:
                lines.append("")
                lines.append("warnings:")
                lines.extend(f"- {warning}" for warning in event.warnings)
            if event.errors:
                lines.append("")
                lines.append("errors:")
                lines.extend(f"- {error}" for error in event.errors)
            lines.append("")
        lines.extend(
            [
                "## 复盘讲法",
                "",
                "- 先讲 `planner_agent` 如何把自然语言约束为 ModSpec，而不是直接写代码。",
                "- 再讲 `reviewer_agent`、`executor_agent`、`auditor_agent` 和 `repair_agent` 的职责边界。",
                "- 最后用 artifacts 打开 prompt trace、audit report、repair plan 或 generated workspace，证明这不是黑箱输出。",
                "",
            ]
        )
        return "\n".join(lines)

    def _render_html(self, result: AgentReplayResult) -> str:
        raw_json = escape(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        metrics_html = "\n".join(
            self._render_metric_card(key, value)
            for key, value in result.metrics.items()
            if key
        )
        filters = self._render_filter_buttons(result)
        timeline_nav = "\n".join(self._render_timeline_link(event) for event in result.replay_events)
        event_cards = "\n".join(self._render_event_card(event) for event in result.replay_events)
        warning_block = self._render_notice_block("Warnings", result.warnings, "warning")
        error_block = self._render_notice_block("Errors", result.errors, "fail")
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Session Replay</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --panel-strong: #eef2f7;
      --text: #172033;
      --muted: #667085;
      --line: #d8dee8;
      --blue: #2563eb;
      --green: #16803c;
      --amber: #a16207;
      --red: #c2410c;
      --ink: #111827;
      --shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.55 "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }}
    .header-inner {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 28px 24px 22px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 30px;
      line-height: 1.15;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 0;
      font-size: 16px;
      letter-spacing: 0;
    }}
    .subtitle {{
      max-width: 900px;
      color: var(--muted);
      margin: 0;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 20px;
    }}
    .meta-item, .metric-card, .event-card, .notice, details.raw-json {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .meta-item {{
      padding: 12px;
      min-width: 0;
    }}
    .label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    .value {{
      display: block;
      margin-top: 4px;
      overflow-wrap: anywhere;
      font-weight: 650;
    }}
    main {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 22px 24px 40px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }}
    .metric-card {{
      padding: 12px;
      box-shadow: none;
    }}
    .metric-card strong {{
      display: block;
      margin-top: 5px;
      font-size: 17px;
      overflow-wrap: anywhere;
    }}
    .viewer-layout {{
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }}
    .side-panel {{
      position: sticky;
      top: 12px;
      display: grid;
      gap: 12px;
    }}
    .filter-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    button.filter {{
      border: 1px solid var(--line);
      background: #ffffff;
      color: var(--text);
      border-radius: 7px;
      padding: 7px 10px;
      cursor: pointer;
      font: inherit;
    }}
    button.filter.active {{
      border-color: var(--blue);
      color: var(--blue);
      background: #eff6ff;
    }}
    nav.timeline {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    nav.timeline a {{
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr);
      gap: 8px;
      color: var(--text);
      text-decoration: none;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
    }}
    nav.timeline a:last-child {{ border-bottom: 0; }}
    nav.timeline a:hover {{ background: var(--panel-strong); }}
    .event-list {{
      display: grid;
      gap: 14px;
    }}
    .event-card {{
      padding: 16px;
      box-shadow: none;
    }}
    .event-card.hidden {{ display: none; }}
    .event-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .event-title {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 650;
      border: 1px solid var(--line);
      background: var(--panel-strong);
      color: var(--muted);
    }}
    .status-pass {{ color: var(--green); background: #ecfdf3; border-color: #b7e4ca; }}
    .status-fail {{ color: var(--red); background: #fff1ec; border-color: #ffc6b5; }}
    .status-skip {{ color: var(--amber); background: #fffbeb; border-color: #fde68a; }}
    .status-recorded {{ color: var(--blue); background: #eff6ff; border-color: #bfdbfe; }}
    .summary {{
      margin: 0 0 12px;
      color: var(--ink);
      overflow-wrap: anywhere;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 10px;
    }}
    .detail-item {{
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 10px;
      background: #fbfcfe;
      min-width: 0;
    }}
    .detail-item.full {{ grid-column: 1 / -1; }}
    .detail-key {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      padding: 10px;
      border-radius: 7px;
      background: #111827;
      color: #e5e7eb;
      overflow: auto;
      max-height: 360px;
    }}
    code {{ font-family: Consolas, "Cascadia Mono", monospace; }}
    .artifact-list {{
      display: grid;
      gap: 7px;
      margin-top: 10px;
    }}
    .artifact {{
      display: grid;
      gap: 3px;
      padding: 9px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fbfcfe;
    }}
    .artifact a {{
      color: var(--blue);
      text-decoration: none;
      overflow-wrap: anywhere;
    }}
    .artifact a:hover {{ text-decoration: underline; }}
    .notice {{
      padding: 14px;
      margin-bottom: 14px;
      box-shadow: none;
    }}
    .notice ul {{ margin: 8px 0 0 20px; padding: 0; }}
    details.raw-json {{
      margin-top: 18px;
      padding: 14px;
      box-shadow: none;
    }}
    details.raw-json summary {{
      cursor: pointer;
      font-weight: 700;
    }}
    .empty {{
      color: var(--muted);
    }}
    @media (max-width: 980px) {{
      .meta-grid, .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .viewer-layout {{ grid-template-columns: 1fr; }}
      .side-panel {{ position: static; }}
    }}
    @media (max-width: 620px) {{
      .header-inner, main {{ padding-left: 14px; padding-right: 14px; }}
      .meta-grid, .metrics, .detail-grid {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 25px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <h1>Agent Session Replay</h1>
      <p class="subtitle">从历史 `.agent/agent-run.json` 生成的只读回放视图：角色时间线、决策链、LLM telemetry、RAG/repair 证据和 artifact 路径集中在一个页面里。</p>
      <div class="meta-grid">
        {self._render_meta_item("Run", "success" if result.success else "failed")}
        {self._render_meta_item("Mode", result.mode)}
        {self._render_meta_item("Planner", result.planner_mode)}
        {self._render_meta_item("Provider", result.llm_provider)}
        {self._render_meta_item("Source", str(result.source_path))}
        {self._render_meta_item("Workspace", str(result.workspace or ""))}
        {self._render_meta_item("Events", str(len(result.replay_events)))}
        {self._render_meta_item("Original Run", str(result.metrics.get("original_run_success")))}
      </div>
    </div>
  </header>
  <main>
    <section>
      <h2>Metrics</h2>
      <div class="metrics">
        {metrics_html}
      </div>
    </section>
    {warning_block}
    {error_block}
    <section class="viewer-layout">
      <aside class="side-panel">
        <section>
          <h2>Filters</h2>
          <div class="filter-row">
            {filters}
          </div>
        </section>
        <section>
          <h2>Timeline</h2>
          <nav class="timeline" aria-label="Replay timeline">
            {timeline_nav}
          </nav>
        </section>
      </aside>
      <section>
        <h2>Events</h2>
        <div class="event-list">
          {event_cards}
        </div>
      </section>
    </section>
    <details class="raw-json">
      <summary>Replay JSON</summary>
      <pre><code>{raw_json}</code></pre>
    </details>
  </main>
  <script>
    const buttons = document.querySelectorAll("[data-filter]");
    const cards = document.querySelectorAll(".event-card");
    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        const filter = button.getAttribute("data-filter");
        buttons.forEach((item) => item.classList.toggle("active", item === button));
        cards.forEach((card) => {{
          const match = filter === "all" || card.getAttribute("data-kind") === filter || card.getAttribute("data-status") === filter;
          card.classList.toggle("hidden", !match);
        }});
      }});
    }});
  </script>
</body>
</html>
"""

    def _render_metric_card(self, key: str, value: Any) -> str:
        return (
            '<div class="metric-card">'
            f'<span class="label">{escape(str(key))}</span>'
            f"<strong>{escape(self._format_scalar(value))}</strong>"
            "</div>"
        )

    def _render_meta_item(self, label: str, value: str) -> str:
        return (
            '<div class="meta-item">'
            f'<span class="label">{escape(label)}</span>'
            f'<span class="value">{escape(value)}</span>'
            "</div>"
        )

    def _render_filter_buttons(self, result: AgentReplayResult) -> str:
        filters = ["all"]
        filters.extend(sorted({event.kind for event in result.replay_events}))
        filters.extend(status for status in ("pass", "fail", "skip") if any(event.status == status for event in result.replay_events))
        return "\n".join(
            f'<button type="button" class="filter{" active" if item == "all" else ""}" data-filter="{escape(item)}">{escape(item)}</button>'
            for item in filters
        )

    def _render_timeline_link(self, event: ReplayEvent) -> str:
        status_class = self._status_class(event.status)
        return (
            f'<a href="#event-{event.index}">'
            f'<span class="badge {status_class}">{event.index}</span>'
            f'<span><strong>{escape(event.kind)}</strong><br><span class="empty">{escape(self._truncate(event.title, 46))}</span></span>'
            "</a>"
        )

    def _render_event_card(self, event: ReplayEvent) -> str:
        status_class = self._status_class(event.status)
        details_html = self._render_details(event.details)
        artifacts_html = self._render_artifacts(event.artifacts)
        warnings_html = self._render_notice_block("Warnings", event.warnings, "warning")
        errors_html = self._render_notice_block("Errors", event.errors, "fail")
        return f"""<article class="event-card" id="event-{event.index}" data-kind="{escape(event.kind)}" data-status="{escape(event.status)}">
  <div class="event-head">
    <div>
      <div class="event-title">
        <span class="badge">{event.index}</span>
        <h3>{escape(event.title)}</h3>
      </div>
      <div class="empty">{escape(event.kind)}{(" · " + escape(event.role)) if event.role else ""}</div>
    </div>
    <span class="badge {status_class}">{escape(event.status)}</span>
  </div>
  <p class="summary">{escape(event.summary)}</p>
  {details_html}
  {artifacts_html}
  {warnings_html}
  {errors_html}
</article>"""

    def _render_details(self, details: dict[str, Any]) -> str:
        if not details:
            return ""
        items: list[str] = []
        for key, value in details.items():
            is_full = isinstance(value, (dict, list)) or len(self._format_scalar(value)) > 90
            css_class = "detail-item full" if is_full else "detail-item"
            items.append(
                f'<div class="{css_class}">'
                f'<div class="detail-key">{escape(str(key))}</div>'
                f"{self._render_value(value)}"
                "</div>"
            )
        return '<div class="detail-grid">' + "\n".join(items) + "</div>"

    def _render_artifacts(self, artifacts: dict[str, str]) -> str:
        if not artifacts:
            return ""
        items: list[str] = []
        for key, value in artifacts.items():
            if not value:
                continue
            href = self._artifact_href(value)
            rendered_value = escape(value)
            if href:
                rendered_path = f'<a href="{escape(href)}">{rendered_value}</a>'
            else:
                rendered_path = f'<span>{rendered_value}</span>'
            items.append(
                '<div class="artifact">'
                f'<span class="label">{escape(key)}</span>'
                f"{rendered_path}"
                "</div>"
            )
        if not items:
            return ""
        return '<div class="artifact-list">' + "\n".join(items) + "</div>"

    def _render_notice_block(self, title: str, items: list[str], status: str) -> str:
        if not items:
            return ""
        status_class = self._status_class(status)
        body = "\n".join(f"<li>{escape(item)}</li>" for item in items)
        return f'<section class="notice"><span class="badge {status_class}">{escape(title)}</span><ul>{body}</ul></section>'

    def _render_value(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            payload = json.dumps(value, ensure_ascii=False, indent=2)
            return f"<pre><code>{escape(payload)}</code></pre>"
        return f'<span class="value">{escape(self._format_scalar(value))}</span>'

    def _format_scalar(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return str(value).lower()
        return str(value)

    def _artifact_href(self, value: str) -> str:
        if not value:
            return ""
        try:
            path = Path(value)
            if path.is_absolute():
                return path.as_uri()
        except (OSError, ValueError):
            return ""
        return ""

    def _status_class(self, status: str) -> str:
        normalized = status if status in {"pass", "fail", "skip", "recorded"} else "recorded"
        return f"status-{normalized}"

    def _truncate(self, value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: max(0, limit - 3)] + "..."
