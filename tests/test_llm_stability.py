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
    LLMNormalizationResult,
    LLMProviderConfig,
    LLMUsage,
    LLMProviderRequestError,
    LLMPricing,
    MockLLMClient,
    ModSpec,
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
    _harden_decomposed_composed_features,
    _parse_or_repair_llm_json,
    plan_with_decomposed_llm,
    plan_with_llm,
)
from neoforge_agent.llm_output_normalizer import (
    DECOMPOSED_PLANNER_NORMALIZATION,
    _normalize_behavior,
    _normalize_content_feature,
    normalize_llm_modspec_output,
    normalize_llm_patch_output,
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


class ParsedWrapperClient:
    provider_name = "openai-compatible"

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        payload = {"modspec": ruby_payload()}
        return LLMCompletion(
            raw_text=json.dumps(payload, ensure_ascii=False),
            parsed_json=payload,
            provider=self.provider_name,
        )


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


class AlwaysBadJsonClient:
    provider_name = "openai-compatible"

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self.calls += 1
        return LLMCompletion(
            raw_text=f"I cannot return JSON on call {self.calls}.",
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


class RealProviderLikeBadDecomposedClient:
    provider_name = "openai-compatible"

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        if "DECOMPOSED_FEATURE_PLAN_V1" in system_prompt:
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
                        "depends_on": [],
                        "fields": {"type": "item", "id": "ruby", "display_name_en_us": "Ruby"},
                    },
                    {
                        "type": "ore",
                        "id": "ruby_ore",
                        "display_name_en_us": "Ruby Ore",
                        "depends_on": [],
                        "fields": {"type": "ore", "id": "ruby_ore", "display_name_en_us": "Ruby Ore"},
                    },
                    {
                        "type": "machine",
                        "id": "compressor",
                        "display_name_en_us": "Compressor",
                        "depends_on": ["ruby"],
                        "fields": {"type": "machine", "id": "compressor", "display_name_en_us": "Compressor"},
                    },
                    {
                        "type": "recipe",
                        "id": "compressor_craft",
                        "display_name_en_us": "Compressor Crafting",
                        "depends_on": ["ruby"],
                        "fields": {"type": "recipe", "id": "compressor_craft", "display_name_en_us": "Compressor Crafting"},
                    },
                    {
                        "type": "recipe",
                        "id": "ruby_compressing",
                        "display_name_en_us": "Ruby Compressing",
                        "depends_on": ["compressor", "ruby_ore"],
                        "fields": {"type": "recipe", "id": "ruby_compressing", "display_name_en_us": "Ruby Compressing"},
                    },
                    {
                        "type": "progression",
                        "id": "ruby_progression",
                        "display_name_en_us": "Ruby Progression",
                        "depends_on": ["ruby_ore", "ruby", "compressor"],
                        "fields": {"type": "progression", "id": "ruby_progression", "display_name_en_us": "Ruby Progression"},
                    },
                ],
            }
            return LLMCompletion(raw_text=json.dumps(payload), parsed_json=payload, provider=self.provider_name)

        target = json.loads(user_prompt.split("Target feature plan item JSON:\n", 1)[1].split("\n\nReturn only", 1)[0])
        feature_type = target["type"]
        feature_id = target["id"]
        payload: dict
        if feature_type == "ore":
            payload = {
                "type": "ore",
                "id": feature_id,
                "display_name_en_us": "Ruby Ore",
                "drop": None,
                "worldgen": {
                    "enabled": True,
                    "dimension": "overworld",
                    "min_y": -64,
                    "max_y": 32,
                    "vein_size": 6,
                    "veins_per_chunk": 4,
                },
            }
        elif feature_id == "compressor_craft":
            payload = {
                "type": "recipe",
                "id": feature_id,
                "display_name_en_us": "Compressor Crafting",
                "recipe_type": "crafting_shaped",
            }
        elif feature_id == "ruby_compressing":
            payload = {
                "type": "recipe",
                "id": feature_id,
                "display_name_en_us": "Ruby Compressing",
                "recipe_type": "compressor",
            }
        elif feature_type == "progression":
            payload = {
                "type": "progression",
                "id": feature_id,
                "title": "Ruby Progression",
                "entry_stage": "start",
                "end_stage": "mastery",
                "stages": [
                    {
                        "id": "start",
                        "type": "start",
                        "title": "Start",
                        "provides": ["ruby_ore_discovery"],
                        "evidence": "采集红宝石矿石",
                    },
                    {
                        "id": "mastery",
                        "type": "end",
                        "title": "Mastery",
                        "evidence": "制作全套红宝石工具",
                    },
                ],
            }
        elif feature_type == "machine":
            payload = {
                "type": "machine",
                "id": feature_id,
                "display_name_en_us": "Compressor",
                "machine_kind": "compressor",
            }
        else:
            payload = {
                "type": feature_type,
                "id": feature_id,
                "display_name_en_us": target.get("display_name_en_us", "Feature"),
            }
        return LLMCompletion(raw_text=json.dumps(payload, ensure_ascii=False), parsed_json=payload, provider=self.provider_name)


