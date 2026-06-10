from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib import error, request

from .llm_provider import (
    LLMPricing,
    LLMProviderMetadata,
    LLMRequestOptions,
    LLMStreamEvent,
    LLMUsage,
    estimate_llm_usage,
    mock_provider_metadata,
    openai_compatible_provider_metadata,
    unsupported_provider_metadata,
)


DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_TIMEOUT_SECONDS = 60
DEFAULT_LLM_MAX_RETRIES = 2
DEFAULT_LLM_SCHEMA_RETRIES = 1
DEFAULT_LLM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36"
DOTENV_FILENAMES = (".env.local", ".env")


@dataclass(slots=True)
class LLMCompletion:
    raw_text: str
    parsed_json: dict | None
    provider: str
    model: str = ""
    usage: LLMUsage | None = None
    estimated_cost_usd: float | None = None
    latency_ms: int | None = None
    request_id: str | None = None
    finish_reason: str | None = None

    def telemetry_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "usage": self.usage.to_dict() if self.usage else None,
            "estimated_cost_usd": self.estimated_cost_usd,
            "latency_ms": self.latency_ms,
            "request_id": self.request_id,
            "finish_reason": self.finish_reason,
        }


@dataclass(slots=True)
class LLMProviderConfig:
    provider: str
    api_key_present: bool
    base_url: str
    model: str
    timeout_seconds: int
    max_retries: int
    valid: bool
    warnings: list[str]
    errors: list[str]
    env_sources: dict[str, str | None]
    input_cost_per_1m_tokens: float | None = None
    output_cost_per_1m_tokens: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "api_key_present": self.api_key_present,
            "base_url": self.base_url,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "valid": self.valid,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "env_sources": dict(self.env_sources),
            "pricing": {
                "input_cost_per_1m_tokens": self.input_cost_per_1m_tokens,
                "output_cost_per_1m_tokens": self.output_cost_per_1m_tokens,
                "currency": "USD",
            },
        }


@dataclass(slots=True)
class LLMProviderHealth:
    provider: str
    status: str
    healthy: bool
    can_attempt_request: bool
    fallback_recommended: bool
    config: LLMProviderConfig
    warnings: list[str]
    errors: list[str]
    checked_network: bool = False
    latency_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "healthy": self.healthy,
            "can_attempt_request": self.can_attempt_request,
            "fallback_recommended": self.fallback_recommended,
            "checked_network": self.checked_network,
            "latency_ms": self.latency_ms,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "config": self.config.to_dict(),
        }


class LLMClient(Protocol):
    provider_name: str

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        ...

    def stream_json(self, system_prompt: str, user_prompt: str) -> Iterator[LLMStreamEvent]:
        ...

    def metadata(self) -> LLMProviderMetadata:
        ...


def inspect_llm_provider_config(provider: str = "openai-compatible") -> LLMProviderConfig:
    normalized = provider.lower()
    if normalized == "mock":
        return LLMProviderConfig(
            provider="mock",
            api_key_present=False,
            base_url="",
            model="mock",
            timeout_seconds=0,
            max_retries=0,
            valid=True,
            warnings=[],
            errors=[],
            env_sources={},
            input_cost_per_1m_tokens=0.0,
            output_cost_per_1m_tokens=0.0,
        )

    if normalized != "openai-compatible":
        return LLMProviderConfig(
            provider=normalized,
            api_key_present=False,
            base_url="",
            model="",
            timeout_seconds=DEFAULT_LLM_TIMEOUT_SECONDS,
            max_retries=DEFAULT_LLM_MAX_RETRIES,
            valid=False,
            warnings=[],
            errors=[f"Unsupported LLM provider: {provider}"],
            env_sources={},
        )

    base_url, base_url_source = _env_first(
        ["NEOFORGE_AGENT_LLM_BASE_URL", "OPENAI_BASE_URL"],
        default=DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
    )
    api_key, api_key_source = _env_first(["NEOFORGE_AGENT_LLM_API_KEY", "OPENAI_API_KEY"])
    model, model_source = _env_first(["NEOFORGE_AGENT_LLM_MODEL", "OPENAI_MODEL"])
    timeout_text, timeout_source = _env_first(
        ["NEOFORGE_AGENT_LLM_TIMEOUT_SECONDS", "OPENAI_TIMEOUT_SECONDS"],
        default=str(DEFAULT_LLM_TIMEOUT_SECONDS),
    )
    retries_text, retries_source = _env_first(
        ["NEOFORGE_AGENT_LLM_MAX_RETRIES", "OPENAI_MAX_RETRIES"],
        default=str(DEFAULT_LLM_MAX_RETRIES),
    )
    input_cost_text, input_cost_source = _env_first(
        ["NEOFORGE_AGENT_LLM_INPUT_COST_PER_1M", "OPENAI_INPUT_COST_PER_1M"]
    )
    output_cost_text, output_cost_source = _env_first(
        ["NEOFORGE_AGENT_LLM_OUTPUT_COST_PER_1M", "OPENAI_OUTPUT_COST_PER_1M"]
    )

    warnings: list[str] = []
    errors: list[str] = []
    timeout_seconds = _parse_positive_int(timeout_text, DEFAULT_LLM_TIMEOUT_SECONDS)
    max_retries = _parse_non_negative_int(retries_text, DEFAULT_LLM_MAX_RETRIES)
    input_cost_per_1m_tokens = _parse_optional_non_negative_float(input_cost_text)
    output_cost_per_1m_tokens = _parse_optional_non_negative_float(output_cost_text)
    model, model_warning = _normalize_model_name(model)
    if model_warning:
        warnings.append(model_warning)

    if timeout_seconds is None:
        warnings.append(
            f"Invalid LLM timeout `{timeout_text}`; using {DEFAULT_LLM_TIMEOUT_SECONDS} seconds."
        )
        timeout_seconds = DEFAULT_LLM_TIMEOUT_SECONDS
    if max_retries is None:
        warnings.append(
            f"Invalid LLM retry count `{retries_text}`; using {DEFAULT_LLM_MAX_RETRIES} retries."
        )
        max_retries = DEFAULT_LLM_MAX_RETRIES
    if input_cost_text and input_cost_per_1m_tokens is None:
        warnings.append(f"Invalid LLM input cost `{input_cost_text}`; token cost estimates will be omitted.")
    if output_cost_text and output_cost_per_1m_tokens is None:
        warnings.append(f"Invalid LLM output cost `{output_cost_text}`; token cost estimates will be omitted.")

    if not api_key:
        errors.append("Missing NEOFORGE_AGENT_LLM_API_KEY or OPENAI_API_KEY.")
    if not model:
        errors.append("Missing NEOFORGE_AGENT_LLM_MODEL or OPENAI_MODEL.")
    if not base_url:
        errors.append("Missing LLM base URL.")
    elif not base_url.startswith(("http://", "https://")):
        errors.append("LLM base URL must start with http:// or https://.")

    return LLMProviderConfig(
        provider="openai-compatible",
        api_key_present=bool(api_key),
        base_url=(base_url or "").rstrip("/"),
        model=model or "",
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        valid=not errors,
        warnings=warnings,
        errors=errors,
        env_sources={
            "base_url": base_url_source,
            "api_key": api_key_source,
            "model": model_source,
            "timeout_seconds": timeout_source,
            "max_retries": retries_source,
            "input_cost_per_1m_tokens": input_cost_source,
            "output_cost_per_1m_tokens": output_cost_source,
        },
        input_cost_per_1m_tokens=input_cost_per_1m_tokens,
        output_cost_per_1m_tokens=output_cost_per_1m_tokens,
    )


def get_llm_provider_metadata(provider: str = "openai-compatible") -> LLMProviderMetadata:
    config = inspect_llm_provider_config(provider)
    if config.provider == "mock":
        return mock_provider_metadata(config.model)
    if config.provider == "openai-compatible":
        return openai_compatible_provider_metadata(
            config.model,
            pricing=LLMPricing(
                input_cost_per_1m_tokens=config.input_cost_per_1m_tokens,
                output_cost_per_1m_tokens=config.output_cost_per_1m_tokens,
            ),
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
        )
    return unsupported_provider_metadata(config.provider, model=config.model)


def check_llm_provider_health(provider: str = "openai-compatible", *, network_probe: bool = False) -> LLMProviderHealth:
    config = inspect_llm_provider_config(provider)
    if config.provider == "mock":
        return LLMProviderHealth(
            provider="mock",
            status="pass",
            healthy=True,
            can_attempt_request=True,
            fallback_recommended=False,
            config=config,
            warnings=[],
            errors=[],
            checked_network=False,
        )

    warnings = list(config.warnings)
    errors = list(config.errors)
    healthy = config.valid
    status = "pass" if healthy else "fail"

    if network_probe:
        warnings.append("Network provider probe is not implemented by default; config-only health was checked.")

    return LLMProviderHealth(
        provider=config.provider,
        status=status,
        healthy=healthy,
        can_attempt_request=config.valid,
        fallback_recommended=not config.valid,
        config=config,
        warnings=warnings,
        errors=errors,
        checked_network=False,
    )


