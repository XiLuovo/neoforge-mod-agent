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

from neoforge_agent import AppConfig, BuildResult, FreeCodeChange, FreeCodeLabRunner, FreeCodePlan, HarvestReportRunner
from neoforge_agent.free_code_lab import harvest_candidate_payload


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


def make_source_workspace(root: Path) -> Path:
    source = root / "source-workspace"
    (source / ".agent").mkdir(parents=True)
    (source / "src" / "main" / "resources").mkdir(parents=True)
    (source / "src" / "main" / "resources" / "existing.txt").write_text("alpha beta alpha\n", encoding="utf-8")
    (source / ".agent" / "modspec.json").write_text("{}\n", encoding="utf-8")
    return source


def resource_write(path: str = "src/main/resources/free-code.txt") -> FreeCodeChange:
    return FreeCodeChange(
        path=path,
        operation="write_file",
        content="free-code lab sample\n",
        reason="unit test",
        risk_level="low",
    )


class FreeCodeLabTests(unittest.TestCase):
    def test_lab_run_copies_workspace_writes_artifacts_and_keeps_source_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="free-code-lab-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            source = make_source_workspace(root)
            runner = FreeCodeLabRunner(test_config(root))
            runner._audit = lambda workspace: {"attempted": True, "success": True, "errors_count": 0, "warnings_count": 0}  # type: ignore[method-assign]

            result = runner.run(
                "Add an advanced machine GUI beyond stable generate.",
                from_workspace=source,
                run_name="unit-lab",
                llm_provider="mock",
                run_build=False,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.run_id, "unit-lab")
            self.assertTrue(result.lab_workspace.exists())
            self.assertTrue((result.lab_workspace / ".agent" / "free-code-lab-note.md").exists())
            self.assertFalse((source / ".agent" / "free-code-lab-note.md").exists())
            self.assertEqual(result.harvest_candidate["recommendation"], "keep_as_lab_sample")
            self.assertEqual(result.harvest_candidate["generate_gap"], "advanced_machine_gui")
            self.assertFalse(result.harvest_candidate["ready_to_harvest"])
            for artifact in result.artifacts.values():
                self.assertTrue(artifact.exists(), artifact)
            checklist = result.manual_runtime_checklist_path.read_text(encoding="utf-8")
            self.assertIn("游戏能否启动", checklist)

            report = json.loads(result.artifacts["report_json"].read_text(encoding="utf-8"))
            self.assertTrue(report["policy"]["experimental_only"])
            self.assertTrue(report["policy"]["does_not_update_generator"])

    def test_review_rejects_unsafe_paths_and_allows_text_roots(self) -> None:
        with tempfile.TemporaryDirectory(prefix="free-code-lab-", dir=TMP_ROOT) as tmp:
            runner = FreeCodeLabRunner(test_config(Path(tmp)))

            safe_plan = FreeCodePlan(
                request="safe",
                changes=[
                    resource_write("src/main/java/com/generated/lab/Sample.java"),
                    resource_write("src/main/resources/assets/lab/lang/en_us.json"),
                    resource_write("build.gradle"),
                    resource_write("gradle.properties"),
                    resource_write(".agent/free-code-note.md"),
                ],
            )
            self.assertEqual(runner._review_plan(safe_plan), [])

            unsafe_paths = [
                "../outside.java",
                "/tmp/outside.java",
                "C:/tmp/outside.java",
                ".git/config",
                "gradle/wrapper/gradle-wrapper.jar",
                "src/neoforge_agent/tool_source.py",
                "build/classes/output.class",
            ]
            for path in unsafe_paths:
                with self.subTest(path=path):
                    errors = runner._review_plan(FreeCodePlan(request="unsafe", changes=[resource_write(path)]))
                    self.assertTrue(errors)

            risky = FreeCodePlan(
                request="risky",
                changes=[
                    FreeCodeChange(
                        path="src/main/java/com/generated/lab/Hack.java",
                        operation="write_file",
                        content="public class Hack { void x(){ Runtime.getRuntime(); } }\n",
                        reason="unit test",
                        risk_level="low",
                    )
                ],
            )
            self.assertTrue(any("forbidden token" in error for error in runner._review_plan(risky)))

    def test_free_code_plan_json_and_replace_text_behaviour(self) -> None:
        parsed = FreeCodePlan.from_dict(
            {
                "free_code_plan": {
                    "summary": "Patch text",
                    "gap": "network_sync",
                    "harvest_direction": "modspec_field",
                    "changes": [
                        {
                            "path": "src/main/resources/free-code.txt",
                            "operation": "replace_text",
                            "search": "beta",
                            "replace": "omega",
                            "reason": "unit test",
                            "risk_level": "low",
                        }
                    ],
                }
            },
            request="Add sync",
        )
        self.assertEqual(parsed.gap, "network_sync")
        self.assertEqual(parsed.changes[0].operation, "replace_text")

        with tempfile.TemporaryDirectory(prefix="free-code-lab-", dir=TMP_ROOT) as tmp:
            runner = FreeCodeLabRunner(test_config(Path(tmp)))
            target = Path(tmp) / "src" / "main" / "resources" / "free-code.txt"
            target.parent.mkdir(parents=True)
            target.write_text("alpha beta alpha\n", encoding="utf-8")

            zero = FreeCodeChange(
                path="src/main/resources/free-code.txt",
                operation="replace_text",
                search="missing",
                replace="ok",
                reason="unit test",
                risk_level="low",
            )
            with self.assertRaisesRegex(ValueError, "found 0"):
                runner._apply_change(target, zero, target.read_text(encoding="utf-8"))

            multiple = FreeCodeChange(
                path="src/main/resources/free-code.txt",
                operation="replace_text",
                search="alpha",
                replace="omega",
                reason="unit test",
                risk_level="low",
            )
            with self.assertRaisesRegex(ValueError, "found 2"):
                runner._apply_change(target, multiple, target.read_text(encoding="utf-8"))

            single = FreeCodeChange(
                path="src/main/resources/free-code.txt",
                operation="replace_text",
                search="beta",
                replace="omega",
                reason="unit test",
                risk_level="low",
            )
            after = runner._apply_change(target, single, target.read_text(encoding="utf-8"))
            self.assertEqual(after, "alpha omega alpha\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "alpha omega alpha\n")

    def test_build_failure_rejects_harvest_candidate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="free-code-lab-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            source = make_source_workspace(root)
            runner = FreeCodeLabRunner(test_config(root))
            runner._audit = lambda workspace: {"attempted": True, "success": True, "errors_count": 0, "warnings_count": 0}  # type: ignore[method-assign]

            with patch.object(runner.builder, "build", return_value=BuildResult(attempted=True, success=False, summary="mock compile error")):
                result = runner.run(
                    "Add experimental machine GUI code.",
                    from_workspace=source,
                    run_name="unit-build-fail",
                    llm_provider="mock",
                    run_build=True,
                )

            self.assertFalse(result.success)
            self.assertEqual(result.harvest_candidate["recommendation"], "reject")
            self.assertIn("build_failed", result.harvest_candidate["blockers"])
            report = json.loads(result.artifacts["report_json"].read_text(encoding="utf-8"))
            self.assertFalse(report["success"])
            self.assertFalse(report["build"]["success"])

    def test_existing_run_name_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory(prefix="free-code-lab-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            source = make_source_workspace(root)
            runner = FreeCodeLabRunner(test_config(root))
            runner._audit = lambda workspace: {"attempted": True, "success": True, "errors_count": 0, "warnings_count": 0}  # type: ignore[method-assign]

            runner.run(
                "Add an experimental sample.",
                from_workspace=source,
                run_name="unit-no-overwrite",
                llm_provider="mock",
                run_build=False,
            )

            with self.assertRaises(FileExistsError):
                runner.run(
                    "Add another experimental sample.",
                    from_workspace=source,
                    run_name="unit-no-overwrite",
                    llm_provider="mock",
                    run_build=False,
                )

    def test_manual_checklist_missing_blocks_harvest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="free-code-lab-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            candidate = harvest_candidate_payload(
                run_id="unit",
                request="Add runtime GUI",
                plan=FreeCodePlan(request="Add runtime GUI", gap="advanced_machine_gui"),
                source_workspace=root / "source",
                lab_workspace=root / "lab",
                changed_files=[],
                build=BuildResult(attempted=True, success=True, summary="mock build"),
                audit_payload={"attempted": True, "success": True},
                manual_runtime_checklist_path=root / "missing-checklist.md",
                success=True,
                errors=[],
            )

            self.assertEqual(candidate["recommendation"], "reject")
            self.assertIn("manual_runtime_checklist_missing", candidate["blockers"])
            self.assertFalse(candidate["ready_to_harvest"])

    def test_harvest_report_aggregates_candidates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="free-code-lab-", dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            candidate_dir = root / "free-code-lab-runs" / "unit-lab" / ".agent"
            candidate_dir.mkdir(parents=True)
            (candidate_dir / "harvest-candidate.json").write_text(
                json.dumps(
                    {
                        "run_id": "unit-lab",
                        "request": "Add machine GUI",
                        "generate_gap": "advanced_machine_gui",
                        "harvest_direction": "java_generator_template",
                        "recommendation": "keep_as_lab_sample",
                        "ready_to_harvest": False,
                    }
                ),
                encoding="utf-8",
            )

            result = HarvestReportRunner(test_config(root)).run(run_name="unit-harvest")

            self.assertTrue(result.success)
            self.assertEqual(len(result.candidates), 1)
            self.assertEqual(result.metrics["total_candidates"], 1)
            self.assertEqual(result.metrics["recommendations"]["keep_as_lab_sample"], 1)
            self.assertTrue(result.report_json_path.exists())
            self.assertTrue(result.report_md_path.exists())


if __name__ == "__main__":
    unittest.main()
