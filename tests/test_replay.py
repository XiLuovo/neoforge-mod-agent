from __future__ import annotations

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

from neoforge_agent import AgentOrchestrator, AgentRunReplayer, AppConfig, RequestOverrides


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class AgentReplayTests(unittest.TestCase):
    def test_replay_agent_run_writes_timeline_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            run = AgentOrchestrator(config).run_generate(
                "Create a ruby mod with ruby.",
                overrides=RequestOverrides(),
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="unit-replay",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
            )
            self.assertTrue(run.success)
            self.assertIsNotNone(run.agent_run_json_path)

            result = AgentRunReplayer(config).replay(config.workspace_root / "unit-replay")

            self.assertTrue(result.success)
            self.assertTrue(result.replay_report_json_path.exists())
            self.assertTrue(result.replay_report_md_path.exists())
            self.assertTrue(result.replay_report_html_path.exists())
            self.assertEqual(result.mode, "generate")
            self.assertEqual(result.metrics["steps_count"], len(run.steps))
            self.assertEqual(result.metrics["decisions_count"], len(run.decisions))
            self.assertEqual(result.metrics["prompt_traces_count"], len(run.prompt_traces))
            self.assertEqual(result.metrics["llm_usage_events_count"], 1)
            self.assertGreater(result.metrics["llm_input_tokens"], 0)
            self.assertGreater(result.metrics["llm_output_tokens"], 0)
            self.assertIn("mock", result.metrics["provider_models"])

            kinds = {event.kind for event in result.replay_events}
            self.assertIn("run_start", kinds)
            self.assertIn("role_step", kinds)
            self.assertIn("decision", kinds)
            self.assertIn("prompt_trace", kinds)
            self.assertIn("repair_rag", kinds)
            self.assertIn("artifacts", kinds)
            self.assertEqual(result.metrics["repair_rag_events_count"], 1)
            self.assertIn("repair_rag_hits_count", result.metrics)

            report = result.replay_report_md_path.read_text(encoding="utf-8")
            self.assertIn("Agent Run Replay", report)
            self.assertIn("不会重新调用 LLM", report)
            self.assertIn("Repair RAG Evidence", report)

            html = result.replay_report_html_path.read_text(encoding="utf-8")
            self.assertIn("Agent Session Replay", html)
            self.assertIn("provider_metadata", html)
            self.assertIn("llm_usage", html)
            self.assertIn("data-filter=\"prompt_trace\"", html)

    def test_replay_accepts_direct_agent_run_json_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            run = AgentOrchestrator(config).run_generate(
                "Create a ruby mod with ruby.",
                overrides=RequestOverrides(),
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="unit-replay-direct",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
            )
            self.assertIsNotNone(run.agent_run_json_path)

            result = AgentRunReplayer(config).replay(run.agent_run_json_path)

            self.assertTrue(result.success)
            self.assertEqual(result.source_path, run.agent_run_json_path)
            self.assertTrue(result.replay_report_html_path.exists())


if __name__ == "__main__":
    unittest.main()
