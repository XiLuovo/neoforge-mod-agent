from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neoforge_agent.agent_models import AgentDecision, AgentPromptTrace, AgentRunResult, AgentStep
from neoforge_agent.agent_runtime import AgentRuntime, AgentRuntimeRequest, AgentRuntimeStageResult
from neoforge_agent.domain_spec import NeoForgeModSpecPlugin
from neoforge_agent import neoforge_runtime_plugin_ports
from neoforge_agent import neoforge_runtime_ports
from neoforge_agent import neoforge_runtime_workflow_ports


class RecordingTraceWriter:
    def __init__(self) -> None:
        self.writes: list[AgentRunResult] = []

    def write(self, run: AgentRunResult) -> None:
        self.writes.append(run)


class FakeRuntimePlugin:
    domain_name = "fake"
    domain_spec_plugin = NeoForgeModSpecPlugin()

    def __init__(self, scenario: str = "success") -> None:
        self.scenario = scenario
        self.calls: list[str] = []

    def plan_generate(self, request: AgentRuntimeRequest) -> AgentRuntimeStageResult:
        self.calls.append("plan")
        if self.scenario == "plan_fail":
            return self._stage(
                "planner_agent",
                success=False,
                status="fail",
                payload={"planning_error": "boom"},
                planner_mode_used="rules",
            )
        return self._stage(
            "planner_agent",
            success=True,
            payload={"spec": {"id": "fake"}},
            planner_mode_used="llm:fake",
            state={"spec": "fake"},
        )

    def review(self, request: AgentRuntimeRequest, plan: AgentRuntimeStageResult) -> AgentRuntimeStageResult:
        self.calls.append("review")
        if self.scenario == "review_fail":
            return self._stage("reviewer_agent", success=False, status="fail", payload={"review": "rejected"})
        return self._stage("reviewer_agent", success=True, payload={"review": "approved"})

    def execute_generate(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        self.calls.append("execute")
        workspace = Path(request.options["workspace"])
        return self._stage(
            "executor_agent",
            success=True,
            payload={"generated": True},
            state={"generation": "fake"},
            workspace=workspace,
            build_payload={"attempted": False, "success": None},
        )

    def audit(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        self.calls.append("audit")
        return self._stage("auditor_agent", success=True, payload={"attempted": True, "success": True})

    def repair(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        self.calls.append("repair")
        return self._stage("repair_agent", success=True, status="skip", payload={"repair_needed": False})

    def final_success(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> bool:
        self.calls.append("final_success")
        return execution.success and audit.success and repair.success

    def final_payload(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
        repair: AgentRuntimeStageResult,
    ) -> dict:
        self.calls.append("final_payload")
        return {
            "final": True,
            "plan": plan.payload,
            "review": review.payload,
            "execution": execution.payload,
            "audit": audit.payload,
            "repair": repair.payload,
        }

    def review_failure_payload(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        review: AgentRuntimeStageResult,
    ) -> dict:
        return {"failed_stage": "reviewer", "review": review.payload, "spec": plan.payload.get("spec")}

    def _stage(
        self,
        role: str,
        *,
        success: bool,
        status: str = "pass",
        payload: dict | None = None,
        state: dict | None = None,
        workspace: Path | None = None,
        planner_mode_used: str | None = None,
        build_payload: dict | None = None,
    ) -> AgentRuntimeStageResult:
        return AgentRuntimeStageResult(
            success=success,
            steps=[AgentStep(role=role, status=status, summary=f"{role} {status}")],
            decisions=[
                AgentDecision(
                    role=role,
                    decision=f"{role}_decision",
                    rationale="fake runtime test decision",
                    status=status,
                )
            ],
            prompt_traces=[
                AgentPromptTrace(
                    role=role,
                    planner_mode="fake",
                    provider="mock",
                    prompt_kind=role,
                    input_text=role,
                )
            ],
            payload=payload or {},
            state=state,
            workspace=workspace,
            planner_mode_used=planner_mode_used,
            build_payload=build_payload or {},
        )


class AgentRuntimeTests(unittest.TestCase):
    def test_runtime_port_modules_keep_plugin_and_workflow_seams_distinct(self) -> None:
        plugin_fields = set(neoforge_runtime_plugin_ports.NeoForgeRuntimePluginDeps.__dataclass_fields__)

        self.assertEqual(
            plugin_fields,
            {
                "planning_workflow",
                "review_workflow",
                "generate_execution",
                "audit_workflow",
                "repair_stage",
                "finalization",
            },
        )
        self.assertFalse(hasattr(neoforge_runtime_plugin_ports, "NeoForgeRuntimePlanningPort"))
        self.assertIs(
            neoforge_runtime_ports.NeoForgeRuntimePluginDeps,
            neoforge_runtime_plugin_ports.NeoForgeRuntimePluginDeps,
        )
        self.assertIs(
            neoforge_runtime_ports.NeoForgeRuntimePlanningPort,
            neoforge_runtime_workflow_ports.NeoForgeRuntimePlanningPort,
        )

    def test_run_generate_success_accumulates_trace_and_writes_once(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agent-runtime-", dir=TMP_ROOT) as tmp:
            plugin = FakeRuntimePlugin()
            writer = RecordingTraceWriter()
            runtime = AgentRuntime(plugin, writer)

            run = runtime.run_generate(_request(Path(tmp)))

            self.assertTrue(run.success)
            self.assertEqual(plugin.calls, ["plan", "review", "execute", "audit", "repair", "final_success", "final_payload"])
            self.assertEqual(writer.writes, [run])
            self.assertEqual(run.planner_mode, "llm:fake")
            self.assertEqual(run.workspace, Path(tmp))
            self.assertEqual(
                [step.role for step in run.steps],
                ["planner_agent", "reviewer_agent", "executor_agent", "auditor_agent", "repair_agent"],
            )
            self.assertEqual(len(run.decisions), 5)
            self.assertEqual(len(run.prompt_traces), 5)
            self.assertEqual(run.payload["final"], True)

    def test_run_generate_planner_failure_returns_unwritten_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agent-runtime-", dir=TMP_ROOT) as tmp:
            plugin = FakeRuntimePlugin("plan_fail")
            writer = RecordingTraceWriter()
            runtime = AgentRuntime(plugin, writer)

            run = runtime.run_generate(_request(Path(tmp)))

            self.assertFalse(run.success)
            self.assertEqual(plugin.calls, ["plan"])
            self.assertEqual(writer.writes, [])
            self.assertEqual(run.planner_mode, "rules")
            self.assertEqual(run.payload, {"planning_error": "boom"})
            self.assertEqual([step.role for step in run.steps], ["planner_agent"])

    def test_run_generate_review_failure_uses_plugin_failure_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agent-runtime-", dir=TMP_ROOT) as tmp:
            plugin = FakeRuntimePlugin("review_fail")
            writer = RecordingTraceWriter()
            runtime = AgentRuntime(plugin, writer)

            run = runtime.run_generate(_request(Path(tmp)))

            self.assertFalse(run.success)
            self.assertEqual(plugin.calls, ["plan", "review"])
            self.assertEqual(writer.writes, [])
            self.assertEqual(run.planner_mode, "llm:fake")
            self.assertEqual(run.payload["failed_stage"], "reviewer")
            self.assertEqual(run.payload["review"], {"review": "rejected"})
            self.assertEqual([step.role for step in run.steps], ["planner_agent", "reviewer_agent"])


def _request(workspace: Path) -> AgentRuntimeRequest:
    return AgentRuntimeRequest(
        mode="generate",
        request="Create a fake mod.",
        planner_mode="llm",
        llm_provider="mock",
        options={"workspace": workspace},
    )


if __name__ == "__main__":
    unittest.main()