class MockLLMClient:
    provider_name = "mock"

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def metadata(self) -> LLMProviderMetadata:
        return mock_provider_metadata("mock")

    def stream_json(self, system_prompt: str, user_prompt: str) -> Iterator[LLMStreamEvent]:
        completion = self.complete_json(system_prompt, user_prompt)
        yield from _completion_stream_events(completion)

    def _completion(self, system_prompt: str, user_prompt: str, payload: dict) -> LLMCompletion:
        raw_text = json.dumps(payload, ensure_ascii=False, indent=2)
        usage = estimate_llm_usage(system_prompt, user_prompt, raw_text)
        return LLMCompletion(
            raw_text=raw_text,
            parsed_json=payload,
            provider=self.provider_name,
            model="mock",
            usage=usage,
            estimated_cost_usd=0.0,
            latency_ms=0,
            finish_reason="stop",
        )

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        prompt = user_prompt.lower()
        if "LLM_REVIEWER" in system_prompt:
            payload = self._mock_reviewer_payload(user_prompt)
            return self._completion(system_prompt, user_prompt, payload)
        if "TOOL_CALLING_REPAIR_AGENT" in system_prompt:
            payload = self._mock_repair_tool_payload(user_prompt)
            return self._completion(system_prompt, user_prompt, payload)
        is_modify = "existing modspec json" in prompt and "change request" in prompt
        if is_modify:
            payload = self._mock_modify_payload(user_prompt)
            return self._completion(system_prompt, user_prompt, payload)
        if self._is_direct_code_prompt(user_prompt):
            payload = self._direct_code_payload(user_prompt)
            return self._completion(system_prompt, user_prompt, payload)
        if (
            "quest" in prompt
            or "questline" in prompt
            or "task chain" in prompt
            or "advancement" in prompt
            or "guidebook" in prompt
            or "guide book" in prompt
            or "patchouli" in prompt
            or "任务" in user_prompt
            or "任务链" in user_prompt
            or "成就" in user_prompt
            or "引导" in user_prompt
            or "指南" in user_prompt
        ):
            payload = self._load_example("quest_guide_gameplay_loop.json")
            return self._completion(system_prompt, user_prompt, payload)
        if (
            "balance" in prompt
            or "economy" in prompt
            or "rarity" in prompt
            or "loot weight" in prompt
            or "machine cost" in prompt
            or "经济系统" in user_prompt
            or "稀有度" in user_prompt
            or "机器耗时" in user_prompt
            or "能量消耗" in user_prompt
            or "战利品权重" in user_prompt
        ):
            payload = self._load_example("balance_gameplay_loop.json")
            return self._completion(system_prompt, user_prompt, payload)
        if (
            "progression" in prompt
            or "gameplay loop" in prompt
            or "gameplay route" in prompt
            or "玩法线" in user_prompt
            or "成长路线" in user_prompt
            or "玩法路线" in user_prompt
        ):
            payload = self._load_example("progression_gameplay_loop.json")
            return self._completion(system_prompt, user_prompt, payload)
        if (
            "controlled java extension" in prompt
            or "safe java extension" in prompt
            or "java extension" in prompt
            or "受控 java 扩展" in prompt
        ):
            payload = {
                "mod_id": "extension_mod",
                "mod_name": "Extension Mod",
                "package": "com.generated.extension_mod",
                "version": "0.1.0",
                "features": [self._safe_java_extension_feature()],
            }
            return self._completion(system_prompt, user_prompt, payload)
        if (
            "ruby realm" in prompt
            or "world structure dsl" in prompt
            or ("dimension" in prompt and "biome" in prompt and "structure" in prompt)
            or ("loot pool" in prompt and "structure" in prompt)
        ):
            payload = self._ruby_realm_payload()
            return self._completion(system_prompt, user_prompt, payload)
        if any(token in user_prompt for token in ("一套红宝石工具", "红宝石工具套装", "红宝石全套工具")) or "ruby tool set" in prompt or "ruby tools" in prompt:
            payload = self._ruby_payload(self._ruby_tool_set())
        elif any(token in user_prompt for token in ("一套红宝石护甲", "红宝石护甲套装", "红宝石全套护甲")) or "ruby armor set" in prompt or "ruby armor" in prompt:
            payload = self._ruby_payload(self._ruby_armor_set())
        elif "红宝石镐" in user_prompt or "ruby pickaxe" in prompt:
            payload = self._ruby_payload([self._ruby_tool_feature("pickaxe")])
        elif "红宝石斧" in user_prompt or "ruby axe" in prompt:
            payload = self._ruby_payload([self._ruby_tool_feature("axe")])
        elif "红宝石铲" in user_prompt or "ruby shovel" in prompt:
            payload = self._ruby_payload([self._ruby_tool_feature("shovel")])
        elif "红宝石锄" in user_prompt or "ruby hoe" in prompt:
            payload = self._ruby_payload([self._ruby_tool_feature("hoe")])
        elif "红宝石头盔" in user_prompt or "ruby helmet" in prompt:
            payload = self._ruby_payload([self._ruby_armor_feature("helmet")])
        elif "红宝石胸甲" in user_prompt or "ruby chestplate" in prompt:
            payload = self._ruby_payload([self._ruby_armor_feature("chestplate")])
        elif "红宝石护腿" in user_prompt or "ruby leggings" in prompt:
            payload = self._ruby_payload([self._ruby_armor_feature("leggings")])
        elif "红宝石靴" in user_prompt or "ruby boots" in prompt:
            payload = self._ruby_payload([self._ruby_armor_feature("boots")])
        elif self._is_ruby_block_variant_prompt(user_prompt):
            payload = self._ruby_payload(self._ruby_block_variant_set())
        elif self._ruby_block_variant_kinds_from_prompt(user_prompt):
            payload = self._ruby_payload(self._ruby_block_variant_features(self._ruby_block_variant_kinds_from_prompt(user_prompt)))
        elif "ruby goblin" in prompt or ("goblin" in prompt and any(token in prompt for token in ("mob", "entity", "monster"))):
            payload = self._ruby_payload([self._ruby_goblin_feature()])
        elif "behavior dsl" in prompt or "battle charm" in prompt:
            payload = {
                "mod_id": "behavior_mod",
                "mod_name": "Behavior Mod",
                "package": "com.generated.behavior_mod",
                "version": "0.1.0",
                "features": [self._battle_charm_feature()],
            }
        elif "红宝石护符" in user_prompt or "ruby charm" in prompt:
            payload = {
                "mod_id": "ruby_mod",
                "mod_name": "Ruby Mod",
                "package": "com.generated.ruby_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "item",
                        "id": "ruby_charm",
                        "display_name_en_us": "Ruby Charm",
                        "display_name_zh_cn": "红宝石护符",
                        "behavior": {
                            "type": "right_click_heal",
                            "amount": 4,
                            "cooldown_ticks": 400,
                            "consume": False,
                        },
                    }
                ],
            }
        elif "速度水晶" in user_prompt or "speed crystal" in prompt:
            payload = {
                "mod_id": "speed_mod",
                "mod_name": "Speed Mod",
                "package": "com.generated.speed_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "item",
                        "id": "speed_crystal",
                        "display_name_en_us": "Speed Crystal",
                        "display_name_zh_cn": "速度水晶",
                        "behavior": {
                            "type": "right_click_effect",
                            "effect": "minecraft:speed",
                            "duration_ticks": 200,
                            "amplifier": 1,
                            "cooldown_ticks": 200,
                            "consume": False,
                        },
                    }
                ],
            }
        elif ("红宝石苹果" in user_prompt or "ruby apple" in prompt) and ("生命恢复" in user_prompt or "regeneration" in prompt):
            payload = {
                "mod_id": "ruby_mod",
                "mod_name": "Ruby Mod",
                "package": "com.generated.ruby_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "food",
                        "id": "ruby_apple",
                        "display_name_en_us": "Ruby Apple",
                        "display_name_zh_cn": "红宝石苹果",
                        "nutrition": 6,
                        "saturation": 0.8,
                        "effects": [
                            {
                                "effect": "minecraft:regeneration",
                                "duration_ticks": 100,
                                "amplifier": 1,
                                "probability": 1.0,
                            }
                        ],
                    }
                ],
            }
        elif ("红宝石剑" in user_prompt or "ruby sword" in prompt) and ("点燃" in user_prompt or "ignite" in prompt or "着火" in user_prompt):
            payload = {
                "mod_id": "ruby_mod",
                "mod_name": "Ruby Mod",
                "package": "com.generated.ruby_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "sword",
                        "id": "ruby_sword",
                        "display_name_en_us": "Ruby Sword",
                        "display_name_zh_cn": "红宝石剑",
                        "attack_damage_bonus": 4,
                        "attack_speed": -2.4,
                        "tool_material": "ruby",
                        "on_hit": {
                            "type": "ignite",
                            "seconds": 5,
                        },
                    }
                ],
            }
        elif ("自然生成" in user_prompt or "overworld" in prompt or "主世界" in user_prompt) and ("矿石" in user_prompt or "ore" in prompt):
            payload = {
                "mod_id": "ruby_mod",
                "mod_name": "Ruby Mod",
                "package": "com.generated.ruby_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "item",
                        "id": "ruby",
                        "display_name_en_us": "Ruby",
                        "display_name_zh_cn": "红宝石"
                    },
                    {
                        "type": "ore",
                        "id": "ruby_ore",
                        "display_name_en_us": "Ruby Ore",
                        "display_name_zh_cn": "红宝石矿石",
                        "drop": "ruby_mod:ruby",
                        "strength": 3.0,
                        "resistance": 3.0,
                        "sound": "stone",
                        "requires_correct_tool": True,
                        "tool_tier": "iron",
                        "worldgen": {
                            "enabled": True,
                            "dimension": "minecraft:overworld",
                            "min_y": -64,
                            "max_y": 32,
                            "vein_size": 6,
                            "veins_per_chunk": 4,
                        },
                    }
                ],
            }
        elif "ruby" in prompt or "红宝石" in user_prompt:
            if is_modify:
                payload = self._mock_modify_payload(user_prompt)
            elif any(token in prompt for token in ("sword", "apple", "ore", "block")) or any(
                token in user_prompt for token in ("剑", "苹果", "矿石", "方块")
            ):
                payload = self._load_example("llm_ruby_full_expected.json")
            else:
                payload = {
                    "mod_id": "ruby_mod",
                    "mod_name": "Ruby Mod",
                    "package": "com.generated.ruby_mod",
                    "version": "0.1.0",
                    "features": [
                        {
                            "type": "item",
                            "id": "ruby",
                            "display_name_en_us": "Ruby",
                            "display_name_zh_cn": "红宝石",
                        }
                    ],
                }
        else:
            payload = {
                "mod_id": "generated_mod",
                "mod_name": "Generated Mod",
                "package": "com.generated.generated_mod",
                "version": "0.1.0",
                "features": [],
            }

        return self._completion(system_prompt, user_prompt, payload)

    def _ruby_payload(self, features: list[dict]) -> dict:
        return {
            "mod_id": "ruby_mod",
            "mod_name": "Ruby Mod",
            "package": "com.generated.ruby_mod",
            "version": "0.1.0",
            "features": features,
        }

    def _is_direct_code_prompt(self, text: str) -> bool:
        prompt = text.lower()
        return any(
            token in prompt
            for token in (
                "direct code",
                "direct-code",
                "raw java",
                "freeform java",
                "custom java",
                "write java",
                "source patch",
                "patch source",
                "direct code lane",
            )
        )

    def _direct_code_payload(self, request: str) -> dict:
        package_name = "com.generated.direct_code_mod.directcode"
        content = "\n".join(
            [
                f"package {package_name};",
                "",
                "public final class DirectCodeMockFeature {",
                "    private DirectCodeMockFeature() {",
                "    }",
                "",
                "    public static String summary() {",
                '        return "mock direct code";',
                "    }",
                "}",
                "",
            ]
        )
        return {
            "mod_id": "direct_code_mod",
            "mod_name": "Direct Code Mod",
            "package": "com.generated.direct_code_mod",
            "version": "0.1.0",
            "features": [],
            "routing_decision": {
                "lane": "direct_code",
                "reason": "Mock planner detected source-level Java customization beyond ModSpec.",
            },
            "requires_direct_code": True,
            "direct_code_plan": {
                "request": request,
                "summary": "Add a safe direct-code marker class.",
                "changes": [
                    {
                        "path": "src/main/java/com/generated/direct_code_mod/directcode/DirectCodeMockFeature.java",
                        "operation": "write_file",
                        "content": content,
                        "reason": "Safe compile-verifiable direct-code mock artifact.",
                        "risk_level": "low",
                    }
                ],
            },
        }

    def _ruby_realm_payload(self) -> dict:
        return {
            "mod_id": "world_mod",
            "mod_name": "World Mod",
            "package": "com.generated.world_mod",
            "version": "0.1.0",
            "features": [
                {
                    "type": "biome",
                    "id": "ruby_fields",
                    "display_name_en_us": "Ruby Fields",
                    "temperature": 0.9,
                    "downfall": 0.25,
                    "sky_color": 12086413,
                    "water_color": 12733738,
                    "water_fog_color": 8004671,
                    "fog_color": 14262712,
                    "grass_color": 9227122,
                    "foliage_color": 7061097,
                },
                {
                    "type": "dimension",
                    "id": "ruby_realm",
                    "display_name_en_us": "Ruby Realm",
                    "biome": "world_mod:ruby_fields",
                    "dimension_type": "overworld_like",
                    "generator": "noise",
                    "ambient_light": 0.15,
                },
                {
                    "type": "world_feature",
                    "id": "ruby_vein",
                    "display_name_en_us": "Ruby Vein",
                    "feature_kind": "ore_vein",
                    "placed_block": "minecraft:redstone_ore",
                    "biomes": "world_mod:ruby_fields",
                    "vein_size": 6,
                    "veins_per_chunk": 5,
                    "min_y": -48,
                    "max_y": 32,
                },
                {
                    "type": "loot_pool",
                    "id": "ruby_shrine_loot",
                    "display_name_en_us": "Ruby Shrine Loot",
                    "rolls": 2,
                    "entries": [
                        {"item": "minecraft:emerald", "min_count": 1, "max_count": 4, "weight": 3},
                        {"item": "minecraft:diamond", "min_count": 1, "max_count": 2, "weight": 1, "chance": 0.5},
                    ],
                },
                {
                    "type": "structure",
                    "id": "ruby_shrine",
                    "display_name_en_us": "Ruby Shrine",
                    "structure_kind": "jigsaw",
                    "biomes": "world_mod:ruby_fields",
                    "spacing": 28,
                    "separation": 8,
                    "salt": 754321,
                    "size": 1,
                    "start_height": 64,
                    "loot_table": "world_mod:chests/ruby_shrine_loot",
                },
            ],
        }

    def _ruby_tool_set(self) -> list[dict]:
        equipment = [
            self._ruby_item_feature(),
            self._ruby_sword_feature(),
            *[self._ruby_tool_feature(tool_type) for tool_type in ("pickaxe", "axe", "shovel", "hoe")],
        ]
        return [*equipment, *self._ruby_equipment_recipes(("ruby_sword", "ruby_pickaxe", "ruby_axe", "ruby_shovel", "ruby_hoe"))]

    def _ruby_armor_set(self) -> list[dict]:
        equipment = [
            self._ruby_item_feature(),
            *[self._ruby_armor_feature(armor_type) for armor_type in ("helmet", "chestplate", "leggings", "boots")],
        ]
        return [*equipment, *self._ruby_equipment_recipes(("ruby_helmet", "ruby_chestplate", "ruby_leggings", "ruby_boots"))]

    def _is_ruby_block_variant_prompt(self, text: str) -> bool:
        prompt = text.lower()
        return (
            any(token in text for token in ("红宝石方块变体", "红宝石建筑方块套装", "红宝石方块套装"))
            or "ruby block variants" in prompt
            or "ruby building block set" in prompt
            or "ruby building blocks" in prompt
        )

    def _ruby_block_variant_kinds_from_prompt(self, text: str) -> list[str]:
        if self._is_ruby_block_variant_prompt(text):
            return ["stairs", "slab", "wall", "button", "pressure_plate", "fence", "fence_gate", "door", "trapdoor"]
        prompt = text.lower()
        kinds: list[str] = []
        checks = [
            ("stairs", ("红宝石楼梯", "ruby stairs", "ruby stair")),
            ("slab", ("红宝石台阶", "红宝石半砖", "ruby slab")),
            ("wall", ("红宝石墙", "ruby wall")),
            ("button", ("红宝石按钮", "ruby button")),
            ("pressure_plate", ("红宝石压力板", "ruby pressure plate")),
            ("fence_gate", ("红宝石栅栏门", "ruby fence gate")),
            ("trapdoor", ("红宝石活板门", "ruby trapdoor", "ruby trap door")),
            ("fence", ("红宝石栅栏", "ruby fence")),
            ("door", ("红宝石门", "ruby door")),
        ]
        for block_kind, tokens in checks:
            if block_kind == "fence" and ("红宝石栅栏门" in text or "ruby fence gate" in prompt):
                continue
            if block_kind == "door" and (
                "红宝石活板门" in text
                or "红宝石栅栏门" in text
                or "ruby trapdoor" in prompt
                or "ruby trap door" in prompt
                or "ruby fence gate" in prompt
            ):
                continue
            if any((token in prompt) if token.isascii() else (token in text) for token in tokens):
                kinds.append(block_kind)
        return kinds

    def _ruby_item_feature(self) -> dict:
        return {
            "type": "item",
            "id": "ruby",
            "display_name_en_us": "Ruby",
            "display_name_zh_cn": "红宝石",
        }

    def _ruby_goblin_feature(self) -> dict:
        return {
            "type": "entity",
            "id": "ruby_goblin",
            "display_name_en_us": "Ruby Goblin",
            "display_name_zh_cn": "Ruby Goblin",
            "entity_kind": "monster",
            "category": "monster",
            "width": 0.6,
            "height": 1.35,
            "tracking_range": 10,
            "update_interval": 3,
            "xp_reward": 5,
            "fire_immune": False,
            "attributes": {
                "max_health": 24,
                "movement_speed": 0.27,
                "attack_damage": 4,
                "armor": 2,
                "follow_range": 28,
                "knockback_resistance": 0,
            },
            "drops": [
                {
                    "item": "minecraft:emerald",
                    "min_count": 1,
                    "max_count": 2,
                    "chance": 0.5,
                }
            ],
            "spawn": {
                "enabled": True,
                "biomes": "#minecraft:is_overworld",
                "weight": 80,
                "min_count": 1,
                "max_count": 3,
                "placement": "on_ground",
            },
            "goals": [
                {"type": "float", "priority": 0},
                {"type": "melee_attack", "priority": 2, "speed": 1.1},
                {"type": "random_stroll", "priority": 5, "speed": 0.9},
                {"type": "look_at_player", "priority": 6, "distance": 8},
                {"type": "random_look_around", "priority": 7},
                {"type": "hurt_by_target", "priority": 1},
                {"type": "target_player", "priority": 2},
            ],
            "attack": {
                "type": "melee",
                "damage": 4,
                "speed": 1.1,
            },
        }

    def _safe_java_extension_feature(self) -> dict:
        return {
            "type": "java_extension",
            "id": "safe_info_extension",
            "display_name_en_us": "Safe Info Extension",
            "class_name": "SafeInfoExtension",
            "purpose": "Expose a tiny compile-time helper without editing existing generated sources.",
            "explanation": "The deterministic generator renders this as an additive managed class under the extension package.",
            "allowed_imports": ["net.minecraft.network.chat.Component"],
            "methods": [
                {
                    "name": "describe",
                    "return_type": "String",
                    "return_value": "Controlled Java extension generated from ModSpec.",
                    "explanation": "Returns a short audit-friendly description.",
                }
            ],
        }

    def _battle_charm_feature(self) -> dict:
        return {
            "type": "item",
            "id": "battle_charm",
            "display_name_en_us": "Battle Charm",
            "display_name_zh_cn": "",
            "behavior": {
                "type": "event_action",
                "events": [
                    {
                        "trigger": "right_click",
                        "triggers": ["right_click", "inventory_tick"],
                        "trigger_mode": "sequence",
                        "window_ticks": 100,
                        "cooldown_ticks": 100,
                        "state_key": "battle_charge",
                        "state_value": 1,
                        "resource": "energy",
                        "resource_amount": 10,
                        "conditions": [
                            {"type": "not_sneaking"},
                            {"type": "cooldown_ready", "resource": "battle_charge"},
                        ],
                        "actions": [
                            {"type": "heal", "target": "self", "amount": 4},
                            {
                                "type": "apply_effect",
                                "target": "self",
                                "effect": "minecraft:regeneration",
                                "duration_ticks": 100,
                                "amplifier": 0,
                            },
                            {"type": "set_state", "state_key": "battle_charge", "state_value": 1},
                            {"type": "consume_resource", "resource": "energy", "resource_amount": 10},
                            {"type": "spawn_particles", "particle": "minecraft:heart", "count": 10},
                            {"type": "play_sound", "sound": "minecraft:entity.experience_orb.pickup"},
                            {"type": "chain_event", "chain_trigger": "inventory_tick", "chain_target": "self", "delay_ticks": 20, "chain_window_ticks": 40},
                        ],
                    },
                    {
                        "trigger": "inventory_tick",
                        "interval_ticks": 100,
                        "conditions": [
                            {"type": "health_below", "threshold": 12},
                            {"type": "state_equals", "state_key": "battle_charge", "state_value": 1},
                        ],
                        "actions": [
                            {"type": "spawn_particles", "particle": "minecraft:heart", "count": 2},
                            {"type": "restore_resource", "resource": "energy", "resource_amount": 5},
                        ],
                    },
                ],
            },
        }

    def _ruby_block_feature(self) -> dict:
        return {
            "type": "block",
            "id": "ruby_block",
            "display_name_en_us": "Block of Ruby",
            "display_name_zh_cn": "红宝石方块",
            "strength": 5.0,
            "resistance": 6.0,
            "sound": "metal",
            "requires_correct_tool": True,
            "tool_tier": "iron",
            "block_kind": "cube",
        }

    def _ruby_block_variant_set(self) -> list[dict]:
        return self._ruby_block_variant_features(["stairs", "slab", "wall", "button", "pressure_plate", "fence", "fence_gate", "door", "trapdoor"])

    def _ruby_block_variant_features(self, block_kinds: list[str]) -> list[dict]:
        features = [
            self._ruby_item_feature(),
            self._ruby_block_feature(),
            *[self._ruby_block_variant_feature(kind) for kind in block_kinds],
        ]
        recipe_ids = [
            "ruby_block",
            *[self._ruby_block_variant_feature(kind)["id"] for kind in block_kinds],
        ]
        return [*features, *self._ruby_block_variant_recipes(recipe_ids)]

    def _ruby_block_variant_feature(self, block_kind: str) -> dict:
        labels = {
            "stairs": ("ruby_stairs", "Ruby Stairs", "红宝石楼梯"),
            "slab": ("ruby_slab", "Ruby Slab", "红宝石台阶"),
            "wall": ("ruby_wall", "Ruby Wall", "红宝石墙"),
            "button": ("ruby_button", "Ruby Button", "红宝石按钮"),
            "pressure_plate": ("ruby_pressure_plate", "Ruby Pressure Plate", "红宝石压力板"),
            "fence": ("ruby_fence", "Ruby Fence", "红宝石栅栏"),
            "fence_gate": ("ruby_fence_gate", "Ruby Fence Gate", "红宝石栅栏门"),
            "door": ("ruby_door", "Ruby Door", "红宝石门"),
            "trapdoor": ("ruby_trapdoor", "Ruby Trapdoor", "红宝石活板门"),
        }
        identifier, display_name, display_name_zh = labels[block_kind]
        return {
            "type": "block",
            "id": identifier,
            "display_name_en_us": display_name,
            "display_name_zh_cn": display_name_zh,
            "strength": 5.0,
            "resistance": 6.0,
            "sound": "metal",
            "requires_correct_tool": True,
            "tool_tier": "iron",
            "block_kind": block_kind,
            "base_block": "ruby_block",
        }

    def _ruby_sword_feature(self) -> dict:
        return {
            "type": "sword",
            "id": "ruby_sword",
            "display_name_en_us": "Ruby Sword",
            "display_name_zh_cn": "红宝石剑",
            "attack_damage_bonus": 4,
            "attack_speed": -2.4,
            "tool_material": "ruby",
        }

    def _ruby_tool_feature(self, tool_type: str) -> dict:
        labels = {
            "pickaxe": ("ruby_pickaxe", "Ruby Pickaxe", "红宝石镐", 1.0, -2.8),
            "axe": ("ruby_axe", "Ruby Axe", "红宝石斧", 5.0, -3.0),
            "shovel": ("ruby_shovel", "Ruby Shovel", "红宝石铲", 1.5, -3.0),
            "hoe": ("ruby_hoe", "Ruby Hoe", "红宝石锄", 0.0, -3.0),
        }
        identifier, display_name, display_name_zh, attack_damage, attack_speed = labels.get(tool_type, labels["pickaxe"])
        return {
            "type": "tool",
            "id": identifier,
            "display_name_en_us": display_name,
            "display_name_zh_cn": display_name_zh,
            "tool_type": tool_type,
            "tool_material": "ruby",
            "attack_damage_bonus": attack_damage,
            "attack_speed": attack_speed,
        }

    def _ruby_armor_feature(self, armor_type: str) -> dict:
        labels = {
            "helmet": ("ruby_helmet", "Ruby Helmet", "红宝石头盔"),
            "chestplate": ("ruby_chestplate", "Ruby Chestplate", "红宝石胸甲"),
            "leggings": ("ruby_leggings", "Ruby Leggings", "红宝石护腿"),
            "boots": ("ruby_boots", "Ruby Boots", "红宝石靴子"),
        }
        identifier, display_name, display_name_zh = labels.get(armor_type, labels["helmet"])
        return {
            "type": "armor",
            "id": identifier,
            "display_name_en_us": display_name,
            "display_name_zh_cn": display_name_zh,
            "armor_type": armor_type,
            "armor_material": "ruby",
        }

    def _ruby_equipment_recipes(self, identifiers: tuple[str, ...]) -> list[dict]:
        patterns = {
            "ruby_sword": (["R", "R", "S"], {"R": "ruby_mod:ruby", "S": "minecraft:stick"}),
            "ruby_pickaxe": (["RRR", " S ", " S "], {"R": "ruby_mod:ruby", "S": "minecraft:stick"}),
            "ruby_axe": (["RR ", "RS ", " S "], {"R": "ruby_mod:ruby", "S": "minecraft:stick"}),
            "ruby_shovel": (["R", "S", "S"], {"R": "ruby_mod:ruby", "S": "minecraft:stick"}),
            "ruby_hoe": (["RR ", " S ", " S "], {"R": "ruby_mod:ruby", "S": "minecraft:stick"}),
            "ruby_helmet": (["RRR", "R R"], {"R": "ruby_mod:ruby"}),
            "ruby_chestplate": (["R R", "RRR", "RRR"], {"R": "ruby_mod:ruby"}),
            "ruby_leggings": (["RRR", "R R", "R R"], {"R": "ruby_mod:ruby"}),
            "ruby_boots": (["R R", "R R"], {"R": "ruby_mod:ruby"}),
        }
        recipes: list[dict] = []
        for identifier in identifiers:
            pattern, keys = patterns[identifier]
            recipes.append(
                {
                    "type": "recipe",
                    "id": identifier,
                    "recipe_type": "shaped",
                    "pattern": pattern,
                    "keys": keys,
                    "result": f"ruby_mod:{identifier}",
                    "count": 1,
                    "category": "equipment",
                    "group": "ruby_equipment",
                }
            )
        return recipes

    def _ruby_block_variant_recipes(self, identifiers: list[str] | tuple[str, ...]) -> list[dict]:
        patterns = {
            "ruby_block": ("shaped", ["RRR", "RRR", "RRR"], {"R": "ruby_mod:ruby"}, [], 1, "building"),
            "ruby_stairs": ("shaped", ["R  ", "RR ", "RRR"], {"R": "ruby_mod:ruby_block"}, [], 4, "building"),
            "ruby_slab": ("shaped", ["RRR"], {"R": "ruby_mod:ruby_block"}, [], 6, "building"),
            "ruby_wall": ("shaped", ["RRR", "RRR"], {"R": "ruby_mod:ruby_block"}, [], 6, "building"),
            "ruby_button": ("shapeless", [], {}, ["ruby_mod:ruby_block"], 1, "redstone"),
            "ruby_pressure_plate": ("shaped", ["RR"], {"R": "ruby_mod:ruby_block"}, [], 1, "redstone"),
            "ruby_fence": ("shaped", ["RSR", "RSR"], {"R": "ruby_mod:ruby_block", "S": "minecraft:stick"}, [], 3, "building"),
            "ruby_fence_gate": ("shaped", ["SRS", "SRS"], {"R": "ruby_mod:ruby_block", "S": "minecraft:stick"}, [], 1, "redstone"),
            "ruby_door": ("shaped", ["RR", "RR", "RR"], {"R": "ruby_mod:ruby_block"}, [], 3, "redstone"),
            "ruby_trapdoor": ("shaped", ["RRR", "RRR"], {"R": "ruby_mod:ruby_block"}, [], 2, "redstone"),
        }
        recipes: list[dict] = []
        for identifier in identifiers:
            recipe_type, pattern, keys, ingredients, count, category = patterns[identifier]
            recipes.append(
                {
                    "type": "recipe",
                    "id": identifier,
                    "recipe_type": recipe_type,
                    "pattern": pattern,
                    "keys": keys,
                    "ingredients": ingredients,
                    "result": f"ruby_mod:{identifier}",
                    "count": count,
                    "category": category,
                    "group": "ruby_block_variants",
                }
            )
        return recipes

    def _load_example(self, filename: str) -> dict:
        path = self.project_root / "examples" / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def _mock_repair_tool_payload(self, user_prompt: str) -> dict:
        try:
            prompt_payload = json.loads(user_prompt)
        except json.JSONDecodeError:
            prompt_payload = {}
        completed = prompt_payload.get("completed_actions") if isinstance(prompt_payload, dict) else []
        if not isinstance(completed, list):
            completed = []
        completed_actions = [str(action) for action in completed]
        prompt = user_prompt.lower()
        current_gates = prompt_payload.get("current_gates", {}) if isinstance(prompt_payload, dict) else {}
        audit_gate = current_gates.get("audit", {}) if isinstance(current_gates, dict) else {}
        audit_success = audit_gate.get("success") if isinstance(audit_gate, dict) else None
        loop_purpose = str(prompt_payload.get("loop_purpose", "repair")) if isinstance(prompt_payload, dict) else "repair"
        rag_policy = prompt_payload.get("rag_policy", {}) if isinstance(prompt_payload, dict) else {}
        rag_mode = str(rag_policy.get("mode", "auto") if isinstance(rag_policy, dict) else "auto").lower()
        rag_off = rag_mode == "off"

        if loop_purpose.startswith("develop"):
            if "retrieve_rag" not in completed_actions:
                return {
                    "thought_summary": "Use NeoForge knowledge before refining the generated baseline workspace.",
                    "action": "retrieve_rag",
                    "args": {
                        "reason": "develop_refinement_sensitive_resource",
                        "query": "pack.mcmeta generated resources develop refinement audit",
                        "limit": 5,
                        "max_hops": 2,
                    },
                }
            if rag_off:
                return {
                    "thought_summary": "RAG is disabled for this ablation run, so the mock agent refuses a sensitive resource refinement.",
                    "action": "finish",
                    "args": {
                        "status": "failed",
                        "summary": "RAG disabled; sensitive generated resource refinement was not patched.",
                    },
                }
            if "read_file" not in completed_actions:
                return {
                    "thought_summary": "Inspect the generated pack metadata before applying a controlled refinement.",
                    "action": "read_file",
                    "args": {"path": "src/main/resources/pack.mcmeta"},
                }
            if "apply_structured_patch" not in completed_actions:
                match = re.search(r'"description":\s*"([^"]+ resources)"', user_prompt)
                old = match.group(0) if match else '"description": "ruby_mod resources"'
                description = match.group(1) if match else "ruby_mod resources"
                return {
                    "thought_summary": "Apply a minimal structured patch to mark the generated baseline as refined.",
                    "action": "apply_structured_patch",
                    "args": {
                        "changes": [
                            {
                                "operation": "replace_text",
                                "path": "src/main/resources/pack.mcmeta",
                                "old": old,
                                "new": f'"description": "{description} (develop refined)"',
                                "reason": "Develop mode should refine the generated workspace through a constrained structured patch.",
                                "citation_ids": ["pack.mcmeta"],
                            }
                        ]
                    },
                }
            if "run_audit" not in completed_actions:
                return {
                    "thought_summary": "After refining the generated workspace, rerun audit to validate the gate.",
                    "action": "run_audit",
                    "args": {},
                }
            return {
                "thought_summary": "The develop refinement loop verified the workspace; finish with the latest observations.",
                "action": "finish",
                "args": {"status": "success", "summary": "Develop refinement completed after audit verification."},
            }

        if audit_success is True and (not completed_actions or completed_actions[-1] != "finish"):
            return {
                "thought_summary": "The requested audit gate is now passing, so the repair can finish.",
                "action": "finish",
                "args": {"status": "success", "summary": "Audit/build observations pass."},
            }

        if "missing required file" in prompt and "regenerate_managed_files" not in completed_actions:
            return {
                "thought_summary": "A generated file is missing, so deterministic regeneration is the safest repair.",
                "action": "regenerate_managed_files",
                "args": {},
            }

        if "neoforge.mods.toml" in prompt and "regenerate_managed_files" in completed_actions:
            if "retrieve_rag" not in completed_actions:
                return {
                    "thought_summary": "Regeneration could not restore the missing mods metadata template, so retrieve repair guidance before patching.",
                    "action": "retrieve_rag",
                    "args": {
                        "reason": "missing neoforge.mods.toml",
                        "query": "neoforge mods.toml metadata missing generated template repair",
                        "limit": 5,
                        "max_hops": 2,
                    },
                }
            if rag_off:
                return {
                    "thought_summary": "RAG is disabled for this ablation run, so the mock agent stops before restoring sensitive NeoForge metadata.",
                    "action": "finish",
                    "args": {
                        "status": "failed",
                        "summary": "RAG disabled; missing neoforge.mods.toml was not patched.",
                    },
                }
            if "apply_structured_patch" not in completed_actions:
                return {
                    "thought_summary": "Write a minimal generated NeoForge mods metadata file through the structured patch tool.",
                    "action": "apply_structured_patch",
                    "args": {
                        "changes": [
                            {
                                "operation": "write_file",
                                "path": "src/main/templates/META-INF/neoforge.mods.toml",
                                "content": (
                                    'modLoader="javafml"\n'
                                    'loaderVersion="[4,)"\n'
                                    'license="MIT"\n'
                                    '[[mods]]\n'
                                    'modId="ruby_mod"\n'
                                    'version="0.1.0"\n'
                                    'displayName="Ruby Mod"\n'
                                    "description='''\n"
                                    "Generated NeoForge metadata restored by the constrained repair agent.\n"
                                    "'''\n"
                                ),
                                "reason": "Audit requires the generated NeoForge mods metadata template to exist.",
                                "citation_ids": ["neoforge.mods_toml"],
                            }
                        ]
                    },
                }
            if "run_audit" not in completed_actions:
                return {
                    "thought_summary": "After restoring neoforge.mods.toml, rerun audit to verify the workspace.",
                    "action": "run_audit",
                    "args": {},
                }
            return {
                "thought_summary": "The metadata template repair was verified by audit; finish the repair loop.",
                "action": "finish",
                "args": {"status": "success", "summary": "Missing NeoForge metadata template restored and audited."},
            }

        goal_text = str(prompt_payload.get("goal", "") if isinstance(prompt_payload, dict) else "").lower()
        audit_text = json.dumps(audit_gate, ensure_ascii=False).lower() if isinstance(audit_gate, dict) else ""
        recipe_failure = (
            "missing_agentic_rag_material" in prompt
            or "recipe/resource" in goal_text
            or "recipe json" in goal_text
            or ("recipe" in audit_text and ("data/" in audit_text or "missing_agentic_rag_material" in audit_text))
        )
        if recipe_failure:
            if "retrieve_rag" not in completed_actions:
                return {
                    "thought_summary": "The failure touches data-pack recipe JSON, so retrieve recipe/resource path rules before patching.",
                    "action": "retrieve_rag",
                    "args": {
                        "reason": "recipe json audit failure",
                        "query": "recipe json audit failure missing local item resource path",
                        "limit": 5,
                        "max_hops": 2,
                    },
                }
            if rag_off:
                return {
                    "thought_summary": "RAG is disabled for this ablation run, so the mock agent refuses to patch recipe JSON without citations.",
                    "action": "finish",
                    "args": {
                        "status": "failed",
                        "summary": "RAG disabled; recipe/resource path failure was not patched.",
                    },
                }
            if "search_files" not in completed_actions and "read_file" not in completed_actions:
                return {
                    "thought_summary": "Locate the generated recipe JSON containing the broken resource reference.",
                    "action": "search_files",
                    "args": {
                        "query": "missing_agentic_rag_material",
                        "glob": "src/main/resources/data/**/*.json",
                        "limit": 10,
                    },
                }
            if "apply_structured_patch" not in completed_actions:
                recipe_path = _recent_observation_match_path(
                    prompt_payload,
                    prefix="src/main/resources/data/",
                    suffix=".json",
                ) or "src/main/resources/data/ruby_mod/recipe/ruby_sword.json"
                return {
                    "thought_summary": "Patch the broken generated recipe reference back to the local ruby item id with citation support.",
                    "action": "apply_structured_patch",
                    "args": {
                        "changes": [
                            {
                                "operation": "replace_text",
                                "path": recipe_path,
                                "old": "ruby_mod:missing_agentic_rag_material",
                                "new": "ruby_mod:ruby",
                                "reason": "Generated recipe JSON must reference an existing namespaced item id.",
                                "citation_ids": ["data.recipes_loot_tags"],
                            }
                        ]
                    },
                }
            if "run_audit" not in completed_actions:
                return {
                    "thought_summary": "After repairing the recipe JSON resource reference, rerun audit.",
                    "action": "run_audit",
                    "args": {},
                }
            return {
                "thought_summary": "The recipe/resource path repair was verified by audit; finish the repair loop.",
                "action": "finish",
                "args": {"status": "success", "summary": "Recipe resource path repaired and audited."},
            }

        if "retrieve_rag" not in completed_actions:
            return {
                "thought_summary": "Use bundled NeoForge repair knowledge before editing files.",
                "action": "retrieve_rag",
                "args": {
                    "reason": "pack.mcmeta audit failure",
                    "query": "pack.mcmeta audit repair generated resources",
                    "limit": 5,
                    "max_hops": 2,
                },
            }

        if rag_off:
            return {
                "thought_summary": "RAG is disabled for this ablation run, so the mock agent stops before patching sensitive generated resources.",
                "action": "finish",
                "args": {
                    "status": "failed",
                    "summary": "RAG disabled; sensitive metadata/resource failure was not patched.",
                },
            }

        if "pack.mcmeta" in prompt and "read_file" not in completed_actions:
            return {
                "thought_summary": "The audit points at pack.mcmeta, so read that managed resource file.",
                "action": "read_file",
                "args": {"path": "src/main/resources/pack.mcmeta"},
            }

        if "read_file" in completed_actions and "apply_structured_patch" not in completed_actions:
            if '"pack_format": "BROKEN"' in user_prompt:
                old = '"pack_format": "BROKEN"'
            elif '"pack_format": "broken"' in prompt:
                old = '"pack_format": "broken"'
            else:
                old = '"pack_format": "BROKEN"'
            return {
                "thought_summary": "Apply a minimal structured text replacement to restore integer pack_format.",
                "action": "apply_structured_patch",
                "args": {
                    "changes": [
                        {
                            "operation": "replace_text",
                            "path": "src/main/resources/pack.mcmeta",
                            "old": old,
                            "new": '"pack_format": 61',
                            "reason": "Audit requires pack.pack_format to be an integer.",
                            "citation_ids": ["pack.mcmeta"],
                        }
                    ]
                },
            }

        if "apply_structured_patch" in completed_actions and "run_audit" not in completed_actions:
            return {
                "thought_summary": "After a structured patch, rerun audit to verify the repair.",
                "action": "run_audit",
                "args": {},
            }

        if "run_audit" in completed_actions:
            return {
                "thought_summary": "The audit was rerun; finish based on the latest gate observation.",
                "action": "finish",
                "args": {"status": "success", "summary": "Repair loop completed after audit verification."},
            }

        return {
            "thought_summary": "No targeted repair was identified; finish with the current observations.",
            "action": "finish",
            "args": {"status": "failed", "summary": "Mock repair agent could not identify a safe repair."},
        }

    def _mock_reviewer_payload(self, user_prompt: str) -> dict:
        try:
            prompt_payload = json.loads(user_prompt)
        except json.JSONDecodeError:
            prompt_payload = {}
        prompt = user_prompt.lower()
        goal = str(prompt_payload.get("user_goal", "") if isinstance(prompt_payload, dict) else "")
        audit = prompt_payload.get("audit_result", {}) if isinstance(prompt_payload, dict) else {}
        build = prompt_payload.get("build_result", {}) if isinstance(prompt_payload, dict) else {}
        stage = str(prompt_payload.get("review_stage", "") if isinstance(prompt_payload, dict) else "")
        changed_files = prompt_payload.get("changed_files_summary", []) if isinstance(prompt_payload, dict) else []
        audit_failed = isinstance(audit, dict) and audit.get("attempted") and audit.get("success") is False
        build_failed = isinstance(build, dict) and build.get("attempted") and build.get("success") is False
        trigger_text = goal.lower() if goal else prompt

        if "missing requirement" in trigger_text or "must include missing" in trigger_text or "needs missing feature" in trigger_text:
            return {
                "coverage_status": "fail",
                "covered_requirements": ["Generated baseline workspace was reviewed."],
                "missing_requirements": ["A requested missing feature is not represented in the ModSpec or generated workspace."],
                "unsupported_or_risky_requests": [],
                "patch_risks": [],
                "recommended_checks": ["Update ModSpec or planner handling for the missing feature, then rerun audit."],
                "evidence_sufficiency": "sufficient",
                "unsupported_citation_gaps": [],
                "requires_more_rag": False,
                "decision": "reject",
                "confidence": 0.86,
            }
        if "needs repair review" in trigger_text or "reviewer needs repair" in trigger_text:
            return {
                "coverage_status": "partial",
                "covered_requirements": ["Generated workspace exists and can be audited."],
                "missing_requirements": ["Reviewer requested one additional constrained refinement pass."],
                "unsupported_or_risky_requests": [],
                "patch_risks": ["Structured patch changed generated resources; verify audit after reviewer-requested repair."],
                "recommended_checks": ["Run one more tool-calling refinement loop with this reviewer observation."],
                "evidence_sufficiency": "insufficient",
                "unsupported_citation_gaps": ["Reviewer requested more RAG-backed evidence before approval."],
                "requires_more_rag": True,
                "decision": "needs_repair",
                "confidence": 0.78,
            }
        if audit_failed or build_failed:
            return {
                "coverage_status": "partial",
                "covered_requirements": ["Reviewer inspected planner, trace, and gate observations."],
                "missing_requirements": ["Deterministic audit/build gate still reports failure."],
                "unsupported_or_risky_requests": [],
                "patch_risks": ["Reviewer approval cannot override failing audit/build gates."],
                "recommended_checks": ["Repair gate failures before accepting the run."],
                "evidence_sufficiency": "sufficient",
                "unsupported_citation_gaps": [],
                "requires_more_rag": False,
                "decision": "needs_repair",
                "confidence": 0.82,
            }
        patch_risks = []
        if isinstance(changed_files, list) and changed_files:
            patch_risks.append("Changed files were constrained to generated workspace paths.")
        return {
            "coverage_status": "pass",
            "covered_requirements": [
                goal or "User goal was represented by the generated ModSpec/workspace.",
                "Requested audit/build observations do not show failing gates.",
            ],
            "missing_requirements": [],
            "unsupported_or_risky_requests": [],
            "patch_risks": patch_risks,
            "recommended_checks": ["Keep deterministic audit/build as the final acceptance gate."],
            "evidence_sufficiency": "sufficient",
            "unsupported_citation_gaps": [],
            "requires_more_rag": False,
            "decision": "approve" if stage != "baseline" else "approve",
            "confidence": 0.9,
        }

    def _mock_modify_payload(self, user_prompt: str) -> dict:
        change_request = user_prompt
        if "Change Request:" in user_prompt:
            change_request = user_prompt.split("Change Request:", 1)[1]
        prompt = change_request.lower()
        if self._is_direct_code_prompt(change_request):
            return self._direct_code_modify_payload(change_request)
        features: list[dict] = []
        if (
            "controlled java extension" in prompt
            or "safe java extension" in prompt
            or "java extension" in prompt
            or "受控 java 扩展" in prompt
        ):
            features.append(self._safe_java_extension_feature())
        if "红宝石护符" in change_request or "ruby charm" in prompt or "right click heal" in prompt or "heals 4" in prompt:
            features.append(
                {
                    "type": "item",
                    "id": "ruby_charm",
                    "display_name_en_us": "Ruby Charm",
                    "display_name_zh_cn": "红宝石护符",
                    "behavior": {
                        "type": "right_click_heal",
                        "amount": 4,
                        "cooldown_ticks": 400,
                        "consume": False,
                    },
                }
            )
        if self._is_ruby_block_variant_prompt(change_request):
            features.extend(self._ruby_block_variant_set())
        elif self._ruby_block_variant_kinds_from_prompt(change_request):
            features.extend(self._ruby_block_variant_features(self._ruby_block_variant_kinds_from_prompt(change_request)))
        if any(token in change_request for token in ("一套红宝石工具", "红宝石工具套装", "红宝石全套工具")) or "ruby tool set" in prompt or "ruby tools" in prompt:
            features.extend(self._ruby_tool_set())
        elif "红宝石镐" in change_request or "ruby pickaxe" in prompt:
            features.append(self._ruby_tool_feature("pickaxe"))
        elif "红宝石斧" in change_request or "ruby axe" in prompt:
            features.append(self._ruby_tool_feature("axe"))
        elif "红宝石铲" in change_request or "ruby shovel" in prompt:
            features.append(self._ruby_tool_feature("shovel"))
        elif "红宝石锄" in change_request or "ruby hoe" in prompt:
            features.append(self._ruby_tool_feature("hoe"))
        if any(token in change_request for token in ("一套红宝石护甲", "红宝石护甲套装", "红宝石全套护甲")) or "ruby armor set" in prompt or "ruby armor" in prompt:
            features.extend(self._ruby_armor_set())
        elif "红宝石头盔" in change_request or "ruby helmet" in prompt:
            features.append(self._ruby_armor_feature("helmet"))
        elif "红宝石胸甲" in change_request or "ruby chestplate" in prompt:
            features.append(self._ruby_armor_feature("chestplate"))
        elif "红宝石护腿" in change_request or "ruby leggings" in prompt:
            features.append(self._ruby_armor_feature("leggings"))
        elif "红宝石靴" in change_request or "ruby boots" in prompt:
            features.append(self._ruby_armor_feature("boots"))
        if "红宝石剑" in change_request or "ruby sword" in prompt or "再添加红宝石剑" in change_request:
            features.append(
                {
                    "type": "sword",
                    "id": "ruby_sword",
                    "display_name_en_us": "Ruby Sword",
                    "display_name_zh_cn": "红宝石剑",
                    "attack_damage_bonus": 4,
                    "attack_speed": -2.4,
                    "tool_material": "ruby",
                }
            )
        if "红宝石方块" in change_request or "ruby block" in prompt:
            features.append(
                {
                    "type": "block",
                    "id": "ruby_block",
                    "display_name_en_us": "Block of Ruby",
                    "display_name_zh_cn": "红宝石方块",
                    "strength": 5.0,
                    "resistance": 6.0,
                    "sound": "metal",
                    "requires_correct_tool": True,
                    "tool_tier": "iron",
                }
            )
        if "红宝石矿石" in change_request or "ruby ore" in prompt:
            features.append(
                {
                    "type": "ore",
                    "id": "ruby_ore",
                    "display_name_en_us": "Ruby Ore",
                    "display_name_zh_cn": "红宝石矿石",
                    "drop": "ruby_mod:ruby",
                    "strength": 3.0,
                    "resistance": 3.0,
                    "sound": "stone",
                    "requires_correct_tool": True,
                    "tool_tier": "iron",
                    "worldgen": {
                        "enabled": True,
                        "dimension": "minecraft:overworld",
                        "min_y": -64,
                        "max_y": 32,
                        "vein_size": 6,
                        "veins_per_chunk": 4,
                    } if ("自然生成" in change_request or "主世界" in change_request or "overworld" in prompt) else None,
                }
            )
        if "红宝石苹果" in change_request or "ruby apple" in prompt:
            features.append(
                {
                    "type": "food",
                    "id": "ruby_apple",
                    "display_name_en_us": "Ruby Apple",
                    "display_name_zh_cn": "红宝石苹果",
                    "nutrition": 6,
                    "saturation": 0.8,
                }
            )
        if "分解成九个红宝石" in change_request or "9 ruby" in prompt:
            features.append(
                {
                    "type": "recipe",
                    "id": "ruby_from_ruby_block",
                    "recipe_type": "shapeless",
                    "ingredients": ["ruby_mod:ruby_block"],
                    "result": "ruby_mod:ruby",
                    "count": 9,
                }
            )
        if "合成红宝石方块" in change_request or "craft ruby block" in prompt:
            features.append(
                {
                    "type": "recipe",
                    "id": "ruby_block",
                    "recipe_type": "shaped",
                    "pattern": ["RRR", "RRR", "RRR"],
                    "keys": {"R": "ruby_mod:ruby"},
                    "result": "ruby_mod:ruby_block",
                    "count": 1,
                }
            )
        if any(feature.get("id") == "ruby_ore" for feature in features) and '"id": "ruby"' not in user_prompt:
            features.insert(
                0,
                {
                    "type": "item",
                    "id": "ruby",
                    "display_name_en_us": "Ruby",
                    "display_name_zh_cn": "Ruby",
                },
            )
        return {
            "mod_id": "ruby_mod",
            "mod_name": "Ruby Mod",
            "package": "com.generated.ruby_mod",
            "version": "0.1.0",
            "features": features,
        }

    def _direct_code_modify_payload(self, request: str) -> dict:
        package_name = "com.generated.ruby_mod.directcode"
        content = "\n".join(
            [
                f"package {package_name};",
                "",
                "public final class DirectCodeModifyMockFeature {",
                "    private DirectCodeModifyMockFeature() {",
                "    }",
                "",
                "    public static String summary() {",
                '        return "mock direct code modify";',
                "    }",
                "}",
                "",
            ]
        )
        return {
            "mod_id": "ruby_mod",
            "mod_name": "Ruby Mod",
            "package": "com.generated.ruby_mod",
            "version": "0.1.0",
            "features": [],
            "routing_decision": {
                "lane": "direct_code",
                "reason": "Mock modify planner detected source-level Java customization beyond ModSpec.",
            },
            "requires_direct_code": True,
            "direct_code_plan": {
                "request": request,
                "summary": "Add a safe direct-code modify marker class.",
                "changes": [
                    {
                        "path": "src/main/java/com/generated/ruby_mod/directcode/DirectCodeModifyMockFeature.java",
                        "operation": "write_file",
                        "content": content,
                        "reason": "Safe compile-verifiable direct-code modify mock artifact.",
                        "risk_level": "low",
                    }
                ],
            },
        }


