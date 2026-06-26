from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class LLMEngineeringReportResult:
    success: bool
    run_id: str
    version: str
    target: str
    source_agent_dir: Path
    workspace: Path | None
    artifacts: dict[str, str]
    metrics: dict[str, Any]
    prompt_records: list[dict[str, Any]]
    provider_records: list[dict[str, Any]]
    usage_summary: dict[str, Any]
    reliability_summary: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    report_dir: Path | None = None
    llm_engineering_report_json_path: Path | None = None
    llm_engineering_report_md_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "version": self.version,
            "target": self.target,
            "source_agent_dir": str(self.source_agent_dir),
            "workspace": str(self.workspace) if self.workspace else None,
            "artifacts": dict(self.artifacts),
            "metrics": dict(self.metrics),
            "prompt_records": list(self.prompt_records),
            "provider_records": list(self.provider_records),
            "usage_summary": dict(self.usage_summary),
            "reliability_summary": dict(self.reliability_summary),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "warnings_count": len(self.warnings),
            "errors_count": len(self.errors),
            "report_dir": str(self.report_dir) if self.report_dir else None,
            "llm_engineering_report_json_path": str(self.llm_engineering_report_json_path)
            if self.llm_engineering_report_json_path
            else None,
            "llm_engineering_report_md_path": str(self.llm_engineering_report_md_path)
            if self.llm_engineering_report_md_path
            else None,
        }


class LLMEngineeringReportRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(self, target: str | Path, *, run_name: str | None = None) -> LLMEngineeringReportResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        agent_dir = self._resolve_agent_dir(target)
        workspace = agent_dir.parent if agent_dir.name == ".agent" else None
        artifacts = self._artifact_paths(agent_dir)
        warnings: list[str] = []
        errors: list[str] = []

        agent_run = self._load_json_optional(agent_dir / "agent-run.json", warnings, "agent-run.json")
        prompt_traces = self._load_prompt_traces(agent_dir, agent_run, warnings)
        stability = self._load_json_optional(agent_dir / "llm-stability.json", warnings, "llm-stability.json")

        prompt_records = self._prompt_records(prompt_traces)
        provider_records = self._provider_records(prompt_traces, stability)
        usage_summary = self._usage_summary(prompt_traces, stability)
        reliability_summary = self._reliability_summary(prompt_traces, stability, agent_run)
        metrics = {
            "prompt_traces_count": len(prompt_traces),
            "provider_records_count": len(provider_records),
            "providers": sorted({str(record.get("provider", "")) for record in provider_records if record.get("provider")}),
            "models": sorted({str(record.get("model", "")) for record in provider_records if record.get("model")}),
            "prompt_kinds": sorted({str(record.get("prompt_kind", "")) for record in prompt_records if record.get("prompt_kind")}),
            "prompt_versions": sorted({str(record.get("prompt_version", "")) for record in prompt_records if record.get("prompt_version")}),
            "json_repair_applied_count": reliability_summary["json_repair_applied_count"],
            "retry_attempts_total": reliability_summary["retry_attempts_total"],
            "schema_retry_attempts_total": reliability_summary["schema_retry_attempts_total"],
            "fallback_detected": reliability_summary["fallback_detected"],
            "usage_events_count": usage_summary["usage_events_count"],
            "estimated_cost_usd": usage_summary["estimated_cost_usd"],
        }
        success = bool(prompt_traces or stability)
        if not success:
            errors.append("No prompt-trace.json, agent-run prompt traces, or llm-stability.json artifacts were found.")

        report_dir = ensure_directory(self.config.workspace_root / "llm-engineering-runs" / run_id / ".agent")
        report_json = report_dir / "llm-engineering-report.json"
        report_md = report_dir / "llm-engineering-report.md"
        result = LLMEngineeringReportResult(
            success=success,
            run_id=run_id,
            version=self._project_version(),
            target=str(target),
            source_agent_dir=agent_dir,
            workspace=workspace,
            artifacts=artifacts,
            metrics=metrics,
            prompt_records=prompt_records,
            provider_records=provider_records,
            usage_summary=usage_summary,
            reliability_summary=reliability_summary,
            warnings=warnings,
            errors=errors,
            report_dir=report_dir,
            llm_engineering_report_json_path=report_json,
            llm_engineering_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_markdown(result))
        return result

    def _project_version(self) -> str:
        pyproject_path = self.config.project_root / "pyproject.toml"
        if not pyproject_path.exists():
            return "unknown"
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version", "unknown"))

    def _resolve_agent_dir(self, target: str | Path) -> Path:
        raw = Path(target)
        candidates: list[Path] = []
        if raw.exists():
            candidates.append(raw)
        if not raw.is_absolute():
            candidates.append(self.config.workspace_root / raw)

        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_file():
                if resolved.parent.name == ".agent":
                    return resolved.parent
                if resolved.name in {"agent-run.json", "prompt-trace.json", "llm-stability.json"}:
                    return resolved.parent
            if resolved.is_dir():
                if resolved.name == ".agent":
                    return resolved
                if (resolved / ".agent").exists():
                    return (resolved / ".agent").resolve()
                if any((resolved / name).exists() for name in ("agent-run.json", "prompt-trace.json", "llm-stability.json")):
                    return resolved

        raise FileNotFoundError(f"LLM engineering artifacts not found for target: {target}")

    def _artifact_paths(self, agent_dir: Path) -> dict[str, str]:
        names = {
            "agent_run": "agent-run.json",
            "prompt_trace": "prompt-trace.json",
            "llm_stability": "llm-stability.json",
            "planner_system_prompt": "planner-system-prompt.txt",
            "llm_plan_raw": "llm-plan-raw.json",
            "llm_plan_normalized": "llm-plan-normalized.json",
        }
        return {key: str(agent_dir / name) for key, name in names.items() if (agent_dir / name).exists()}

    def _load_json_optional(self, path: Path, warnings: list[str], label: str) -> Any:
        if not path.exists():
            warnings.append(f"Missing optional artifact: {label}")
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data

    def _load_prompt_traces(self, agent_dir: Path, agent_run: Any, warnings: list[str]) -> list[dict[str, Any]]:
        prompt_trace_path = agent_dir / "prompt-trace.json"
        if prompt_trace_path.exists():
            data = json.loads(prompt_trace_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [dict(item) for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                return [data]
            warnings.append("prompt-trace.json exists but is not a JSON object or list.")
        if isinstance(agent_run, dict):
            traces = agent_run.get("prompt_traces")
            if isinstance(traces, list):
                return [dict(item) for item in traces if isinstance(item, dict)]
        warnings.append("No prompt traces found; falling back to llm-stability.json only.")
        return []

    def _prompt_records(self, traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for index, trace in enumerate(traces, start=1):
            metadata = _dict(trace.get("provider_metadata"))
            default_options = _dict(metadata.get("default_options"))
            usage = _dict(_dict(trace.get("completion_usage")).get("usage"))
            system_prompt = str(trace.get("system_prompt", ""))
            input_text = str(trace.get("input_text", ""))
            raw_text = str(trace.get("raw_text", ""))
            prompt_version = (
                trace.get("prompt_version")
                or metadata.get("prompt_version")
                or _dict(trace.get("prompt_metadata")).get("version")
                or f"sha256:{_sha256_prefix(system_prompt)}"
            )
            records.append(
                {
                    "index": index,
                    "role": str(trace.get("role", "")),
                    "planner_mode": str(trace.get("planner_mode", "")),
                    "provider": str(trace.get("provider", "")),
                    "prompt_kind": str(trace.get("prompt_kind", "")),
                    "prompt_version": prompt_version,
                    "system_prompt_hash": _sha256_prefix(system_prompt),
                    "input_text_hash": _sha256_prefix(input_text),
                    "model": str(metadata.get("model") or _dict(trace.get("completion_usage")).get("model", "")),
                    "response_format": default_options.get("response_format"),
                    "temperature": default_options.get("temperature"),
                    "stream": default_options.get("stream"),
                    "timeout_seconds": default_options.get("timeout_seconds"),
                    "max_retries": default_options.get("max_retries"),
                    "system_prompt_chars": len(system_prompt),
                    "input_text_chars": len(input_text),
                    "raw_text_chars": len(raw_text),
                    "normalized_json_present": isinstance(trace.get("normalized_json"), dict),
                    "usage": usage,
                    "estimated_cost_usd": _dict(trace.get("completion_usage")).get("estimated_cost_usd"),
                    "warnings_count": len(trace.get("warnings", []) or []),
                    "error": trace.get("error"),
                }
            )
        return records

    def _provider_records(self, traces: list[dict[str, Any]], stability: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(provider: str, metadata: dict[str, Any], config: dict[str, Any], health: dict[str, Any]) -> None:
            model = str(metadata.get("model") or config.get("model", ""))
            key = (provider, model)
            if key in seen:
                return
            seen.add(key)
            default_options = _dict(metadata.get("default_options"))
            records.append(
                {
                    "provider": provider,
                    "model": model,
                    "display_name": metadata.get("display_name", ""),
                    "capabilities": _dict(metadata.get("capabilities")),
                    "default_options": default_options,
                    "retry_policy": _dict(metadata.get("retry_policy")),
                    "pricing": _dict(metadata.get("pricing")),
                    "config": config,
                    "health": health,
                }
            )

        for trace in traces:
            provider = str(trace.get("provider", ""))
            metadata = _dict(trace.get("provider_metadata"))
            config = _dict(trace.get("provider_config"))
            health = _dict(trace.get("provider_health"))
            if provider or metadata or config or health:
                add(provider or str(metadata.get("provider", "")), metadata, config, health)

        if isinstance(stability, dict):
            add(
                str(stability.get("provider", "")),
                _dict(stability.get("provider_metadata")),
                _dict(stability.get("provider_config")),
                _dict(stability.get("provider_health")),
            )

        return records

    def _usage_summary(self, traces: list[dict[str, Any]], stability: Any) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        for trace in traces:
            completion = _dict(trace.get("completion_usage"))
            usage = _dict(completion.get("usage"))
            if usage:
                records.append({"source": "prompt_trace", "completion_usage": completion, "usage": usage})
        if not records and isinstance(stability, dict):
            completion = _dict(stability.get("completion_usage"))
            usage = _dict(completion.get("usage"))
            if usage:
                records.append({"source": "llm_stability", "completion_usage": completion, "usage": usage})

        estimated_costs = [
            float(item["completion_usage"].get("estimated_cost_usd"))
            for item in records
            if isinstance(item["completion_usage"].get("estimated_cost_usd"), (int, float))
        ]
        return {
            "usage_events_count": len(records),
            "input_tokens": sum(int(item["usage"].get("input_tokens", 0) or 0) for item in records),
            "output_tokens": sum(int(item["usage"].get("output_tokens", 0) or 0) for item in records),
            "total_tokens": sum(int(item["usage"].get("total_tokens", 0) or 0) for item in records),
            "estimated_cost_usd": round(sum(estimated_costs), 8) if estimated_costs else None,
            "records": records,
        }

    def _reliability_summary(self, traces: list[dict[str, Any]], stability: Any, agent_run: Any) -> dict[str, Any]:
        sources = traces if traces else ([stability] if isinstance(stability, dict) else [])
        retry_attempts = sum(int(_dict(item).get("retry_attempts", 0) or 0) for item in sources)
        schema_retry_attempts = sum(int(_dict(item).get("schema_retry_attempts", 0) or 0) for item in sources)
        parse_attempts = sum(len(_dict(item).get("parse_attempts", []) or []) for item in sources)
        schema_validation_attempts = sum(len(_dict(item).get("schema_validation_attempts", []) or []) for item in sources)
        json_repair_count = sum(1 for item in sources if bool(_dict(item).get("json_repair_applied")))
        warnings = _warning_texts(traces, stability, agent_run)
        fallback_recommended = any(
            bool(_dict(_dict(item).get("provider_health")).get("fallback_recommended"))
            for item in sources
            if isinstance(item, dict)
        )
        fallback_detected = fallback_recommended or any("fallback" in item.lower() or "fall back" in item.lower() for item in warnings)
        return {
            "retry_attempts_total": retry_attempts,
            "schema_retry_attempts_total": schema_retry_attempts,
            "parse_attempts_count": parse_attempts,
            "schema_validation_attempts_count": schema_validation_attempts,
            "json_repair_applied_count": json_repair_count,
            "fallback_recommended": fallback_recommended,
            "fallback_detected": fallback_detected,
            "warning_samples": warnings[:10],
        }

    def _render_markdown(self, result: LLMEngineeringReportResult) -> str:
        lines = [
            "# LLM Engineering Report",
            "",
            f"- success: `{result.success}`",
            f"- run id: `{result.run_id}`",
            f"- project version: `{result.version}`",
            f"- target: `{result.target}`",
            f"- source agent dir: `{result.source_agent_dir}`",
            f"- prompt traces: `{result.metrics.get('prompt_traces_count')}`",
            f"- providers: `{', '.join(result.metrics.get('providers', [])) or 'none'}`",
            f"- models: `{', '.join(result.metrics.get('models', [])) or 'none'}`",
            f"- usage events: `{result.usage_summary.get('usage_events_count')}`",
            f"- estimated cost USD: `{result.usage_summary.get('estimated_cost_usd')}`",
            "",
            "## Prompt And Provider",
            "",
        ]
        if result.prompt_records:
            for record in result.prompt_records:
                lines.extend(
                    [
                        f"- trace {record['index']}: `{record.get('role')}` / `{record.get('prompt_kind')}`",
                        f"  - prompt version: `{record.get('prompt_version')}`",
                        f"  - system prompt hash: `{record.get('system_prompt_hash')}`",
                        f"  - provider/model: `{record.get('provider')}` / `{record.get('model')}`",
                        f"  - response format: `{record.get('response_format')}`",
                        f"  - temperature: `{record.get('temperature')}`",
                        f"  - timeout/retry: `{record.get('timeout_seconds')}` / `{record.get('max_retries')}`",
                        f"  - system/input/raw chars: `{record.get('system_prompt_chars')}` / `{record.get('input_text_chars')}` / `{record.get('raw_text_chars')}`",
                    ]
                )
        else:
            lines.append("- No prompt trace records were found.")
        lines.extend(
            [
                "",
                "## Reliability",
                "",
                f"- retry attempts: `{result.reliability_summary.get('retry_attempts_total')}`",
                f"- schema retry attempts: `{result.reliability_summary.get('schema_retry_attempts_total')}`",
                f"- parse attempts: `{result.reliability_summary.get('parse_attempts_count')}`",
                f"- schema validation attempts: `{result.reliability_summary.get('schema_validation_attempts_count')}`",
                f"- JSON repair applied count: `{result.reliability_summary.get('json_repair_applied_count')}`",
                f"- fallback detected: `{result.reliability_summary.get('fallback_detected')}`",
                "",
                "## Usage",
                "",
                f"- input tokens: `{result.usage_summary.get('input_tokens')}`",
                f"- output tokens: `{result.usage_summary.get('output_tokens')}`",
                f"- total tokens: `{result.usage_summary.get('total_tokens')}`",
                f"- estimated cost USD: `{result.usage_summary.get('estimated_cost_usd')}`",
                "",
                "## Artifacts",
                "",
            ]
        )
        lines.extend(f"- `{key}`: `{value}`" for key, value in result.artifacts.items())
        if result.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in result.warnings)
        if result.errors:
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- {error}" for error in result.errors)
        lines.append("")
        return "\n".join(lines)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sha256_prefix(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _warning_texts(traces: list[dict[str, Any]], stability: Any, agent_run: Any) -> list[str]:
    warnings: list[str] = []
    for trace in traces:
        warnings.extend(str(item) for item in trace.get("warnings", []) or [])
        health = _dict(trace.get("provider_health"))
        warnings.extend(str(item) for item in health.get("warnings", []) or [])
        warnings.extend(str(item) for item in health.get("errors", []) or [])
    if isinstance(stability, dict):
        health = _dict(stability.get("provider_health"))
        warnings.extend(str(item) for item in health.get("warnings", []) or [])
        warnings.extend(str(item) for item in health.get("errors", []) or [])
    if isinstance(agent_run, dict):
        for step in agent_run.get("steps", []) or []:
            if isinstance(step, dict):
                warnings.extend(str(item) for item in step.get("warnings", []) or [])
        warnings.extend(str(item) for item in agent_run.get("warnings", []) or [])
    return [item for item in warnings if item]
