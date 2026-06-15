from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib import error

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neoforge_agent import (
    AppConfig,
    LLMProviderConfig,
    LLMUsage,
    LLMProviderRequestError,
    LLMPricing,
    MockLLMClient,
    OpenAICompatibleClient,
    check_llm_provider_health,
    get_llm_provider_metadata,
    inspect_llm_provider_config,
    write_planner_artifacts,
)
from neoforge_agent.llm_client import LLMCompletion
from neoforge_agent.llm_planner import (
    _build_modify_system_prompt,
    _build_system_prompt,
    _decomposed_feature_user_prompt,
    plan_with_decomposed_llm,
    plan_with_llm,
)


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


def ruby_payload() -> dict:
    return {
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


class FencedJsonClient:
    provider_name = "openai-compatible"

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        raw_text = "The plan is:\n```json\n" + json.dumps(ruby_payload(), ensure_ascii=False) + "\n```"
        return LLMCompletion(raw_text=raw_text, parsed_json=None, provider=self.provider_name)


class RetryJsonClient:
    provider_name = "openai-compatible"

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self.calls += 1
        if self.calls == 1:
            return LLMCompletion(raw_text="{not json", parsed_json=None, provider=self.provider_name)
        return LLMCompletion(
            raw_text=json.dumps(ruby_payload(), ensure_ascii=False),
            parsed_json=None,
            provider=self.provider_name,
        )


class SchemaRetryClient:
    provider_name = "openai-compatible"

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self.calls += 1
        if self.calls == 1:
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
                        "behavior": {
                            "type": "right_click_heal",
                            "amount": -1,
                            "cooldown_ticks": 20,
                            "consume": False,
                        },
                    }
                ],
            }
            return LLMCompletion(raw_text=json.dumps(payload), parsed_json=payload, provider=self.provider_name)
        return LLMCompletion(raw_text=json.dumps(ruby_payload()), parsed_json=ruby_payload(), provider=self.provider_name)


class BadDecomposedFeatureClient:
    provider_name = "openai-compatible"

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self.calls += 1
        if "DECOMPOSED_FEATURE_PLAN_V1" in system_prompt:
            payload = {
                "mod_id": "ruby_mod",
                "mod_name": "Ruby Mod",
                "package": "com.generated.ruby_mod",
                "features": [
                    {
                        "type": "item",
                        "id": "ruby",
                        "display_name_en_us": "Ruby",
                        "intent": "Base material item.",
                        "depends_on": [],
                        "fields": {"type": "item", "id": "ruby", "display_name_en_us": "Ruby"},
                    }
                ],
            }
            return LLMCompletion(raw_text=json.dumps(payload), parsed_json=payload, provider=self.provider_name)
        payload = {"note": "not a feature json object"}
        return LLMCompletion(raw_text=json.dumps(payload), parsed_json=payload, provider=self.provider_name)


class FakeProviderResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.status = 200

    def __enter__(self) -> "FakeProviderResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def getcode(self) -> int:
        return self.status