def _recent_observation_match_path(
    prompt_payload: dict[str, Any],
    *,
    prefix: str,
    suffix: str,
) -> str | None:
    observations = prompt_payload.get("recent_observations") if isinstance(prompt_payload, dict) else []
    if not isinstance(observations, list):
        return None
    normalized_prefix = prefix.replace("\\", "/")
    for entry in reversed(observations):
        if not isinstance(entry, dict):
            continue
        candidates: list[Any] = []
        observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
        candidates.extend(observation.get("matches") if isinstance(observation.get("matches"), list) else [])
        candidates.extend(entry.get("matches") if isinstance(entry.get("matches"), list) else [])
        if observation.get("path"):
            candidates.append({"path": observation.get("path")})
        if entry.get("path"):
            candidates.append({"path": entry.get("path")})
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            path = str(candidate.get("path") or "").replace("\\", "/").strip()
            if path.startswith(normalized_prefix) and path.endswith(suffix):
                return path
    return None


class OpenAICompatibleClient:
    provider_name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = DEFAULT_LLM_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_LLM_MAX_RETRIES,
        pricing: LLMPricing | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.pricing = pricing or LLMPricing()

    @classmethod
    def from_env(cls) -> "OpenAICompatibleClient":
        config = inspect_llm_provider_config("openai-compatible")
        if not config.valid:
            raise ValueError("Invalid LLM provider configuration: " + "; ".join(config.errors))
        api_key, _ = _env_first(["NEOFORGE_AGENT_LLM_API_KEY", "OPENAI_API_KEY"])
        return cls(
            base_url=config.base_url,
            api_key=api_key or "",
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            pricing=LLMPricing(
                input_cost_per_1m_tokens=config.input_cost_per_1m_tokens,
                output_cost_per_1m_tokens=config.output_cost_per_1m_tokens,
            ),
        )

    def metadata(self) -> LLMProviderMetadata:
        return openai_compatible_provider_metadata(
            self.model,
            pricing=self.pricing,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
        )

    def stream_json(self, system_prompt: str, user_prompt: str) -> Iterator[LLMStreamEvent]:
        completion = self.complete_json(system_prompt, user_prompt)
        yield from _completion_stream_events(completion)

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": _llm_user_agent(),
            },
            method="POST",
        )
        last_error: BaseException | None = None
        attempts = self.max_retries + 1
        started_at = time.perf_counter()
        for attempt in range(attempts):
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as response:
                    response_payload = json.loads(response.read().decode("utf-8"))
                break
            except Exception as exc:  # noqa: BLE001 - provider failures are normalized below.
                last_error = exc
                if attempt >= attempts - 1 or not _is_retryable_provider_error(exc):
                    raise RuntimeError(_format_provider_error(exc)) from exc
                time.sleep(min(0.25 * (attempt + 1), 1.0))
        else:
            raise RuntimeError(_format_provider_error(last_error))

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        choice = response_payload["choices"][0]
        message = choice["message"]["content"]
        if isinstance(message, list):
            raw_text = "".join(part.get("text", "") for part in message if isinstance(part, dict))
        else:
            raw_text = str(message)
        parsed = _extract_json_object(raw_text)
        usage = _usage_from_response_payload(response_payload, system_prompt, user_prompt, raw_text)
        return LLMCompletion(
            raw_text=raw_text,
            parsed_json=parsed,
            provider=self.provider_name,
            model=str(response_payload.get("model") or self.model),
            usage=usage,
            estimated_cost_usd=self.pricing.estimate_cost_usd(usage),
            latency_ms=latency_ms,
            request_id=str(response_payload.get("id")) if response_payload.get("id") else None,
            finish_reason=str(choice.get("finish_reason")) if choice.get("finish_reason") else None,
        )


