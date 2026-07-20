from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from neoforge_agent.semantic_coverage import (
    evaluate_semantic_coverage,
    evaluate_stability_report_semantics,
    write_stability_semantic_report,
)


class SemanticCoverageTests(unittest.TestCase):
    def test_feature_match_does_not_hide_missing_behavior_category(self) -> None:
        result = evaluate_semantic_coverage(
            expected_features=["ruby_sword"],
            expected_categories=["sword", "behavior", "sword_ignite"],
            modspec={
                "features": [
                    {
                        "type": "sword",
                        "id": "ruby_sword",
                        "display_name_en_us": "Ruby Sword",
                    }
                ]
            },
        )

        self.assertEqual(result.matched_expected_features, ["ruby_sword"])
        self.assertEqual(result.missing_expected_categories, ["behavior", "sword_ignite"])
        self.assertFalse(result.semantic_success)

    def test_failed_process_cannot_be_semantically_successful(self) -> None:
        result = evaluate_semantic_coverage(
            expected_features=[],
            expected_categories=[],
            modspec=None,
            process_success=False,
        )

        self.assertFalse(result.semantic_success)

    def test_semantic_warnings_are_classified_and_deduplicated(self) -> None:
        ignored = "Decomposed planner v1 ignored unsupported feature type: block"
        removed = "Decomposed feature 'ruby_sword' had empty behavior type; removed behavior."
        progression = "Progression 'ruby_progression' has multiple stages but no links."
        result = evaluate_semantic_coverage(
            expected_features=[],
            expected_categories=[],
            modspec={"features": []},
            warnings=[ignored, ignored, removed, progression, "Recipe id normalized."],
        )

        self.assertEqual(result.ignored_feature_warnings, [ignored])
        self.assertEqual(result.removed_behavior_warnings, [removed])
        self.assertEqual(result.semantic_warnings, [ignored, removed, progression])

    def test_existing_stability_report_can_be_evaluated_without_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ruby-workspace"
            agent_dir = workspace / ".agent"
            agent_dir.mkdir(parents=True)
            (agent_dir / "modspec.json").write_text(
                json.dumps({"features": [{"type": "item", "id": "ruby"}]}),
                encoding="utf-8",
            )
            report = {
                "run_id": "existing-run",
                "cases": [
                    {
                        "id": "basic_ruby",
                        "strict_success": True,
                        "workspace": str(workspace),
                        "warnings": [],
                    },
                    {
                        "id": "ruby_realm",
                        "strict_success": False,
                        "workspace": None,
                        "warnings": [],
                    },
                ],
            }
            cases = [
                {
                    "id": "basic_ruby",
                    "expected_features": ["ruby"],
                    "expected_categories": ["item"],
                },
                {
                    "id": "ruby_realm",
                    "expected_features": ["ruby_realm"],
                    "expected_categories": ["dimension"],
                },
            ]

            semantic_report = evaluate_stability_report_semantics(report, cases)

        self.assertEqual(semantic_report["metrics"]["semantic_success_count"], 1)
        self.assertEqual(semantic_report["metrics"]["expected_features_matched"], 1)
        self.assertFalse(semantic_report["cases"][1]["semantic_success"])

    def test_semantic_report_writer_creates_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent_dir = workspace / ".agent"
            agent_dir.mkdir(parents=True)
            (agent_dir / "modspec.json").write_text(
                json.dumps({"features": [{"type": "item", "id": "ruby"}]}),
                encoding="utf-8",
            )
            report_path = root / "real-llm-stability.json"
            report_path.write_text(
                json.dumps(
                    {
                        "run_id": "writer-run",
                        "cases": [
                            {
                                "id": "basic_ruby",
                                "strict_success": True,
                                "workspace": str(workspace),
                                "warnings": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            cases_path = root / "cases.json"
            cases_path.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "basic_ruby",
                                "expected_features": ["ruby"],
                                "expected_categories": ["item"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            json_path, markdown_path = write_stability_semantic_report(report_path, cases_path)

            self.assertTrue(json_path.is_file())
            self.assertTrue(markdown_path.is_file())
            self.assertIn("semantic success: `1/1`", markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
