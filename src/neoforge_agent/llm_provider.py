from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class LLMModelCapabilities:
    supports_json_mode: bool
    supports_streaming: bool
    supports_system_prompt: bool = True
    supports_tool_calling: bool = False
    max_context_tokens: int | None = None
    max_output_tokens: int | None = None
    modalities: list[str] = field(default_factory=lambda: ["text"])
    streaming_mode: str = "none"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "supports_json_mode": self.supports_json_mode,
            "supports_streaming": self.supports_streaming,
            "supports_system_prompt": self.supports_system_prompt,
            "supports_tool_calling": self.supports_tool_calling,
            "max_context_tokens": self.max_context_tokens,
            "max_output_tokens": self.max_output_tokens,
            "modalities": list(self.modalities),
            "streaming_mode": self.streaming_mode,
            "notes": list(self.notes),
        }


@dataclass(slots=True)
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int | None = None
    source: str = "estimated"

    def resolved_total_tokens(self) -> int:
        if self.total_tokens is not None:
            return self.total_tokens
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.resolved_total_tokens(),
            "source": self.source,
        }


@dataclass(slots=True)
class LLMPricing:
    input_cost_per_1m_tokens: float | None = None
    output_cost_per_1m_tokens: float | None = None
    currency: str = "USD"

    def estimate_cost_usd(self, usage: LLMUsage | None) -> float | None:
        if usage is None:
            return None
        if self.input_cost_per_1m_tokens is None or self.output_cost_per_1m_tokens is None:
            return None
        cost = (
            usage.input_tokens * self.input_cost_per_1m_tokens
            + usage.output_tokens * self.output_cost_per_1m_tokens
        ) / 1_000_000
        return round(cost, 8)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_cost_per_1m_tokens": self.input_cost_per_1m_tokens,
            "output_cost_per_1m_tokens": self.output_cost_per_1m_tokens,
            "currency": self.currency,
        }


@dataclass(slots=True)
class LLMRequestOptions:
    temperature: float = 0.0
    response_format: str = "json_object"
    stream: bool = False
    timeout_seconds: int | None = None
    max_retries: int | None = None
    max_output_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature": self.temperature,
            "response_format": self.response_format,
            "stream": self.stream,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "max_output_tokens": self.max_output_tokens,
        }


@dataclass(slots=True)
class LLMProviderMetadata:
    provider: str
    model: str
    display_name: str
    capabilities: LLMModelCapabilities
    pricing: LLMPricing = field(default_factory=LLMPricing)
    default_options: LLMRequestOptions = field(default_factory=LLMRequestOptions)
    retry_policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "display_name": self.display_name,
            "capabilities": self.capabilities.to_dict(),
            "pricing": self.pricing.to_dict(),
            "default_options": self.default_options.to_dict(),
            "retry_policy": dict(self.retry_policy),
        }


@dataclass(slots=True)
class LLMStreamEvent:
    event: str
    provider: str
    model: str = ""
    text_delta: str = ""
    raw_text: str = ""
    parsed_json: dict[str, Any] | None = None
    usage: LLMUsage | None = None
    estimated_cost_usd: float | None = None
    latency_ms: int | None = None
    request_id: str | None = None
    finish_reason: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "provider": self.provider,
            "model": self.model,
            "text_delta": self.text_delta,
            "raw_text": self.raw_text,
            "parsed_json": self.parsed_json,
            "usage": self.usage.to_dict() if self.usage else None,
            "estimated_cost_usd": self.estimated_cost_usd,
            "latency_ms": self.latency_ms,
            "request_id": self.request_id,
            "finish_reason": self.finish_reason,
            "error": self.error,
        }


MetadataFactory = Callable[[str], LLMProviderMetadata]


class LLMProviderRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, MetadataFactory] = {}

    def register(self, provider: str, factory: MetadataFactory) -> None:
        self._factories[provider.lower()] = factory

    def metadata(self, provider: str, model: str = "") -> LLMProviderMetadata:
        normalized = provider.lower()
        if normalized not in self._factories:
            return unsupported_provider_metadata(normalized, model=model)
        return self._factories[normalized](model)

    def providers(self) -> list[str]:
        return sorted(self._factories)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def estimate_llm_usage(system_prompt: str, user_prompt: str, raw_text: str) -> LLMUsage:
    return LLMUsage(
        input_tokens=estimate_tokens(system_prompt) + estimate_tokens(user_prompt),
        output_tokens=estimate_tokens(raw_text),
        source="estimated",
    )


def mock_provider_metadata(model: str = "mock") -> LLMProviderMetadata:
    return LLMProviderMetadata(
        provider="mock",
        model=model or "mock",
        display_name="Mock LLM",
        capabilities=LLMModelCapabilities(
            supports_json_mode=True,
            supports_streaming=True,
            supports_tool_calling=False,
            max_context_tokens=128_000,
            modalities=["text"],
            streaming_mode="synthetic",
            notes=["Offline deterministic provider for tests and demos."],
        ),
        pricing=LLMPricing(input_cost_per_1m_tokens=0.0, output_cost_per_1m_tokens=0.0),
        default_options=LLMRequestOptions(stream=True, timeout_seconds=0, max_retries=0),
        retry_policy={"max_retries": 0, "backoff": "none"},
    )


def openai_compatible_provider_metadata(
    model: str = "",
    *,
    pricing: LLMPricing | None = None,
    timeout_seconds: int | None = None,
    max_retries: int | None = None,
    response_format: str = "json_object",
) -> LLMProviderMetadata:
    return LLMProviderMetadata(
        provider="openai-compatible",
        model=model,
        display_name="OpenAI-Compatible Chat Completions",
        capabilities=LLMModelCapabilities(
            supports_json_mode=True,
            supports_streaming=True,
            supports_tool_calling=False,
            max_context_tokens=None,
            modalities=["text"],
            streaming_mode="completion_event_fallback",
            notes=["Native SSE streaming is abstracted as provider events after full completion."],
        ),
        pricing=pricing or LLMPricing(),
        default_options=LLMRequestOptions(
            response_format=response_format,
            stream=True,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        ),
        retry_policy={
            "max_retries": max_retries,
            "retryable_errors": ["HTTP 429", "HTTP 5xx", "timeout", "url_error", "decode_error"],
            "backoff": "exponential_capped_250ms_to_2s",
        },
    )


def unsupported_provider_metadata(provider: str, *, model: str = "") -> LLMProviderMetadata:
    return LLMProviderMetadata(
        provider=provider,
        model=model,
        display_name=f"Unsupported provider: {provider}",
        capabilities=LLMModelCapabilities(
            supports_json_mode=False,
            supports_streaming=False,
            supports_system_prompt=False,
            notes=["Provider is not registered."],
        ),
    )


DEFAULT_LLM_PROVIDER_REGISTRY = LLMProviderRegistry()
DEFAULT_LLM_PROVIDER_REGISTRY.register("mock", mock_provider_metadata)
DEFAULT_LLM_PROVIDER_REGISTRY.register("openai-compatible", lambda model: openai_compatible_provider_metadata(model))