def create_llm_client(provider: str, project_root: Path) -> LLMClient:
    normalized = provider.lower()
    if normalized == "mock":
        return MockLLMClient(project_root=project_root)
    if normalized == "openai-compatible":
        return OpenAICompatibleClient.from_env()
    raise ValueError(f"Unsupported LLM provider: {provider}")


def _completion_stream_events(completion: LLMCompletion) -> Iterator[LLMStreamEvent]:
    yield LLMStreamEvent(
        event="start",
        provider=completion.provider,
        model=completion.model,
    )
    if completion.raw_text:
        yield LLMStreamEvent(
            event="delta",
            provider=completion.provider,
            model=completion.model,
            text_delta=completion.raw_text,
        )
    yield LLMStreamEvent(
        event="complete",
        provider=completion.provider,
        model=completion.model,
        raw_text=completion.raw_text,
        parsed_json=completion.parsed_json,
        usage=completion.usage,
        estimated_cost_usd=completion.estimated_cost_usd,
        latency_ms=completion.latency_ms,
        request_id=completion.request_id,
        finish_reason=completion.finish_reason,
    )


def _extract_json_object(raw_text: str) -> dict | None:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _usage_from_response_payload(
    response_payload: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    raw_text: str,
) -> LLMUsage:
    usage_payload = response_payload.get("usage")
    if isinstance(usage_payload, dict):
        input_tokens = _coerce_non_negative_int(
            usage_payload.get("prompt_tokens", usage_payload.get("input_tokens"))
        )
        output_tokens = _coerce_non_negative_int(
            usage_payload.get("completion_tokens", usage_payload.get("output_tokens"))
        )
        total_tokens = _coerce_non_negative_int(usage_payload.get("total_tokens"))
        if input_tokens is not None or output_tokens is not None or total_tokens is not None:
            return LLMUsage(
                input_tokens=input_tokens or 0,
                output_tokens=output_tokens or 0,
                total_tokens=total_tokens,
                source="provider",
            )
    return estimate_llm_usage(system_prompt, user_prompt, raw_text)