class FragmentedProgressionDecomposedClient:
    provider_name = "openai-compatible"

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        if "DECOMPOSED_FEATURE_PLAN_V1" in system_prompt:
            payload = {
                "mod_id": "ruby_mod",
                "mod_name": "Ruby Mod",
                "package": "com.generated.ruby_mod",
                "features": [
                    {"type": "item", "id": "ruby", "display_name_en_us": "Ruby"},
                    {"type": "ore", "id": "ruby_ore", "display_name_en_us": "Ruby Ore", "fields": {"drop": "ruby_mod:ruby"}},
                    {"type": "machine", "id": "compressor", "display_name_en_us": "Compressor"},
                    {"type": "tool", "id": "ruby_pickaxe", "display_name_en_us": "Ruby Pickaxe", "fields": {"tool_type": "pickaxe", "tool_material": "ruby"}},
                    {
                        "type": "sword",
                        "id": "ruby_sword",
                        "display_name_en_us": "Ruby Sword",
                        "fields": {"tool_material": "ruby", "behavior": {"type": ""}},
                    },
                    {
                        "type": "progression",
                        "id": "obtain_ruby",
                        "display_name_en_us": "Obtain Ruby",
                        "depends_on": ["ruby"],
                        "fields": {"stage_type": "material"},
                    },
                    {
                        "type": "progression",
                        "id": "craft_compressor",
                        "display_name_en_us": "Craft Compressor",
                        "depends_on": ["compressor"],
                        "fields": {"stage_type": "machine"},
                    },
                    {
                        "type": "progression",
                        "id": "craft_ruby_tools",
                        "display_name_en_us": "Craft Ruby Tools",
                        "depends_on": ["ruby_pickaxe", "ruby_sword"],
                        "fields": {"stage_type": "equipment"},
                    },
                ],
            }
            return LLMCompletion(raw_text=json.dumps(payload), parsed_json=payload, provider=self.provider_name)

        target = json.loads(user_prompt.split("Target feature plan item JSON:\n", 1)[1].split("\n\nReturn only", 1)[0])
        feature = dict(target.get("fields", {}))
        feature.setdefault("type", target["type"])
        feature.setdefault("id", target["id"])
        feature.setdefault("display_name_en_us", target.get("display_name_en_us", "Feature"))
        if feature["type"] == "ore":
            feature.setdefault(
                "worldgen",
                {"enabled": True, "dimension": "minecraft:overworld", "min_y": -64, "max_y": 32, "vein_size": 6, "veins_per_chunk": 4},
            )
        if feature["type"] == "machine":
            feature.setdefault("machine_kind", "compressor")
        return LLMCompletion(raw_text=json.dumps(feature), parsed_json=feature, provider=self.provider_name)


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
            self.assertTrue(any(item["strategy"] == "strip_markdown_fence" for item in artifacts.parse_attempts))
            stability_path = workspace / ".agent" / "llm-stability.json"
            self.assertTrue(stability_path.exists())
            stability = json.loads(stability_path.read_text(encoding="utf-8"))
            self.assertTrue(stability["json_repair_applied"])
            self.assertIn("provider_metadata", stability)
            self.assertIn("completion_usage", stability)
            self.assertIn("completion_attempts", stability)

    def test_planner_extracts_json_from_prose_wrapped_fence(self) -> None:
        raw_text = "Sure, here is the JSON:\n```json\n" + json.dumps(ruby_payload()) + "\n```\nDone."

        parsed, attempts, repaired = _parse_or_repair_llm_json(raw_text)

        self.assertTrue(repaired)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["mod_id"], "ruby_mod")
        self.assertTrue(any(item["strategy"] == "strip_markdown_fence" and item["success"] for item in attempts))

    def test_planner_extracts_json_from_fenced_common_wrapper(self) -> None:
        raw_text = "```json\n" + json.dumps({"modspec": ruby_payload()}) + "\n```"

        parsed, attempts, repaired = _parse_or_repair_llm_json(raw_text)

        self.assertTrue(repaired)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["mod_id"], "ruby_mod")
        self.assertTrue(any(item["strategy"] == "unwrap_modspec" and item["success"] for item in attempts))

    def test_planner_unwraps_common_modspec_json_wrapper(self) -> None:
        raw_text = json.dumps({"modspec": ruby_payload()})

        parsed, attempts, repaired = _parse_or_repair_llm_json(raw_text)

        self.assertTrue(repaired)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["mod_id"], "ruby_mod")
        self.assertTrue(any(item["strategy"] == "unwrap_modspec" and item["success"] for item in attempts))

    def test_planner_unwraps_provider_parsed_common_wrapper(self) -> None:
        client = ParsedWrapperClient()

        spec, artifacts = plan_with_llm("Create a ruby mod with ruby.", client)

        self.assertEqual(spec.mod_id, "ruby_mod")
        self.assertTrue(artifacts.json_repair_applied)
        self.assertTrue(any(item["strategy"] == "unwrap_modspec" and item["success"] for item in artifacts.parse_attempts))

    def test_planner_writes_bad_json_raw_outputs_on_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            workspace = Path(tmp) / "workspace"
            client = AlwaysBadJsonClient()

            with patch.dict(os.environ, {"NEOFORGE_AGENT_LLM_RETRIES": "1"}):
                with self.assertRaises(Exception) as raised:
                    plan_with_llm("Create a ruby mod with ruby.", client, config=config)

            artifacts = raised.exception.artifacts
            write_planner_artifacts(workspace, config, artifacts)

            agent_dir = workspace / ".agent"
            bad_outputs = agent_dir / "llm-bad-json-outputs.json"
            bad_raw = agent_dir / "llm-bad-json-output" / "01-bad-json-output.txt"
            stability = json.loads((agent_dir / "llm-stability.json").read_text(encoding="utf-8"))
            self.assertEqual(client.calls, 2)
            self.assertTrue(bad_outputs.exists())
            self.assertTrue(bad_raw.exists())
            self.assertIn("I cannot return JSON", bad_raw.read_text(encoding="utf-8"))
            self.assertEqual(stability["bad_json_outputs_count"], 2)

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

    def test_llm_normalization_returns_named_result(self) -> None:
        config = AppConfig.default()

        result = normalize_llm_modspec_output(ruby_payload(), "Create a ruby mod with ruby.", config)

        self.assertIsInstance(result, LLMNormalizationResult)
        self.assertEqual(result.normalized_json["mod_id"], "ruby_mod")
        self.assertEqual(result.normalized_json["features"][0]["id"], "ruby")
        self.assertIsInstance(result.warnings, list)

        existing = ModSpec.from_dict(result.normalized_json)
        patch_result = normalize_llm_patch_output(
            {
                "features": [
                    {
                        "type": "item",
                        "id": "ruby_dust",
                        "display_name_en_us": "Ruby Dust",
                    }
                ]
            },
            existing,
            "Add ruby dust.",
            config,
        )

        self.assertIsInstance(patch_result, LLMNormalizationResult)
        self.assertEqual(patch_result.normalized_json["mod_id"], existing.mod_id)
        self.assertEqual(patch_result.normalized_json["features"][0]["id"], "ruby_dust")

    def test_decomposed_planner_uses_named_normalization_facade(self) -> None:
        expanded = DECOMPOSED_PLANNER_NORMALIZATION.expand_typed_feature_lists(
            {
                "items": [{"id": "ruby"}],
                "machines": [{"id": "compressor"}],
            }
        )

        self.assertEqual([feature["type"] for feature in expanded], ["item", "machine"])
        self.assertIn("compressor", DECOMPOSED_PLANNER_NORMALIZATION.supported_machine_kinds)
        self.assertEqual(DECOMPOSED_PLANNER_NORMALIZATION.normalize_behavior_type_alias("heal"), "right_click_heal")
        self.assertEqual(
            DECOMPOSED_PLANNER_NORMALIZATION.recipe_result_reference({"item": "ruby_mod:ruby", "count": 1}),
            "ruby_mod:ruby",
        )
        self.assertTrue(DECOMPOSED_PLANNER_NORMALIZATION.is_blank_value(""))

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

    def test_decomposed_planner_hardens_real_provider_schema_drift(self) -> None:
        client = RealProviderLikeBadDecomposedClient()

        spec, artifacts = plan_with_decomposed_llm(
            "Create a ruby progression gameplay loop with ruby ore worldgen in the overworld, "
            "a compressor machine, ruby tools, recipes, and an auditable progression report.",
            client,
        )

        self.assertEqual(spec.mod_id, "ruby_mod")
        self.assertEqual(spec.machines[0].identifier, "ruby_compressor")
        self.assertEqual(spec.ores[0].drop, "ruby_mod:ruby")
        self.assertEqual(spec.ores[0].worldgen.dimension, "minecraft:overworld")
        self.assertEqual({recipe.recipe_type for recipe in spec.recipes}, {"shapeless"})
        self.assertIn("ruby_mod:ruby_compressor", {recipe.result for recipe in spec.recipes})
        self.assertTrue(spec.progressions)
        self.assertEqual(
            {stage.stage_type for stage in spec.progressions[0].stages},
            {"milestone"},
        )
        self.assertTrue(any("normalized" in warning for warning in artifacts.warnings))
        self.assertTrue(artifacts.schema_validation_attempts[-1]["success"])

    def test_decomposed_planner_collapses_progression_fragments(self) -> None:
        client = FragmentedProgressionDecomposedClient()

        spec, artifacts = plan_with_decomposed_llm(
            "Create a ruby progression gameplay loop with ruby ore worldgen in the overworld, "
            "a compressor machine, ruby tools, recipes, and an auditable progression report.",
            client,
        )

        self.assertEqual(spec.machines[0].identifier, "ruby_compressor")
        self.assertEqual(len(spec.progressions), 1)
        self.assertEqual(spec.progressions[0].identifier, "ruby_progression")
        self.assertGreaterEqual(len(spec.progressions[0].stages), 3)
        self.assertIsNone(spec.swords[0].behavior)
        self.assertTrue(any("Collapsed" in warning for warning in artifacts.warnings))
        self.assertTrue(any("empty behavior type" in warning for warning in artifacts.warnings))
        self.assertTrue(artifacts.schema_validation_attempts[-1]["success"])

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

    def test_behavior_normalization_accepts_real_provider_aliases(self) -> None:
        normalized = _normalize_behavior(
            {
                "type": "right_click_heal",
                "heal_amount": 4,
                "cooldown_seconds": 20,
            }
        )

        self.assertEqual(normalized["amount"], 4.0)
        self.assertEqual(normalized["cooldown_ticks"], 400)

        hardened, warnings = _harden_decomposed_composed_features(
            [{"type": "item", "id": "ruby_charm", "behavior": {"type": "heal", "amount": 4}}],
            {"mod_id": "ruby_mod", "features": [{"type": "item", "id": "ruby_charm"}]},
        )
        self.assertEqual(hardened[0]["behavior"]["type"], "right_click_heal")
        self.assertTrue(any("behavior type 'heal' normalized" in warning for warning in warnings))

    def test_item_normalization_accepts_right_click_behavior_alias(self) -> None:
        warnings: list[str] = []
        normalized = _normalize_content_feature(
            {
                "type": "item",
                "id": "ruby_charm",
                "display_name_en_us": "Ruby Charm",
                "right_click_behavior": {
                    "type": "heal",
                    "amount": 4,
                    "cooldown_seconds": 20,
                },
            },
            "item",
            warnings,
        )

        self.assertIsNotNone(normalized)
        behavior = normalized["behavior"]
        self.assertEqual(behavior["type"], "right_click_heal")
        self.assertEqual(behavior["amount"], 4.0)
        self.assertEqual(behavior["cooldown_ticks"], 400)

    def test_item_normalization_accepts_string_behavior_with_top_level_aliases(self) -> None:
        warnings: list[str] = []
        normalized = _normalize_content_feature(
            {
                "type": "item",
                "id": "ruby_charm",
                "display_name_en_us": "Ruby Charm",
                "behavior": "right_click_heal",
                "heal_amount": 4,
                "cooldown_seconds": 20,
            },
            "item",
            warnings,
        )

        self.assertIsNotNone(normalized)
        behavior = normalized["behavior"]
        self.assertEqual(behavior["type"], "right_click_heal")
        self.assertEqual(behavior["amount"], 4.0)
        self.assertEqual(behavior["cooldown_ticks"], 400)

    def test_item_normalization_accepts_nested_right_click_behavior_alias(self) -> None:
        warnings: list[str] = []
        normalized = _normalize_content_feature(
            {
                "type": "item",
                "id": "ruby_charm",
                "display_name_en_us": "Ruby Charm",
                "behavior": {
                    "right_click": {
                        "heal": 4,
                        "cooldown": 20,
                    },
                },
            },
            "item",
            warnings,
        )

        self.assertIsNotNone(normalized)
        behavior = normalized["behavior"]
        self.assertEqual(behavior["type"], "right_click_heal")
        self.assertEqual(behavior["amount"], 4.0)
        self.assertEqual(behavior["cooldown_ticks"], 400)

    def test_item_normalization_accepts_nested_right_click_effect_alias(self) -> None:
        warnings: list[str] = []
        normalized = _normalize_content_feature(
            {
                "type": "item",
                "id": "ruby_charm",
                "display_name_en_us": "Ruby Charm",
                "behavior": {
                    "right_click": {
                        "apply_effect": {
                            "effect": "minecraft:regeneration",
                            "duration": 8,
                        },
                        "cooldown_seconds": 20,
                    },
                },
            },
            "item",
            warnings,
        )

        self.assertIsNotNone(normalized)
        behavior = normalized["behavior"]
        self.assertEqual(behavior["type"], "right_click_effect")
        self.assertEqual(behavior["effect"], "minecraft:regeneration")
        self.assertEqual(behavior["duration_ticks"], 160)
        self.assertEqual(behavior["cooldown_ticks"], 400)

    def test_tool_material_object_infers_material_from_identifier(self) -> None:
        warnings: list[str] = []
        normalized = _normalize_content_feature(
            {
                "type": "tool",
                "id": "ruby_pickaxe",
                "display_name_en_us": "Ruby Pickaxe",
                "tool_type": "pickaxe",
                "tool_material": {
                    "durability": 1561,
                    "mining_speed": 8.0,
                    "attack_damage_bonus": 3.0,
                    "enchantability": 10,
                },
            },
            "tool",
            warnings,
        )

        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["tool_material"], "ruby")
        self.assertTrue(any("inferred 'ruby'" in warning for warning in warnings))

    def test_decomposed_recipe_aliases_canonicalize_to_result_id(self) -> None:
        feature_plan = {
            "mod_id": "ruby_mod",
            "features": [
                {"type": "item", "id": "ruby"},
                {"type": "tool", "id": "ruby_pickaxe"},
                {"type": "recipe", "id": "ruby_pickaxe_recipe"},
            ],
        }
        features = [
            {"type": "item", "id": "ruby"},
            {"type": "tool", "id": "ruby_pickaxe"},
            {
                "type": "recipe",
                "id": "ruby_pickaxe_recipe",
                "recipe_type": "shaped",
                "pattern": ["RRR", " S ", " S "],
                "key": {"R": {"item": "ruby_mod:ruby"}, "S": {"item": "minecraft:stick"}},
                "result": {"item": "ruby_mod:ruby_pickaxe", "count": 1},
            },
        ]

        hardened, warnings = _harden_decomposed_composed_features(features, feature_plan)
        recipe = next(feature for feature in hardened if feature["type"] == "recipe")

        self.assertEqual(recipe["id"], "ruby_pickaxe")
        self.assertEqual(recipe["result"], "ruby_mod:ruby_pickaxe")
        self.assertEqual(recipe["count"], 1)
        self.assertEqual(recipe["keys"], {"R": "ruby_mod:ruby", "S": "minecraft:stick"})
        self.assertTrue(any("normalized to 'keys'" in warning for warning in warnings))
        self.assertTrue(any("id normalized to 'ruby_pickaxe'" in warning for warning in warnings))

    def test_decomposed_drops_recipe_with_missing_internal_dependency(self) -> None:
        feature_plan = {
            "mod_id": "ruby_mod",
            "features": [
                {"type": "item", "id": "ruby"},
                {
                    "type": "recipe",
                    "id": "ruby_helmet_recipe",
                    "depends_on": ["ruby", "ruby_helmet"],
                },
            ],
        }
        features = [
            {"type": "item", "id": "ruby", "display_name_en_us": "Ruby"},
            {
                "type": "recipe",
                "id": "ruby_helmet_recipe",
                "recipe_type": "shaped",
                "pattern": ["###", "# #"],
                "keys": {"#": "ruby"},
                "result": "ruby_helmet",
            },
        ]

        hardened, warnings = _harden_decomposed_composed_features(features, feature_plan)

        self.assertEqual([feature["id"] for feature in hardened], ["ruby"])
        self.assertTrue(any("missing internal dependency" in warning for warning in warnings))

    def test_decomposed_recipe_canonicalizes_vanilla_stick_reference(self) -> None:
        feature_plan = {
            "mod_id": "ruby_mod",
            "features": [
                {"type": "item", "id": "ruby"},
                {"type": "sword", "id": "ruby_sword"},
                {
                    "type": "recipe",
                    "id": "ruby_sword_recipe",
                    "depends_on": ["ruby", "ruby_sword"],
                },
            ],
        }
        features = [
            {"type": "item", "id": "ruby"},
            {"type": "sword", "id": "ruby_sword"},
            {
                "type": "recipe",
                "id": "ruby_sword_recipe",
                "recipe_type": "shaped",
                "pattern": [" # ", " # ", " / "],
                "keys": {"#": "ruby", "/": "stick"},
                "result": "ruby_sword",
            },
        ]

        hardened, _ = _harden_decomposed_composed_features(features, feature_plan)

        recipe = next(feature for feature in hardened if feature["type"] == "recipe")
        self.assertEqual(recipe["keys"]["/"], "minecraft:stick")

    def test_decomposed_recipe_id_collision_keeps_unique_identifiers(self) -> None:
        feature_plan = {
            "mod_id": "ruby_mod",
            "features": [
                {"type": "item", "id": "ruby"},
                {"type": "recipe", "id": "ruby_helmet_recipe", "depends_on": ["ruby"]},
                {"type": "recipe", "id": "ruby_chestplate_recipe", "depends_on": ["ruby"]},
            ],
        }
        features = [
            {"type": "item", "id": "ruby"},
            {
                "type": "recipe",
                "id": "ruby_helmet_recipe",
                "recipe_type": "shapeless",
                "ingredients": ["ruby"],
                "result": "ruby",
            },
            {
                "type": "recipe",
                "id": "ruby_chestplate_recipe",
                "recipe_type": "shapeless",
                "ingredients": ["ruby"],
                "result": "ruby",
            },
        ]

        hardened, warnings = _harden_decomposed_composed_features(features, feature_plan)

        recipe_ids = [feature["id"] for feature in hardened if feature["type"] == "recipe"]
        self.assertEqual(len(recipe_ids), len(set(recipe_ids)))
        self.assertIn("ruby_chestplate_recipe", recipe_ids)
        self.assertTrue(any("recipe id collision" in warning for warning in warnings))

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

    def test_openai_compatible_response_format_can_be_disabled_for_provider_compatibility(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "secret-test-key",
                "OPENAI_MODEL": "gpt-test",
                "OPENAI_BASE_URL": "https://example.invalid/v1",
                "NEOFORGE_AGENT_LLM_RESPONSE_FORMAT": "none",
            },
            clear=True,
        ):
            configured = inspect_llm_provider_config("openai-compatible")
            metadata = get_llm_provider_metadata("openai-compatible")

        self.assertEqual(configured.response_format, "none")
        self.assertEqual(configured.env_sources["response_format"], "NEOFORGE_AGENT_LLM_RESPONSE_FORMAT")
        self.assertEqual(metadata.default_options.response_format, "none")

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

    def test_openai_compatible_completion_does_not_stringify_null_content(self) -> None:
        provider_payload = {
            "id": "chatcmpl-null-content-test",
            "model": "deepseek-test",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning_content": "internal reasoning should not be treated as planner output",
                    },
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
            model="deepseek-test",
        )

        with patch("neoforge_agent.llm_client.request.urlopen", return_value=FakeProviderResponse(provider_payload)):
            completion = client.complete_json("system", "user")

        self.assertEqual(completion.raw_text, "")
        self.assertIsNone(completion.parsed_json)
        attempt = completion.telemetry_dict()["provider_attempts"][0]
        self.assertEqual(attempt["message_content_type"], "NoneType")
        self.assertTrue(attempt["message_content_empty"])
        self.assertTrue(attempt["message_has_reasoning_content"])
        self.assertEqual(attempt["response_text_source"], "none")
        self.assertEqual(attempt["response_text_chars"], 0)

    def test_openai_compatible_completion_omits_response_format_when_disabled(self) -> None:
        provider_payload = {
            "id": "chatcmpl-no-json-mode-test",
            "model": "gpt-test",
            "choices": [{"message": {"content": json.dumps(ruby_payload())}, "finish_reason": "stop"}],
        }
        captured_payloads: list[dict] = []
        client = OpenAICompatibleClient(
            base_url="https://example.invalid/v1",
            api_key="secret-test-key",
            model="gpt-test",
            response_format="none",
        )

        def fake_urlopen(req, timeout):  # noqa: ANN001 - urllib test double.
            captured_payloads.append(json.loads(req.data.decode("utf-8")))
            return FakeProviderResponse(provider_payload)

        with patch("neoforge_agent.llm_client.request.urlopen", side_effect=fake_urlopen):
            completion = client.complete_json("system", "user")

        self.assertEqual(completion.parsed_json["mod_id"], "ruby_mod")
        self.assertNotIn("response_format", captured_payloads[0])

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
