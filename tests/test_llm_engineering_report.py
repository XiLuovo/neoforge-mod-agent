from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neoforge_agent import AppConfig, LLMEngineeringReportRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class LLMEngineeringReportTests(unittest.TestCase):
    def test_llm_engineering_report_writes_prompt_provider_and_reliability_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            workspace_root = Path(tmp)
            config = test_config(workspace_root)
            project_dir = workspace_root / "sample-llm-run"
            agent_dir = project_dir / ".agent"
            agent_dir.mkdir(parents=True)
            prompt_trace = [
                {
                    "role": "planner_agent",
                    "planner_mode": "llm",
                    "provider": "mock",
                    "prompt_kind": "generate_modspec",
                    "system_prompt": "Return ModSpec JSON only.",
                    "input_text": "Create a ruby mod.",
                    "raw_text": "{\"mod_id\":\"ruby_mod\"}",
                    "normalized_json": {"mod_id": "ruby_mod"},
                    "warnings": ["provider fallback not needed"],
                    "parse_attempts": [{"attempt": 1, "status": "ok"}],
                    "retry_attempts": 2,
                    "schema_retry_attempts": 1,
                    "schema_validation_attempts": [{"attempt": 1, "valid": False}, {"attempt": 2, "valid": True}],
                    "json_repair_applied": True,
                    "provider_config": {"provider": "mock", "valid": True, "model": "mock"},
                    "provider_health": {"healthy": True, "fallback_recommended": True, "warnings": ["fallback path observed"]},
                    "provider_metadata": {
                        "model": "mock",
                        "display_name": "Mock LLM",
                        "default_options": {
                            "response_format": "json_object",
                            "temperature": 0.1,
                            "stream": False,
                            "timeout_seconds": 30,
                            "max_retries": 2,
                        },
                        "capabilities": {"json_mode": True},
                        "retry_policy": {"max_retries": 2},
                        "pricing": {"input_per_million": 0.0, "output_per_million": 0.0},
                    },
                    "completion_usage": {
                        "model": "mock",
                        "usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
                        "estimated_cost_usd": 0.0,
                    },
                }
            ]
            (agent_dir / "prompt-trace.json").write_text(json.dumps(prompt_trace), encoding="utf-8")
            (agent_dir / "llm-stability.json").write_text(
                json.dumps(
                    {
                        "provider": "mock",
                        "provider_config": {"provider": "mock", "valid": True, "model": "mock"},
                        "provider_health": {"healthy": True},
                        "provider_metadata": {
                            "model": "mock",
                            "display_name": "Mock LLM",
                            "default_options": {"temperature": 0.1},
                        },
                        "completion_usage": {
                            "model": "mock",
                            "usage": {"input_tokens": 4, "output_tokens": 3, "total_tokens": 7},
                            "estimated_cost_usd": 0.0,
                        },
                        "retry_attempts": 1,
                        "schema_retry_attempts": 1,
                        "schema_validation_attempts": [{"attempt": 1, "valid": True}],
                        "json_repair_applied": True,
                        "parse_attempts": [{"attempt": 1, "status": "ok"}],
                    }
                ),
                encoding="utf-8",
            )

            result = LLMEngineeringReportRunner(config).run(project_dir, run_name="unit-llm-engineering")

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["prompt_traces_count"], 1)
            self.assertEqual(result.metrics["providers"], ["mock"])
            self.assertEqual(result.metrics["models"], ["mock"])
            self.assertEqual(result.metrics["retry_attempts_total"], 2)
            self.assertEqual(result.metrics["schema_retry_attempts_total"], 1)
            self.assertEqual(result.metrics["json_repair_applied_count"], 1)
            self.assertTrue(result.metrics["fallback_detected"])
            self.assertEqual(result.usage_summary["input_tokens"], 12)
            self.assertEqual(result.usage_summary["output_tokens"], 8)
            self.assertEqual(result.usage_summary["total_tokens"], 20)
            self.assertEqual(result.prompt_records[0]["response_format"], "json_object")
            self.assertEqual(result.prompt_records[0]["temperature"], 0.1)
            self.assertTrue(result.llm_engineering_report_json_path.exists())
            self.assertTrue(result.llm_engineering_report_md_path.exists())

            payload = json.loads(result.llm_engineering_report_json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["metrics"]["usage_events_count"], 1)
            self.assertEqual(payload["reliability_summary"]["schema_validation_attempts_count"], 2)

    def test_llm_engineering_report_can_fall_back_to_stability_artifact_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            workspace_root = Path(tmp)
            config = test_config(workspace_root)
            agent_dir = workspace_root / "stability-only" / ".agent"
            agent_dir.mkdir(parents=True)
            (agent_dir / "llm-stability.json").write_text(
                json.dumps(
                    {
                        "provider": "mock",
                        "completion_usage": {
                            "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
                            "estimated_cost_usd": 0.0,
                        },
                        "retry_attempts": 1,
                        "schema_retry_attempts": 0,
                        "parse_attempts": [{"attempt": 1, "status": "ok"}],
                    }
                ),
                encoding="utf-8",
            )

            result = LLMEngineeringReportRunner(config).run(agent_dir / "llm-stability.json", run_name="unit-stability-only")

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["prompt_traces_count"], 0)
            self.assertEqual(result.usage_summary["usage_events_count"], 1)
            self.assertEqual(result.usage_summary["total_tokens"], 5)
            self.assertEqual(result.reliability_summary["retry_attempts_total"], 1)
            self.assertTrue(result.llm_engineering_report_json_path.exists())


if __name__ == "__main__":
    unittest.main()
