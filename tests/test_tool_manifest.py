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

from neoforge_agent import AppConfig, ToolManifestRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class ToolManifestTests(unittest.TestCase):
    def test_tool_manifest_writes_reports_and_core_tool_schemas(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = ToolManifestRunner(config).build(run_name="unit-tools-manifest")

            self.assertTrue(result.success)
            self.assertTrue(result.tools_manifest_json_path.exists())
            self.assertTrue(result.tools_manifest_md_path.exists())

            tool_names = {tool.name for tool in result.tools}
            self.assertIn("agent_generate", tool_names)
            self.assertIn("agent_modify", tool_names)
            self.assertIn("free_code_lab_generate", tool_names)
            self.assertIn("harvest_report", tool_names)
            self.assertIn("audit_workspace", tool_names)
            self.assertIn("repair_loop", tool_names)
            self.assertIn("rag_eval", tool_names)
            self.assertIn("evidence_chain_report", tool_names)

            agent_generate = next(tool for tool in result.tools if tool.name == "agent_generate")
            self.assertEqual(agent_generate.input_schema["type"], "object")
            self.assertIn("request", agent_generate.input_schema["required"])
            self.assertIn("run_build", agent_generate.input_schema["properties"])
            self.assertIn("code_lane", agent_generate.input_schema["properties"])
            self.assertEqual(agent_generate.input_schema["properties"]["code_lane"]["enum"], ["hybrid", "modspec", "direct"])
            self.assertIn(".agent/direct-code-plan.json", agent_generate.output_artifacts)
            self.assertTrue(agent_generate.output_artifacts)
            self.assertTrue(agent_generate.safety_boundaries)

            agent_modify = next(tool for tool in result.tools if tool.name == "agent_modify")
            self.assertIn("code_lane", agent_modify.input_schema["properties"])
            self.assertEqual(agent_modify.input_schema["properties"]["code_lane"]["enum"], ["hybrid", "modspec", "direct"])
            self.assertIn(".agent/direct-code-review.json", agent_modify.output_artifacts)

            free_code_lab = next(tool for tool in result.tools if tool.name == "free_code_lab_generate")
            self.assertIn("request", free_code_lab.input_schema["required"])
            self.assertIn("from_workspace", free_code_lab.input_schema["required"])
            self.assertIn("run_build", free_code_lab.input_schema["properties"])
            self.assertIn("workspace/free-code-lab-runs/<run-id>/.agent/harvest-candidate.json", free_code_lab.output_artifacts)
            self.assertTrue(any("copies the source workspace" in boundary.lower() for boundary in free_code_lab.safety_boundaries))
            self.assertTrue(any("does not modify" in boundary.lower() for boundary in free_code_lab.safety_boundaries))

            harvest_report = next(tool for tool in result.tools if tool.name == "harvest_report")
            self.assertEqual(harvest_report.cli_mapping, "harvest-report")
            self.assertIn("workspace/harvest-runs/<run-id>/.agent/harvest-report.json", harvest_report.output_artifacts)

            payload = json.loads(result.tools_manifest_json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["tools_count"], len(result.tools))
            self.assertIn("This manifest is a local contract", payload["limitations"][0])


if __name__ == "__main__":
    unittest.main()
