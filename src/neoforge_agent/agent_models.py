from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _serialize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


@dataclass(slots=True)
class AgentStep:
    role: str
    status: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "status": self.status,
            "summary": self.summary,
            "details": _serialize(self.details),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class AgentDecision:
    role: str
    decision: str
    rationale: str
    status: str = "recorded"
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    knowledge_refs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def knowledge_ids(self) -> list[str]:
        ids: list[str] = []
        seen: set[str] = set()
        for item in self.knowledge_refs:
            identifier = str(item.get("id", "")).strip()
            if not identifier or identifier in seen:
                continue
            seen.add(identifier)
            ids.append(identifier)
        return ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "decision": self.decision,
            "rationale": self.rationale,
            "status": self.status,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "knowledge_ids": self.knowledge_ids,
            "knowledge_refs": _serialize(self.knowledge_refs),
        }


@dataclass(slots=True)
class AgentPromptTrace:
    role: str
    planner_mode: str
    provider: str
    prompt_kind: str
    input_text: str
    system_prompt: str = ""
    raw_text: str = ""
    raw_json: dict[str, Any] | None = None
    normalized_json: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    rag_query: str = ""
    rag_query_expansions: list[str] = field(default_factory=list)
    rag_hits: list[dict[str, Any]] = field(default_factory=list)
    rag_categories: dict[str, int] = field(default_factory=dict)
    rag_capabilities: dict[str, int] = field(default_factory=dict)
    used_knowledge: list[dict[str, Any]] = field(default_factory=list)
    rag_quality: dict[str, Any] = field(default_factory=dict)
    parse_attempts: list[dict[str, Any]] = field(default_factory=list)
    retry_attempts: int = 0
    schema_retry_attempts: int = 0
    schema_validation_attempts: list[dict[str, Any]] = field(default_factory=list)
    json_repair_applied: bool = False
    provider_config: dict[str, Any] = field(default_factory=dict)
    provider_health: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    completion_usage: dict[str, Any] = field(default_factory=dict)
    completion_attempts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "planner_mode": self.planner_mode,
            "provider": self.provider,
            "prompt_kind": self.prompt_kind,
            "system_prompt": self.system_prompt,
            "input_text": self.input_text,
            "raw_text": self.raw_text,
            "raw_json": _serialize(self.raw_json),
            "normalized_json": _serialize(self.normalized_json),
            "warnings": list(self.warnings),
            "error": self.error,
            "rag_query": self.rag_query,
            "rag_query_expansions": list(self.rag_query_expansions),
            "rag_hits": _serialize(self.rag_hits),
            "rag_categories": dict(self.rag_categories),
            "rag_capabilities": dict(self.rag_capabilities),
            "used_knowledge": _serialize(self.used_knowledge),
            "rag_quality": _serialize(self.rag_quality),
            "parse_attempts": _serialize(self.parse_attempts),
            "retry_attempts": self.retry_attempts,
            "schema_retry_attempts": self.schema_retry_attempts,
            "schema_validation_attempts": _serialize(self.schema_validation_attempts),
            "json_repair_applied": self.json_repair_applied,
            "provider_config": _serialize(self.provider_config),
            "provider_health": _serialize(self.provider_health),
            "provider_metadata": _serialize(self.provider_metadata),
            "completion_usage": _serialize(self.completion_usage),
            "completion_attempts": _serialize(self.completion_attempts),
        }


@dataclass(slots=True)
class AgentRunResult:
    success: bool
    mode: str
    request: str
    planner_mode: str
    llm_provider: str
    workspace: Path | None = None
    steps: list[AgentStep] = field(default_factory=list)
    decisions: list[AgentDecision] = field(default_factory=list)
    prompt_traces: list[AgentPromptTrace] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    agent_run_json_path: Path | None = None
    agent_run_md_path: Path | None = None
    agent_decisions_md_path: Path | None = None
    prompt_trace_json_path: Path | None = None
    agent_trace_summary_json_path: Path | None = None
    agent_trace_summary_md_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "mode": self.mode,
            "request": self.request,
            "planner_mode": self.planner_mode,
            "llm_provider": self.llm_provider,
            "workspace": _serialize(self.workspace),
            "steps": [step.to_dict() for step in self.steps],
            "decisions": [decision.to_dict() for decision in self.decisions],
            "prompt_traces": [trace.to_dict() for trace in self.prompt_traces],
            "payload": _serialize(self.payload),
            "agent_run_json_path": _serialize(self.agent_run_json_path),
            "agent_run_md_path": _serialize(self.agent_run_md_path),
            "agent_decisions_md_path": _serialize(self.agent_decisions_md_path),
            "prompt_trace_json_path": _serialize(self.prompt_trace_json_path),
            "agent_trace_summary_json_path": _serialize(self.agent_trace_summary_json_path),
            "agent_trace_summary_md_path": _serialize(self.agent_trace_summary_md_path),
        }
