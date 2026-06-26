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

from neoforge_agent import AppConfig, LLMReviewer


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root, project_root=PROJECT_ROOT)


class LLMReviewerTests(unittest.TestCase):
    def review_goal(self, goal: str):
        with tempfile.TemporaryDirectory(prefix="llm-reviewer-", dir=TMP_ROOT) as tmp:
            reviewer = LLMReviewer(test_config(Path(tmp)))
            return reviewer.review(
                workspace=Path(tmp),
                user_goal=goal,
                llm_provider="mock",
                review_stage="unit",
                intent_contract={"requirements": [goal]},
                modspec={"mod_id": "ruby_mod", "features": [{"id": "ruby"}]},
                rag={"hits": [{"id": "rag-1", "title": "NeoForge resource basics"}]},
                tool_call_trace=[
                    {
                        "iteration": 1,
                        "source": "llm",
                        "action": "run_audit",
                        "observation": {"success": True, "summary": "Workspace audit passed."},
                    }
                ],
                changed_files=["src/main/resources/pack.mcmeta"],
                audit_result={"attempted": True, "success": True, "summary": "Workspace audit passed."},
                build_result={"attempted": False, "success": None, "summary": "Build skipped."},
            )

    def test_reviewer_approve_case(self) -> None:
        result = self.review_goal("Create a ruby mod with ruby.")

        self.assertTrue(result.success)
        self.assertEqual(result.coverage_status, "pass")
        self.assertEqual(result.decision, "approve")
        self.assertEqual(result.prompt_trace.role, "reviewer_agent")
        self.assertEqual(result.prompt_trace.prompt_kind, "reviewer_unit")
        self.assertEqual(result.prompt_trace.normalized_json["decision"], "approve")

    def test_reviewer_missing_requirement_case(self) -> None:
        result = self.review_goal("Create a ruby mod that must include missing requirement coverage.")

        self.assertFalse(result.success)
        self.assertEqual(result.coverage_status, "fail")
        self.assertEqual(result.decision, "reject")
        self.assertTrue(result.reviewer_report["missing_requirements"])
        self.assertEqual(result.prompt_trace.normalized_json["coverage_status"], "fail")

    def test_reviewer_needs_repair_case(self) -> None:
        result = self.review_goal("Create a ruby mod; reviewer needs repair before acceptance.")

        self.assertFalse(result.success)
        self.assertEqual(result.coverage_status, "partial")
        self.assertEqual(result.decision, "needs_repair")
        self.assertTrue(result.reviewer_report["recommended_checks"])
        self.assertEqual(result.prompt_trace.normalized_json["decision"], "needs_repair")

    def test_sensitive_patch_without_evidence_requires_more_rag(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-reviewer-", dir=TMP_ROOT) as tmp:
            reviewer = LLMReviewer(test_config(Path(tmp)))
            result = reviewer.review(
                workspace=Path(tmp),
                user_goal="Fix pack.mcmeta audit failures.",
                llm_provider="mock",
                review_stage="unit",
                intent_contract={"requirements": ["Fix pack.mcmeta audit failures."]},
                modspec={"mod_id": "ruby_mod", "features": [{"id": "ruby"}]},
                rag={"hits": [], "citations": []},
                tool_call_trace=[
                    {
                        "iteration": 1,
                        "source": "llm",
                        "action": "apply_structured_patch",
                        "observation": {
                            "success": True,
                            "changed_files": ["src/main/resources/pack.mcmeta"],
                            "citation_ids": [],
                        },
                    }
                ],
                changed_files=["src/main/resources/pack.mcmeta"],
                audit_result={"attempted": True, "success": True, "summary": "Workspace audit passed."},
                build_result={"attempted": False, "success": None, "summary": "Build skipped."},
            )

        self.assertFalse(result.success)
        self.assertEqual(result.decision, "needs_repair")
        self.assertEqual(result.coverage_status, "partial")
        self.assertEqual(result.reviewer_report["evidence_sufficiency"], "insufficient")
        self.assertTrue(result.reviewer_report["requires_more_rag"])
        self.assertTrue(result.reviewer_report["unsupported_citation_gaps"])


if __name__ == "__main__":
    unittest.main()
