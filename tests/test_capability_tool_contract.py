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

from neoforge_agent import AppConfig, CapabilityCatalog, ToolManifestRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


def _blob(parts: list[str]) -> str:
    return " ".join(parts).lower()


class CapabilityToolContractTests(unittest.TestCase):
    def test_experimental_lanes_keep_the_same_boundary_in_catalog_and_tool_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            capabilities = CapabilityCatalog(config).build(run_name="unit-capability-tool-contract")
            manifest = ToolManifestRunner(config).build(run_name="unit-capability-tool-contract")

        by_capability_id = {
            capability.identifier: capability
            for section in capabilities.sections
            for capability in section.capabilities
        }
        for capability_id in [
            "direct_code_lane",
            "direct_code_patch_plan",
            "direct_code_review_gate",
            "direct_code_build_audit_gate",
            "controlled_java_extension",
            "java_extension_sandbox",
            "java_extension_audit",
            "java_extension_build_gate",
            "java_extension_diff_report",
            "java_extension_rollback_report",
        ]:
            self.assertEqual(by_capability_id[capability_id].status, "experimental", capability_id)

        for stable_wrapper_id in ["agent_generate", "agent_modify"]:
            wrapper = by_capability_id[stable_wrapper_id]
            self.assertEqual(wrapper.status, "stable")
            self.assertIn("Direct Code Lane", wrapper.summary)
            self.assertIn("experimental opt-in", wrapper.summary)

        direct_code_limit = next(
            limitation
            for limitation in capabilities.limitations
            if limitation.startswith("Direct Code Lane")
        )
        self.assertIn("not an unbounded coding agent", direct_code_limit)
        self.assertIn("audit/build gates", direct_code_limit)
        self.assertIn("rollback evidence", direct_code_limit)

        for removed_capability_id in [
            "free_code_lab",
            "free_code_lab_safety_gate",
            "capability_harvest_report",
            "capability_harvest_loop",
            "machine_gui_harvest_target",
        ]:
            self.assertNotIn(removed_capability_id, by_capability_id)
        self.assertFalse(any(limitation.startswith("Free-Code Lab") for limitation in capabilities.limitations))

        tools_by_name = {tool.name: tool for tool in manifest.tools}
        for tool_name in ["agent_generate", "agent_modify"]:
            tool = tools_by_name[tool_name]
            code_lane_schema = tool.input_schema["properties"]["code_lane"]
            self.assertEqual(code_lane_schema["enum"], ["hybrid", "modspec", "direct"])
            self.assertIn("experimental", code_lane_schema["description"])
            boundary = _blob(tool.safety_boundaries)
            self.assertIn("direct code", boundary)
            self.assertIn("experimental", boundary)
            self.assertIn("generated workspace", boundary)
            self.assertIn("audit", boundary)
            self.assertIn("rollback", boundary)

        self.assertNotIn("free_code_lab_generate", tools_by_name)
        self.assertNotIn("harvest_report", tools_by_name)

        manifest_direct_code_limit = next(
            limitation
            for limitation in manifest.limitations
            if limitation.startswith("Direct Code Lane")
        )
        self.assertIn("generated workspaces", manifest_direct_code_limit)
        self.assertIn("structured patches", manifest_direct_code_limit)
        self.assertIn("audit/build gates", manifest_direct_code_limit)
        self.assertIn("rollback reporting", manifest_direct_code_limit)
        self.assertFalse(any(limitation.startswith("Free-Code Lab") for limitation in manifest.limitations))

    def test_benchmark_and_evidence_reports_do_not_claim_runtime_acceptance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            capabilities = CapabilityCatalog(config).build(run_name="unit-evidence-scope")
            manifest = ToolManifestRunner(config).build(run_name="unit-evidence-scope")

        by_capability_id = {
            capability.identifier: capability
            for section in capabilities.sections
            for capability in section.capabilities
        }
        for capability_id in ["benchmark_report_page", "evidence_chain_report"]:
            summary = by_capability_id[capability_id].summary
            self.assertIn("manual runtime evidence", summary)
            self.assertNotIn("runtime pass rate", summary)
            self.assertNotIn("runtime validation evidence", summary)

        tools_by_name = {tool.name: tool for tool in manifest.tools}
        for tool_name in ["agent_bench", "evidence_chain_report"]:
            boundary = _blob(tools_by_name[tool_name].safety_boundaries)
            self.assertIn("audit/build", boundary)
            self.assertIn("manual runtime evidence", boundary)
            self.assertIn("does not claim automatic minecraft client/server acceptance", boundary)


if __name__ == "__main__":
    unittest.main()
