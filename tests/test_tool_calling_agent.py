from __future__ import annotations

import json
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

from neoforge_agent import (
    AgentOrchestrator,
    AgentPromptTrace,
    AppConfig,
    LLMReviewResult,
    StructuredPatchApplier,
    ToolCallingRepairResult,
)
from neoforge_agent.auditor import WorkspaceAuditor


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root, project_root=PROJECT_ROOT)


class ToolCallingAgentTests(unittest.TestCase):
    def test_agent_repair_uses_llm_tool_calls_and_structured_patch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tool-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)
            setup = orchestrator.run_generate(
                "Create a ruby mod with ruby.",
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="tool-agent-pack",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
            )
            self.assertTrue(setup.success)
            self.assertIsNotNone(setup.workspace)

            pack_mcmeta = setup.workspace / "src" / "main" / "resources" / "pack.mcmeta"
            text = pack_mcmeta.read_text(encoding="utf-8")
            pack_mcmeta.write_text(text.replace('"pack_format": 61', '"pack_format": "BROKEN"'), encoding="utf-8")
            self.assertFalse(WorkspaceAuditor(config).audit_workspace(setup.workspace).success)

            result = orchestrator.run_repair(
                setup.workspace,
                goal="Fix audit failures without changing user-owned files.",
                planner_mode="llm",
                llm_provider="mock",
                max_iterations=5,
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.mode, "repair")
            self.assertTrue(WorkspaceAuditor(config).audit_workspace(setup.workspace).success)
            self.assertIn('"pack_format": 61', pack_mcmeta.read_text(encoding="utf-8"))

            trace_path = setup.workspace / ".agent" / "tool-call-trace.json"
            self.assertTrue(trace_path.exists())
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            actions = [entry["action"] for entry in trace]
            self.assertEqual(
                actions,
                ["retrieve_rag", "read_file", "apply_structured_patch", "run_audit", "finish"],
            )
            self.assertTrue(all(entry.get("source") == "llm" for entry in trace))
            self.assertTrue(all(entry.get("observation") for entry in trace))
            retrieve_observation = trace[0]["observation"]
            self.assertTrue(retrieve_observation["rag_decision_id"])
            self.assertTrue(retrieve_observation["queries"])
            self.assertTrue(retrieve_observation["citations"])
            self.assertEqual(retrieve_observation["sufficiency"], "sufficient")
            patch_observation = trace[2]["observation"]
            self.assertEqual(patch_observation["citation_ids"], ["pack.mcmeta"])

            repair_payload = result.payload["repair"]
            self.assertTrue(repair_payload["repair_needed"])
            self.assertTrue(repair_payload["repair_executed"])
            self.assertTrue(repair_payload["repair_success"])
            self.assertEqual(repair_payload["tool_calls_count"], 5)

            self.assertTrue((setup.workspace / ".agent" / "structured-patch-report.json").exists())
            self.assertTrue((setup.workspace / ".agent" / "structured-patch-rollback-report.json").exists())
            snapshots = list((setup.workspace / ".agent" / "structured-patch-snapshots").rglob("pack.mcmeta"))
            self.assertTrue(snapshots)
            self.assertTrue((setup.workspace / ".agent" / "repair-rag-context.json").exists())
            rag_trace_path = setup.workspace / ".agent" / "rag-decision-trace.json"
            self.assertTrue(rag_trace_path.exists())
            rag_trace = json.loads(rag_trace_path.read_text(encoding="utf-8"))
            self.assertTrue(rag_trace[0]["used_by_patch"])
            self.assertEqual(rag_trace[0]["patch_citation_ids"], ["pack.mcmeta"])
            reviewer_report = json.loads((setup.workspace / ".agent" / "reviewer-report.json").read_text(encoding="utf-8"))
            self.assertEqual(reviewer_report["source"], "llm_reviewer")
            self.assertEqual(reviewer_report["decision"], "approve")
            self.assertEqual(reviewer_report["coverage_status"], "pass")
            self.assertEqual(reviewer_report["evidence_sufficiency"], "sufficient")
            self.assertEqual(result.payload["repair"]["reviewer"]["source"], "llm_reviewer")
            self.assertTrue(any(trace.role == "reviewer_agent" for trace in result.prompt_traces))
            self.assertGreaterEqual(len(result.prompt_traces), 6)

    def test_reviewer_approval_cannot_override_failed_repair_gate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tool-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            orchestrator = AgentOrchestrator(config)
            setup = orchestrator.run_generate(
                "Create a ruby mod with ruby.",
                planner_mode="llm",
                llm_provider="mock",
                workspace_name="tool-agent-reviewer-gate",
                overwrite=True,
                run_build=False,
                run_audit=True,
                repair=True,
            )
            self.assertTrue(setup.success)
            self.assertIsNotNone(setup.workspace)

            approve_review = LLMReviewResult(
                success=True,
                reviewer_report={
                    "coverage_status": "pass",
                    "covered_requirements": ["Forced reviewer approval for gate boundary test."],
                    "missing_requirements": [],
                    "unsupported_or_risky_requests": [],
                    "patch_risks": [],
                    "recommended_checks": ["Deterministic gates remain authoritative."],
                    "decision": "approve",
                    "confidence": 1.0,
                },
                prompt_trace=AgentPromptTrace(
                    role="reviewer_agent",
                    planner_mode="llm_reviewer",
                    provider="mock",
                    prompt_kind="reviewer_repair_final",
                    input_text="forced reviewer approval",
                    normalized_json={"decision": "approve", "coverage_status": "pass"},
                ),
                provider="mock",
                model="mock",
            )

            def fake_tool_loop(workspace: Path, **kwargs) -> ToolCallingRepairResult:
                final_audit = {
                    "attempted": True,
                    "success": False,
                    "summary": "Forced audit failure after repair loop.",
                    "errors": [{"message": "forced audit failure"}],
                }
                return ToolCallingRepairResult(
                    success=False,
                    workspace=Path(workspace),
                    goal=str(kwargs.get("goal", "")),
                    loop_purpose="repair",
                    max_iterations=int(kwargs.get("max_iterations", 1)),
                    iterations=1,
                    repair_needed=False,
                    repair_executed=False,
                    repair_success=None,
                    initial_build=dict(kwargs.get("initial_build", {})),
                    initial_audit=dict(kwargs.get("initial_audit", {})),
                    final_build=dict(kwargs.get("initial_build", {})),
                    final_audit=final_audit,
                    root_causes=["forced audit failure"],
                    repair_plan=list(kwargs.get("repair_plan") or []),
                    trace=[
                        {
                            "iteration": 1,
                            "role": "repair_agent",
                            "source": "llm",
                            "action": "finish",
                            "args": {"status": "success"},
                            "observation": {"success": False, "summary": "Forced audit failure."},
                        }
                    ],
                )

            with patch.object(orchestrator.tool_calling_repair_agent, "run", side_effect=fake_tool_loop):
                with patch.object(orchestrator.llm_reviewer, "review", return_value=approve_review):
                    result = orchestrator.run_repair(
                        setup.workspace,
                        goal="Fix audit failures without changing user-owned files.",
                        planner_mode="llm",
                        llm_provider="mock",
                        max_iterations=1,
                        run_build=False,
                        run_audit=True,
                    )

            self.assertFalse(result.success)
            self.assertEqual(result.payload["reviewer"]["decision"], "approve")
            self.assertFalse(result.payload["repair"]["final_audit"]["success"])
            reviewer_report = json.loads((setup.workspace / ".agent" / "reviewer-report.json").read_text(encoding="utf-8"))
            self.assertEqual(reviewer_report["decision"], "approve")
            self.assertEqual(reviewer_report["source"], "llm_reviewer")

    def test_structured_patch_rejects_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tool-agent-", dir=TMP_ROOT) as tmp:
            workspace = Path(tmp)
            applier = StructuredPatchApplier(test_config(workspace))

            for path in ("../outside.txt", ".git/config", "gradle/wrapper/gradle-wrapper.jar"):
                with self.subTest(path=path):
                    result = applier.apply(
                        workspace,
                        {
                            "changes": [
                                {
                                    "operation": "write_file",
                                    "path": path,
                                    "content": "unsafe",
                                    "reason": "unit test",
                                }
                            ]
                        },
                    )
                    self.assertFalse(result.success)
                    self.assertTrue(result.errors)


if __name__ == "__main__":
    unittest.main()