def _env_first(names: list[str], *, default: str | None = None) -> tuple[str | None, str | None]:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value, name
    dotenv_values = _project_dotenv_values()
    for name in names:
        entry = dotenv_values.get(name)
        if entry and entry[0]:
            value, source = entry
            return value, f"{source}:{name}"
    return default, None


def _llm_user_agent() -> str:
    value, _ = _env_first(["NEOFORGE_AGENT_LLM_USER_AGENT", "OPENAI_USER_AGENT"])
    return value or DEFAULT_LLM_USER_AGENT


def _project_dotenv_values() -> dict[str, tuple[str, str]]:
    values: dict[str, tuple[str, str]] = {}
    root = Path(os.environ.get("NEOFORGE_AGENT_ROOT", Path(__file__).resolve().parents[2])).resolve()
    for filename in DOTENV_FILENAMES:
        path = root / filename
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            parsed = _parse_dotenv_line(line)
            if parsed is None:
                continue
            name, value = parsed
            values.setdefault(name, (value, filename))
    return values


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].lstrip()
    if "=" not in stripped:
        return None
    name, value = stripped.split("=", 1)
    name = name.strip()
    value = value.strip()
    if not name:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return name, value


def _normalize_model_name(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    stripped = value.strip()
    if not stripped:
        return stripped, None
    for separator in (";", ","):
        if separator in stripped:
            choices = [part.strip() for part in stripped.split(separator) if part.strip()]
            if choices:
                selected = choices[0]
                return (
                    selected,
                    f"LLM model `{stripped}` contains multiple candidates; using `{selected}` for text planning.",
                )
    return stripped, None


def _parse_positive_int(value: str | None, default: int) -> int | None:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _parse_non_negative_int(value: str | None, default: int) -> int | None:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _parse_optional_non_negative_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _coerce_non_negative_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _is_retryable_provider_error(exc: BaseException) -> bool:
    if isinstance(exc, error.HTTPError):
        return exc.code == 429 or 500 <= exc.code < 600
    return isinstance(exc, (TimeoutError, error.URLError, OSError, json.JSONDecodeError, KeyError, IndexError))


def _format_provider_error(exc: BaseException | None) -> str:
    if exc is None:
        return "LLM provider request failed."
    if isinstance(exc, error.HTTPError):
        return f"LLM provider returned HTTP {exc.code}."
    if isinstance(exc, error.URLError):
        return f"LLM provider request failed: {exc.reason}"
    return f"LLM provider request failed: {exc}"
