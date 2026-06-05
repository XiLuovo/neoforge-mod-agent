from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neoforge_agent import AppConfig, RealLLMStabilityRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root, project_root=workspace_root)


class RealLLMStabilityTests(unittest.TestCase):
    def test_real_llm_stability_runs_offline_mock_sample(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = RealLLMStabilityRunner(config).run(
                run_name="unit-real-llm-stability-mock",
                llm_provider="mock",
                limit=1,
                run_build=False,
                run_audit=True,
                fallback_probe=True,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["total_cases"], 1)
            self.assertEqual(result.metrics["strict_success_count"], 1)
            self.assertEqual(result.metrics["real_llm_success_count"], 0)
            self.assertEqual(result.cases[0].outcome, "mock_success")
            self.assertTrue(result.real_llm_stability_json_path.exists())
            self.assertTrue(result.real_llm_stability_md_path.exists())

    def test_real_llm_stability_classifies_missing_provider_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            with patch.dict(os.environ, {"NEOFORGE_AGENT_ROOT": tmp}, clear=True):
                result = RealLLMStabilityRunner(config).run(
                    run_name="unit-real-llm-stability-missing-provider",
                    llm_provider="openai-compatible",
                    limit=1,
                    run_build=False,
                    run_audit=True,
                    fallback_probe=True,
                )

            self.assertTrue(result.success)
            self.assertEqual(result.metrics["total_cases"], 1)
            self.assertEqual(result.metrics["real_llm_success_count"], 0)
            self.assertEqual(result.metrics["provider_failure_count"], 1)
            self.assertEqual(result.metrics["fallback_success_count"], 1)
            self.assertEqual(result.cases[0].failure_type, "provider_failure")
            self.assertEqual(result.cases[0].outcome, "fallback_success")
            self.assertTrue(result.cases[0].fallback_used)
            self.assertTrue(result.cases[0].fallback_success)

    def test_real_llm_stability_require_real_fails_when_provider_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            with patch.dict(os.environ, {"NEOFORGE_AGENT_ROOT": tmp}, clear=True):
                result = RealLLMStabilityRunner(config).run(
                    run_name="unit-real-llm-stability-require-real",
                    llm_provider="openai-compatible",
                    limit=1,
                    run_build=False,
                    run_audit=True,
                    fallback_probe=False,
                    require_real=True,
                )

            self.assertFalse(result.success)
            self.assertGreater(len(result.errors), 0)
            self.assertEqual(result.metrics["real_llm_success_count"], 0)
            self.assertEqual(result.metrics["provider_failure_count"], 1)


if __name__ == "__main__":
    unittest.main()