class LLMStabilityTests(unittest.TestCase):
    def test_planner_repairs_markdown_fenced_json_and_writes_stability_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            workspace = Path(tmp) / "workspace"

            spec, artifacts = plan_with_llm("Create a ruby mod with ruby.", FencedJsonClient(), config=config)
            write_planner_artifacts(workspace, config, artifacts)

            self.assertEqual(spec.mod_id, "ruby_mod")
            self.assertTrue(artifacts.json_repair_applied)
            self.assertTrue(any(item["strategy"] == "extract_balanced_object" for item in artifacts.parse_attempts))
            stability_path = workspace / ".agent" / "llm-stability.json"
            self.assertTrue(stability_path.exists())
            stability = json.loads(stability_path.read_text(encoding="utf-8"))
            self.assertTrue(stability["json_repair_applied"])
            self.assertIn("provider_metadata", stability)
            self.assertIn("completion_usage", stability)
            self.assertIn("completion_attempts", stability)

    def test_planner_retries_after_invalid_json(self) -> None:
        client = RetryJsonClient()

        spec, artifacts = plan_with_llm("Create a ruby mod with ruby.", client)

        self.assertEqual(spec.mod_id, "ruby_mod")
        self.assertEqual(client.calls, 2)
        self.assertEqual(artifacts.retry_attempts, 1)
        self.assertTrue(any(not item["success"] for item in artifacts.parse_attempts))

    def test_planner_retries_after_schema_validation_failure(self) -> None:
        client = SchemaRetryClient()

        spec, artifacts = plan_with_llm("Create a ruby charm that heals.", client)

        self.assertEqual(spec.mod_id, "ruby_mod")
        self.assertEqual(client.calls, 2)
        self.assertEqual(artifacts.schema_retry_attempts, 1)
        self.assertTrue(artifacts.schema_validation_attempts)
        self.assertFalse(artifacts.schema_validation_attempts[0]["success"])
        self.assertTrue(artifacts.schema_validation_attempts[-1]["success"])
        self.assertIn("quality", artifacts.rag_quality)

    def test_decomposed_planner_records_bad_feature_raw_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            workspace = Path(tmp) / "workspace"
            client = BadDecomposedFeatureClient()

            spec, artifacts = plan_with_decomposed_llm("Create a ruby mod with ruby.", client, config=config)
            write_planner_artifacts(workspace, config, artifacts)

            self.assertEqual(spec.mod_id, "ruby_mod")
            self.assertEqual(spec.items[0].identifier, "ruby")
            self.assertTrue(artifacts.decomposed_bad_raw_outputs)
            decomposed_dir = workspace / ".agent" / "decomposed-planner"
            self.assertTrue((decomposed_dir / "feature-plan.json").exists())
            self.assertTrue((decomposed_dir / "feature-jsons.json").exists())
            self.assertTrue((decomposed_dir / "bad-raw-outputs.json").exists())

    def test_decomposed_feature_prompt_uses_slim_context(self) -> None:
        sibling_sentinel = "SIBLING_FULL_FIELDS_SHOULD_NOT_LEAK"
        feature_plan = {
            "mod_id": "ruby_mod",
            "mod_name": "Ruby Mod",
            "package": "com.generated.ruby_mod",
            "version": "0.1.0",
            "description": "Synthetic prompt slimming fixture.",
            "authors": ["Codex"],
            "license_name": "MIT",
            "features": [
                {
                    "type": "item",
                    "id": "ruby",
                    "display_name_en_us": "Ruby",
                    "intent": "Material item.",
                    "depends_on": [],
                    "fields": {"huge_payload": sibling_sentinel * 80},
                },
                {
                    "type": "ore",
                    "id": "ruby_ore",
                    "display_name_en_us": "Ruby Ore",
                    "intent": "Overworld ore.",
                    "depends_on": ["ruby"],
                    "fields": {
                        "drop": "ruby_mod:ruby",
                        "worldgen": {
                            "enabled": True,
                            "dimension": "minecraft:overworld",
                            "min_y": -64,
                            "max_y": 32,
                            "vein_size": 6,
                            "veins_per_chunk": 4,
                        },
                    },
                },
            ],
        }

        prompt = _decomposed_feature_user_prompt(
            "Create a ruby mod with ore worldgen.",
            feature_plan,
            feature_plan["features"][1],
        )

        self.assertNotIn("Feature plan JSON:", prompt)
        self.assertNotIn(sibling_sentinel, prompt)
        self.assertIn("Mod metadata JSON:", prompt)
        self.assertIn("Reference map JSON:", prompt)
        self.assertIn("Dependency summary JSON:", prompt)
        self.assertIn("Field contract JSON:", prompt)
        self.assertIn("Target feature plan item JSON:", prompt)
        self.assertIn('"resource_id": "ruby_mod:ruby"', prompt)
        self.assertLess(len(prompt), 4_000)

    def test_system_prompts_include_real_llm_modspec_contract(self) -> None:
        create_prompt = _build_system_prompt("zh_cn")
        modify_prompt = _build_modify_system_prompt("zh_cn")

        expected_contract = [
            "Real LLM planner contract:",
            "Interpret every user request as a request for ModSpec JSON, not source code.",
            "closest supported DSL/template representation",
            "For machines, output one 'machine' feature",
            "For gameplay/progression requests",
            "For recipes, results and keys must use the same mod namespace",
            "top-level extra_notes",
        ]
        for prompt in (create_prompt, modify_prompt):
            for expected in expected_contract:
                self.assertIn(expected, prompt)

        self.assertIn("For patch requests, Interpret every user request", modify_prompt)
        self.assertNotIn("For patch requests, Interpret every user request", create_prompt)

    def test_provider_config_inspection_is_secret_safe(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-env-", dir=TMP_ROOT) as tmp:
            with patch.dict(os.environ, {"NEOFORGE_AGENT_ROOT": tmp}, clear=True):
                missing = inspect_llm_provider_config("openai-compatible")
        self.assertIsInstance(missing, LLMProviderConfig)
        self.assertFalse(missing.valid)
        self.assertFalse(missing.api_key_present)
        self.assertIn("api_key_present", missing.to_dict())
        self.assertNotIn("secret", json.dumps(missing.to_dict()).lower())

        with patch.dict(
            os.environ,
            {
                "NEOFORGE_AGENT_LLM_API_KEY": "secret-test-key",
                "NEOFORGE_AGENT_LLM_MODEL": "test-model",
                "NEOFORGE_AGENT_LLM_BASE_URL": "https://example.invalid/v1",
                "NEOFORGE_AGENT_LLM_TIMEOUT_SECONDS": "12",
                "NEOFORGE_AGENT_LLM_MAX_RETRIES": "3",
            },
            clear=True,
        ):
            configured = inspect_llm_provider_config("openai-compatible")
        self.assertTrue(configured.valid)
        self.assertTrue(configured.api_key_present)
        self.assertEqual(configured.model, "test-model")
        self.assertEqual(configured.timeout_seconds, 12)
        self.assertEqual(configured.max_retries, 3)
        self.assertNotIn("secret-test-key", json.dumps(configured.to_dict()))

    def test_provider_config_uses_first_text_model_from_composite_env_value(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "secret-test-key",
                "OPENAI_MODEL": "gpt-5.5;gpt-image-2",
                "OPENAI_BASE_URL": "https://example.invalid/v1",
            },
            clear=True,
        ):
            configured = inspect_llm_provider_config("openai-compatible")

        self.assertTrue(configured.valid)
        self.assertEqual(configured.model, "gpt-5.5")
        self.assertTrue(any("multiple candidates" in warning for warning in configured.warnings))

    def test_provider_config_reads_project_dotenv_without_overriding_environment(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-env-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            (root / ".env").write_text(
                "\n".join(
                    [
                        "NEOFORGE_AGENT_LLM_BASE_URL=https://env-file.invalid/v1",
                        "NEOFORGE_AGENT_LLM_API_KEY=secret-from-env-file",
                        "NEOFORGE_AGENT_LLM_MODEL=env-file-model",
                        "NEOFORGE_AGENT_LLM_TIMEOUT_SECONDS=30",
                    ]
                ),
                encoding="utf-8",
            )
            (root / ".env.local").write_text(
                "\n".join(
                    [
                        "# Local developer overrides",
                        "NEOFORGE_AGENT_LLM_BASE_URL=https://local-env-file.invalid/v1",
                        "NEOFORGE_AGENT_LLM_API_KEY=\"secret-from-local-env-file\"",
                        "NEOFORGE_AGENT_LLM_MODEL='local-env-file-model'",
                        "NEOFORGE_AGENT_LLM_MAX_RETRIES=5",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"NEOFORGE_AGENT_ROOT": str(root)}, clear=True):
                configured = inspect_llm_provider_config("openai-compatible")

            self.assertTrue(configured.valid)
            self.assertEqual(configured.base_url, "https://local-env-file.invalid/v1")
            self.assertEqual(configured.model, "local-env-file-model")
            self.assertEqual(configured.timeout_seconds, 30)
            self.assertEqual(configured.max_retries, 5)
            self.assertEqual(configured.env_sources["model"], ".env.local:NEOFORGE_AGENT_LLM_MODEL")
            self.assertNotIn("secret-from-local-env-file", json.dumps(configured.to_dict()))

            with patch.dict(
                os.environ,
                {
                    "NEOFORGE_AGENT_ROOT": str(root),
                    "NEOFORGE_AGENT_LLM_MODEL": "environment-model",
                },
                clear=True,
            ):
                overridden = inspect_llm_provider_config("openai-compatible")

            self.assertEqual(overridden.model, "environment-model")
            self.assertEqual(overridden.env_sources["model"], "NEOFORGE_AGENT_LLM_MODEL")

    def test_provider_health_reports_fallback_without_secret_values(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-env-", dir=TMP_ROOT) as tmp:
            with patch.dict(os.environ, {"NEOFORGE_AGENT_ROOT": tmp}, clear=True):
                health = check_llm_provider_health("openai-compatible")

        self.assertFalse(health.healthy)
        self.assertTrue(health.fallback_recommended)
        self.assertFalse(health.can_attempt_request)
        self.assertIn("Missing", " ".join(health.errors))
        self.assertNotIn("secret", json.dumps(health.to_dict()).lower())

    def test_provider_metadata_reports_capabilities_without_secret_values(self) -> None:
        with patch.dict(
            os.environ,
            {
                "NEOFORGE_AGENT_LLM_API_KEY": "secret-test-key",
                "NEOFORGE_AGENT_LLM_MODEL": "test-model",
                "NEOFORGE_AGENT_LLM_BASE_URL": "https://example.invalid/v1",
                "NEOFORGE_AGENT_LLM_TIMEOUT_SECONDS": "10",
                "NEOFORGE_AGENT_LLM_MAX_RETRIES": "4",
            },
            clear=True,
        ):
            metadata = get_llm_provider_metadata("openai-compatible").to_dict()

        self.assertEqual(metadata["provider"], "openai-compatible")
        self.assertEqual(metadata["model"], "test-model")
        self.assertTrue(metadata["capabilities"]["supports_json_mode"])
        self.assertTrue(metadata["capabilities"]["supports_streaming"])
        self.assertEqual(metadata["retry_policy"]["max_retries"], 4)
        self.assertNotIn("secret-test-key", json.dumps(metadata))

    def test_mock_completion_reports_usage_and_zero_cost(self) -> None:
        client = MockLLMClient(PROJECT_ROOT)

        completion = client.complete_json("system prompt", "Create a ruby mod.")

        self.assertEqual(completion.provider, "mock")
        self.assertEqual(completion.model, "mock")
        self.assertIsNotNone(completion.usage)
        self.assertGreater(completion.usage.input_tokens, 0)
        self.assertGreater(completion.usage.output_tokens, 0)
        self.assertEqual(completion.estimated_cost_usd, 0.0)

    def test_stream_json_yields_start_delta_complete_events(self) -> None:
        client = MockLLMClient(PROJECT_ROOT)

        events = list(client.stream_json("system prompt", "Create a ruby mod."))

        self.assertEqual([event.event for event in events], ["start", "delta", "complete"])
        self.assertIn("ruby_mod", events[1].text_delta)
        self.assertIsNotNone(events[-1].parsed_json)
        self.assertIsNotNone(events[-1].usage)

    def test_openai_compatible_metadata_accepts_optional_pricing_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "secret-test-key",
                "OPENAI_MODEL": "gpt-test",
                "OPENAI_BASE_URL": "https://example.invalid/v1",
                "NEOFORGE_AGENT_LLM_INPUT_COST_PER_1M": "2.5",
                "NEOFORGE_AGENT_LLM_OUTPUT_COST_PER_1M": "10",
            },
            clear=True,
        ):
            configured = inspect_llm_provider_config("openai-compatible")
            metadata = get_llm_provider_metadata("openai-compatible")

        self.assertEqual(configured.input_cost_per_1m_tokens, 2.5)
        self.assertEqual(configured.output_cost_per_1m_tokens, 10.0)
        self.assertEqual(metadata.pricing.input_cost_per_1m_tokens, 2.5)
        self.assertEqual(metadata.pricing.output_cost_per_1m_tokens, 10.0)
        self.assertEqual(metadata.pricing.estimate_cost_usd(LLMUsage(input_tokens=1_000_000, output_tokens=2_000_000)), 22.5)

    def test_openai_compatible_completion_records_provider_usage_without_network(self) -> None:
        provider_payload = {
            "id": "chatcmpl-test",
            "model": "gpt-test",
            "choices": [
                {
                    "message": {"content": json.dumps(ruby_payload())},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 34,
                "total_tokens": 46,
            },
        }
        client = OpenAICompatibleClient(
            base_url="https://example.invalid/v1",
            api_key="secret-test-key",
            model="gpt-test",
            pricing=LLMPricing(input_cost_per_1m_tokens=2.0, output_cost_per_1m_tokens=4.0),
        )

        with patch("neoforge_agent.llm_client.request.urlopen", return_value=FakeProviderResponse(provider_payload)):
            completion = client.complete_json("system", "user")

        self.assertEqual(completion.provider, "openai-compatible")
        self.assertEqual(completion.model, "gpt-test")
        self.assertEqual(completion.parsed_json["mod_id"], "ruby_mod")
        self.assertEqual(completion.request_id, "chatcmpl-test")
        self.assertEqual(completion.finish_reason, "stop")
        self.assertEqual(completion.usage.input_tokens, 12)
        self.assertEqual(completion.usage.output_tokens, 34)
        self.assertEqual(completion.usage.resolved_total_tokens(), 46)
        self.assertEqual(completion.usage.source, "provider")
        self.assertEqual(completion.estimated_cost_usd, 0.00016)
        self.assertEqual(len(completion.provider_attempts), 1)
        self.assertTrue(completion.provider_attempts[0]["success"])
        self.assertEqual(completion.telemetry_dict()["provider_attempts"][0]["status_code"], 200)

    def test_openai_compatible_retries_retryable_provider_errors(self) -> None:
        provider_payload = {
            "id": "chatcmpl-retry-test",
            "model": "gpt-test",
            "choices": [{"message": {"content": json.dumps(ruby_payload())}, "finish_reason": "stop"}],
        }
        client = OpenAICompatibleClient(
            base_url="https://example.invalid/v1",
            api_key="secret-test-key",
            model="gpt-test",
            max_retries=4,
        )
        failures = [
            error.HTTPError("https://example.invalid/v1/chat/completions", 500, "server error", {}, None),
            error.HTTPError("https://example.invalid/v1/chat/completions", 524, "timeout", {}, None),
            FakeProviderResponse(provider_payload),
        ]

        with patch("neoforge_agent.llm_client.request.urlopen", side_effect=failures), patch("neoforge_agent.llm_client.time.sleep") as sleep:
            completion = client.complete_json("system", "user")

        self.assertEqual(completion.parsed_json["mod_id"], "ruby_mod")
        self.assertEqual([attempt["success"] for attempt in completion.provider_attempts], [False, False, True])
        self.assertEqual([attempt.get("status_code") for attempt in completion.provider_attempts[:2]], [500, 524])
        self.assertEqual(sleep.call_count, 2)

    def test_openai_compatible_retry_exhaustion_raises_provider_error(self) -> None:
        client = OpenAICompatibleClient(
            base_url="https://example.invalid/v1",
            api_key="secret-test-key",
            model="gpt-test",
            max_retries=1,
        )
        failure = error.HTTPError("https://example.invalid/v1/chat/completions", 500, "server error", {}, None)

        with patch("neoforge_agent.llm_client.request.urlopen", side_effect=[failure, failure]), patch("neoforge_agent.llm_client.time.sleep"):
            with self.assertRaises(LLMProviderRequestError) as raised:
                client.complete_json("system", "user")

        exc = raised.exception
        self.assertEqual(exc.status_code, 500)
        self.assertTrue(exc.retryable)
        self.assertEqual(exc.attempts, 2)
        self.assertEqual(len(exc.attempt_summaries), 2)
        self.assertNotIn("secret-test-key", json.dumps(exc.to_dict()))


if __name__ == "__main__":
    unittest.main()
