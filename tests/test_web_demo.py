from __future__ import annotations

import json
import tempfile
import time
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

from neoforge_agent import AppConfig, WebDemoRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class WebDemoTests(unittest.TestCase):
    def test_web_demo_renders_interactive_shell(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            runner = WebDemoRunner(test_config(Path(tmp)))

            html = runner.render_index_html()

            self.assertIn("Project Console", html)
            self.assertIn("NeoForge Mod Agent 控制台", html)
            self.assertIn("promptInput", html)
            self.assertIn("workspaceSelect", html)
            self.assertIn("/api/generate", html)
            self.assertIn("/api/jobs/generate", html)
            self.assertIn("/api/modify", html)
            self.assertIn("/api/jobs/modify", html)
            self.assertIn("/api/job", html)
            self.assertIn("runLogOutput", html)
            self.assertIn("buildLogOutput", html)
            self.assertIn("evidenceView", html)
            self.assertIn("directCodeView", html)
            self.assertIn("resourcesView", html)
            self.assertIn("Evidence", html)
            self.assertIn("Direct Code", html)
            self.assertIn("Resources", html)
            self.assertIn("repairView", html)
            self.assertIn("repairStatus", html)
            self.assertIn("Repair Agent", html)
            self.assertIn("Repair RAG", html)
            self.assertIn("/api/knowledge", html)
            self.assertIn("knowledgeOutput", html)
            self.assertIn("knowledgeCategorySelect", html)
            self.assertIn("/api/eval", html)
            self.assertIn("Mock LLM", html)
            self.assertIn("Real LLM", html)

    def test_web_demo_generate_returns_modspec_files_audit_and_trace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            runner = WebDemoRunner(test_config(Path(tmp)))

            payload = runner.run_generate(
                "Create a ruby mod with a ruby charm item.",
                planner_selection="mock-llm",
                workspace_name="unit-web-demo",
                overwrite=True,
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(payload["success"])
            self.assertEqual(payload["modspec"]["features"][0]["id"], "ruby_charm")
            self.assertGreater(payload["summary"]["generated_files_count"], 0)
            self.assertTrue(payload["audit"]["success"])
            self.assertFalse(payload["build"]["attempted"])
            self.assertIn("repair", payload)
            self.assertIn("self_healing", payload)
            self.assertFalse(payload["repair"]["repair_needed"])
            self.assertIn("repair_rag_hits_count", payload["repair"])
            self.assertGreater(payload["agent_trace"]["roles_count"], 0)
            self.assertTrue(Path(payload["workspace"]).exists())
            self.assertIn("build_output", payload)
            self.assertIn("evidence", payload)
            self.assertIn("direct_code", payload)
            self.assertIn("resource_preview", payload)
            self.assertIn("harvest_summary", payload)
            self.assertFalse(payload["summary"]["direct_code_used"])
            self.assertFalse(payload["summary"]["rollback_recommended"])

    def test_web_demo_async_generate_job_exposes_logs_and_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            runner = WebDemoRunner(test_config(Path(tmp)))

            started = runner.start_generate_job(
                "Create a ruby mod with ruby.",
                planner_selection="mock-llm",
                workspace_name="unit-web-demo-job",
                overwrite=True,
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(started["success"])
            self.assertEqual(started["kind"], "generate")
            self.assertIn(started["status"], {"queued", "running", "succeeded"})
            self.assertGreaterEqual(len(started["logs"]), 1)

            deadline = time.time() + 10
            current = started
            while current["status"] not in {"succeeded", "failed"} and time.time() < deadline:
                time.sleep(0.05)
                current = runner.get_job(started["job_id"])

            self.assertEqual(current["status"], "succeeded")
            self.assertIsNotNone(current["result"])
            self.assertTrue(current["result"]["success"])
            self.assertGreaterEqual(len(current["logs"]), 3)
            self.assertIn("live_build_output", current)

    def test_web_demo_build_output_preview_reads_log_tails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            runner = WebDemoRunner(test_config(Path(tmp)))
            logs_dir = Path(tmp) / "workspace" / ".agent" / "logs"
            logs_dir.mkdir(parents=True)
            log_path = logs_dir / "gradle-build.log"
            stdout_path = logs_dir / "gradle-build.stdout.log"
            stderr_path = logs_dir / "gradle-build.stderr.log"
            log_path.write_text("line one\nline two\n", encoding="utf-8")
            stdout_path.write_text("BUILD SUCCESSFUL\n", encoding="utf-8")
            stderr_path.write_text("warning only\n", encoding="utf-8")

            preview = runner._build_output_preview(
                {
                    "attempted": True,
                    "success": True,
                    "summary": "Gradle build completed successfully.",
                    "log_path": str(log_path),
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                }
            )

            self.assertTrue(preview["available"])
            self.assertIn("line two", preview["log_tail"])
            self.assertIn("BUILD SUCCESSFUL", preview["stdout_tail"])
            self.assertIn("warning only", preview["stderr_tail"])

    def test_web_demo_lists_and_filters_knowledge_entries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            runner = WebDemoRunner(test_config(Path(tmp)))

            all_entries = runner.list_knowledge_entries()
            worldgen = runner.list_knowledge_entries(query="ruby ore worldgen", category="worldgen")
            behavior = runner.list_knowledge_entries(capability="right_click_behavior")

            self.assertTrue(all_entries["success"])
            self.assertGreater(all_entries["total_entries"], 0)
            self.assertGreater(len(all_entries["categories"]), 0)
            self.assertGreater(len(all_entries["capabilities"]), 0)
            self.assertTrue(worldgen["entries"])
            self.assertEqual(worldgen["entries"][0]["id"], "worldgen.overworld_ore")
            self.assertEqual(worldgen["entries"][0]["category"], "worldgen")
            self.assertTrue(behavior["entries"])
            self.assertEqual(behavior["entries"][0]["capability"], "right_click_behavior")

    def test_web_demo_lists_loads_and_modifies_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            runner = WebDemoRunner(test_config(Path(tmp)))
            generated = runner.run_generate(
                "Create a ruby mod with ruby.",
                planner_selection="mock-llm",
                workspace_name="unit-web-demo-modify",
                overwrite=True,
                run_build=False,
                run_audit=True,
            )

            workspaces = runner.list_workspaces()
            loaded = runner.get_workspace("unit-web-demo-modify")
            modified = runner.run_modify(
                "unit-web-demo-modify",
                "Add a ruby charm item that heals 4 health on right click with 20 seconds cooldown.",
                planner_selection="mock-llm",
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(generated["success"])
            self.assertTrue(workspaces["success"])
            self.assertGreaterEqual(workspaces["workspaces_count"], 1)
            self.assertTrue(loaded["success"])
            self.assertEqual(loaded["modspec"]["features"][0]["id"], "ruby")
            self.assertIn("self_healing", loaded)
            self.assertIn("evidence", loaded)
            self.assertIn("direct_code", loaded)
            self.assertIn("resource_preview", loaded)
            self.assertIn("harvest_summary", loaded)
            self.assertIn("repair_rag_hits_count", loaded["self_healing"])
            self.assertTrue(modified["success"])
            self.assertIn("ruby_charm", modified["merge"]["added"])
            self.assertIn("item:ruby_charm", modified["modspec_diff"]["added"])
            self.assertIn("patch_agent", modified)
            self.assertTrue(Path(modified["patch_agent"]["plan_json_path"]).exists())
            self.assertTrue(Path(modified["patch_agent"]["report_json_path"]).exists())
            self.assertTrue(modified["audit"]["success"])
            self.assertIn("repair", modified)
            self.assertIn("repair_rag_hits_count", modified["repair"])
            self.assertGreater(modified["agent_trace"]["roles_count"], 0)

    def test_web_demo_workspace_console_summarizes_direct_code_resources_and_harvest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            runner = WebDemoRunner(test_config(root))
            workspace = root / "unit-console"
            agent_dir = workspace / ".agent"
            snapshots = agent_dir / "direct-code-snapshots" / "src" / "main" / "java"
            previews = agent_dir / "previews"
            snapshots.mkdir(parents=True)
            previews.mkdir(parents=True)
            (agent_dir / "modspec.json").write_text(
                json.dumps({"mod_id": "ruby_mod", "features": [{"type": "item", "id": "ruby"}]}),
                encoding="utf-8",
            )
            (agent_dir / "generation-summary.json").write_text(
                json.dumps({"generated_files": ["src/main/java/Ruby.java"]}),
                encoding="utf-8",
            )
            (agent_dir / "audit-report.json").write_text(json.dumps({"success": True}), encoding="utf-8")
            (agent_dir / "direct-code-plan.json").write_text(
                json.dumps({"summary": "Add helper class.", "changes": [{"path": "src/main/java/RubyHelper.java"}]}),
                encoding="utf-8",
            )
            (agent_dir / "direct-code-review.json").write_text(json.dumps({"approved": True, "errors": []}), encoding="utf-8")
            (agent_dir / "direct-code-report.json").write_text(
                json.dumps({"success": True, "changed_files": ["src/main/java/RubyHelper.java"]}),
                encoding="utf-8",
            )
            (agent_dir / "direct-code-rollback-report.json").write_text(
                json.dumps({"status": "recommended", "rollback_required": True, "reason": "build_fail"}),
                encoding="utf-8",
            )
            (agent_dir / "direct-code-diff.md").write_text("# Diff\n", encoding="utf-8")
            (snapshots / "RubyHelper.java").write_text("snapshot", encoding="utf-8")
            (agent_dir / "resource-quality-report.json").write_text(
                json.dumps({"summary": {"textures": 2, "model_variants": 3}}),
                encoding="utf-8",
            )
            (agent_dir / "texture-atlas.png").write_bytes(b"png")
            (previews / "ruby_gallery.png").write_bytes(b"png")

            candidate_dir = root / "free-code-lab-runs" / "unit-lab" / ".agent"
            candidate_dir.mkdir(parents=True)
            (candidate_dir / "harvest-candidate.json").write_text(
                json.dumps({"run_id": "unit-lab", "ready_to_harvest": True, "recommendation": "harvest_into_generator"}),
                encoding="utf-8",
            )
            harvest_dir = root / "harvest-runs" / "unit-harvest" / ".agent"
            harvest_dir.mkdir(parents=True)
            (harvest_dir / "harvest-report.json").write_text(json.dumps({"run_id": "unit-harvest"}), encoding="utf-8")

            payload = runner.get_workspace("unit-console")

            self.assertTrue(payload["success"])
            self.assertTrue(payload["direct_code"]["used"])
            self.assertTrue(payload["direct_code"]["rollback_recommended"])
            self.assertEqual(payload["direct_code"]["rollback_status"], "recommended")
            self.assertEqual(payload["direct_code"]["snapshot_files_count"], 1)
            self.assertTrue(payload["resource_preview"]["available"])
            self.assertTrue(payload["resource_preview"]["atlas_available"])
            self.assertEqual(payload["resource_preview"]["structure_previews_count"], 1)
            self.assertEqual(payload["harvest_summary"]["candidates_count"], 1)
            self.assertEqual(payload["harvest_summary"]["ready_to_harvest_count"], 1)
            self.assertEqual(payload["harvest_summary"]["harvest_reports_count"], 1)
            self.assertTrue(payload["evidence"]["direct_code_used"])
            self.assertTrue(payload["evidence"]["rollback_recommended"])

    def test_web_demo_self_healing_summary_includes_repair_rag_hits(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            runner = WebDemoRunner(test_config(Path(tmp)))
            workspace = Path(tmp) / "unit-rag-workspace"
            workspace.mkdir()

            summary = runner._repair_summary_from_repair_payload(
                {
                    "repair_needed": True,
                    "repair_executed": False,
                    "root_causes": ["Missing generated texture file ruby.png"],
                    "repair_plan": [
                        {
                            "id": "inspect_audit_report",
                            "summary": "Read audit report and regenerate managed texture files.",
                        }
                    ],
                    "repair_rag": {
                        "attempted": True,
                        "success": True,
                        "query": "repair audit missing texture png",
                        "hits_count": 1,
                        "categories": {"audit": 1},
                        "capabilities": {"texture_audit": 1},
                        "hits": [
                            {
                                "id": "audit.texture_checks",
                                "title": "Audit verifies managed texture PNG files",
                                "category": "audit",
                                "capability": "texture_audit",
                                "score": 40,
                            }
                        ],
                    },
                },
                workspace=workspace,
            )

            self.assertEqual(summary["repair_rag_hits_count"], 1)
            self.assertEqual(summary["repair_rag_hits"][0]["id"], "audit.texture_checks")
            self.assertEqual(summary["repair_rag_links"][0]["action_id"], "inspect_audit_report")

    def test_web_demo_eval_returns_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            runner = WebDemoRunner(test_config(Path(tmp)))

            payload = runner.run_eval(
                planner_selection="mock-llm",
                limit=1,
                run_build=False,
                run_audit=True,
                run_name="unit-web-demo-eval",
            )

            self.assertTrue(payload["success"])
            self.assertEqual(payload["summary"]["cases"], 1)
            self.assertIn("rag_hit_rate", payload["summary"])
            self.assertTrue(Path(payload["eval"]["eval_report_json_path"]).exists())


if __name__ == "__main__":
    unittest.main()
