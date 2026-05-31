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

from neoforge_agent import AppConfig, BuildResult, DirectCodeAgent, DirectCodeChange, DirectCodePlan


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


def java_change(path: str, content: str | None = None) -> DirectCodeChange:
    return DirectCodeChange(
        path=path,
        operation="write_file",
        content=content
        or "package com.generated.test;\n\npublic final class DirectCodeSample {\n}\n",
        reason="unit test",
        risk_level="low",
    )


class DirectCodeAgentTests(unittest.TestCase):
    def test_review_rejects_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="direct-code-", dir=TMP_ROOT) as tmp:
            workspace = Path(tmp)
            agent = DirectCodeAgent(test_config(workspace))

            cases = [
                "../outside.java",
                "/tmp/outside.java",
                "C:/tmp/outside.java",
                "gradle/wrapper/gradle-wrapper.jar",
                ".git/config",
            ]
            for path in cases:
                with self.subTest(path=path):
                    result = agent.apply_plan(
                        workspace,
                        DirectCodePlan(request="unsafe", changes=[java_change(path)]),
                    )
                    self.assertFalse(result.success)
                    self.assertFalse(result.review.approved)
                    self.assertTrue(result.errors)

    def test_replace_text_requires_exactly_one_match(self) -> None:
        with tempfile.TemporaryDirectory(prefix="direct-code-", dir=TMP_ROOT) as tmp:
            workspace = Path(tmp)
            target = workspace / "src" / "main" / "resources" / "direct-code.txt"
            target.parent.mkdir(parents=True)
            target.write_text("alpha beta alpha\n", encoding="utf-8")
            agent = DirectCodeAgent(test_config(workspace))

            zero = agent.apply_plan(
                workspace,
                DirectCodePlan(
                    request="zero",
                    changes=[
                        DirectCodeChange(
                            path="src/main/resources/direct-code.txt",
                            operation="replace_text",
                            search="missing",
                            replace="ok",
                            reason="unit test",
                            risk_level="low",
                        )
                    ],
                ),
            )
            self.assertFalse(zero.success)
            self.assertIn("found 0", zero.errors[0])

            multiple = agent.apply_plan(
                workspace,
                DirectCodePlan(
                    request="multiple",
                    changes=[
                        DirectCodeChange(
                            path="src/main/resources/direct-code.txt",
                            operation="replace_text",
                            search="alpha",
                            replace="omega",
                            reason="unit test",
                            risk_level="low",
                        )
                    ],
                ),
            )
            self.assertFalse(multiple.success)
            self.assertIn("found 2", multiple.errors[0])

            single = agent.apply_plan(
                workspace,
                DirectCodePlan(
                    request="single",
                    changes=[
                        DirectCodeChange(
                            path="src/main/resources/direct-code.txt",
                            operation="replace_text",
                            search="beta",
                            replace="omega",
                            reason="unit test",
                            risk_level="low",
                        )
                    ],
                ),
            )
            self.assertTrue(single.success)
            self.assertEqual(target.read_text(encoding="utf-8"), "alpha omega alpha\n")

    def test_artifacts_snapshot_diff_and_rollback_report_are_written(self) -> None:
        with tempfile.TemporaryDirectory(prefix="direct-code-", dir=TMP_ROOT) as tmp:
            workspace = Path(tmp)
            agent = DirectCodeAgent(test_config(workspace))

            result = agent.apply_plan(
                workspace,
                DirectCodePlan(
                    request="write java",
                    summary="Add Java class.",
                    changes=[
                        java_change(
                            "src/main/java/com/generated/test/DirectCodeSample.java",
                            "package com.generated.test;\n\npublic final class DirectCodeSample {\n}\n",
                        )
                    ],
                ),
                build=BuildResult(attempted=True, success=True, summary="mock build"),
                audit_payload={"attempted": True, "success": True},
            )

            self.assertTrue(result.success)
            for artifact in result.artifacts.values():
                self.assertTrue(artifact.exists(), artifact)
            self.assertTrue((workspace / ".agent" / "direct-code-snapshots" / "src" / "main" / "java" / "com" / "generated" / "test" / "DirectCodeSample.java").exists())
            self.assertIn("DirectCodeSample", (workspace / ".agent" / "direct-code-diff.md").read_text(encoding="utf-8"))
            rollback = json.loads((workspace / ".agent" / "direct-code-rollback-report.json").read_text(encoding="utf-8"))
            self.assertEqual(rollback["status"], "not_needed")

    def test_java_package_must_match_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="direct-code-", dir=TMP_ROOT) as tmp:
            workspace = Path(tmp)
            agent = DirectCodeAgent(test_config(workspace))

            result = agent.apply_plan(
                workspace,
                DirectCodePlan(
                    request="bad package",
                    changes=[
                        java_change(
                            "src/main/java/com/generated/test/DirectCodeSample.java",
                            "package com.generated.other;\n\npublic final class DirectCodeSample {\n}\n",
                        )
                    ],
                ),
            )

            self.assertFalse(result.success)
            self.assertTrue(any("package declaration does not match" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
