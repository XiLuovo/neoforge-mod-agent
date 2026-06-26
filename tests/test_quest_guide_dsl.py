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

from neoforge_agent import AppConfig, MockLLMClient, ModProjectPlanner, ModSpec, WorkspaceAuditor, plan_with_llm
from neoforge_agent.validator import validate_mod_spec


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


def normalize_paths(paths: list[str]) -> set[str]:
    return {path.replace("\\", "/") for path in paths}


class QuestGuideDslTests(unittest.TestCase):
    def test_quest_from_dict_round_trips_features_and_top_level_list(self) -> None:
        data = json.loads((PROJECT_ROOT / "examples" / "quest_guide_gameplay_loop.json").read_text(encoding="utf-8"))

        spec = ModSpec.from_dict(data)
        payload = spec.to_dict()

        self.assertEqual(len(spec.quests), 1)
        self.assertEqual(spec.quests[0].identifier, "ruby_questline")
        self.assertEqual(spec.quests[0].tasks[0].task_type, "mine_block")
        self.assertIn("quests", payload)
        self.assertIn("quest", {feature["type"] for feature in payload["features"]})

    def test_quest_validator_rejects_bad_parent_and_unknown_progression(self) -> None:
        spec = ModSpec.from_dict(
            {
                "mod_id": "quest_mod",
                "mod_name": "Quest Mod",
                "package": "com.generated.quest_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "quest",
                        "id": "bad_quest",
                        "title": "Bad Quest",
                        "target_progression": "missing_progression",
                        "tasks": [
                            {
                                "id": "followup",
                                "title": "Followup",
                                "task_type": "milestone",
                                "parent": "missing_parent",
                            }
                        ],
                    }
                ],
            }
        )

        report = validate_mod_spec(spec, AppConfig.default())

        self.assertFalse(report.is_valid)
        self.assertTrue(any("target_progression" in issue.message for issue in report.errors))
        self.assertTrue(any("parent references unknown" in issue.message for issue in report.errors))

    def test_quest_generation_passes_audit_and_writes_reports_and_resources(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "quest_guide_gameplay_loop.json")

            result = planner.execute_spec(
                spec,
                workspace_name="quest",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)
            generated = normalize_paths(result.generated_files)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            self.assertIn(".agent/quest-report.json", generated)
            self.assertIn(".agent/quest-report.md", generated)
            self.assertIn(".agent/guidebook.md", generated)
            self.assertIn(".agent/behavior-report.json", generated)
            self.assertIn(".agent/behavior-report.md", generated)
            self.assertIn("src/main/resources/data/quest_mod/advancement/ruby_questline/mine_ruby_ore.json", generated)
            self.assertIn("src/main/resources/data/quest_mod/patchouli_books/ruby_guidebook/book.json", generated)
            summary = json.loads((result.workspace_dir / ".agent" / "generation-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["features_count"]["quests"], 1)
            report = json.loads((result.workspace_dir / ".agent" / "quest-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["version"], "7.2")
            self.assertEqual(report["totals"]["quest_count"], 1)
            self.assertEqual(report["totals"]["task_count"], 2)
            self.assertEqual(report["totals"]["advancement_count"], 2)
            self.assertIsNotNone(report["quests"][0]["behavior"])
            report_md = (result.workspace_dir / ".agent" / "quest-report.md").read_text(encoding="utf-8")
            self.assertIn("### Behavior", report_md)
            behavior_report = json.loads((result.workspace_dir / ".agent" / "behavior-report.json").read_text(encoding="utf-8"))
            self.assertEqual(behavior_report["totals"]["host_type_counts"]["quest"], 1)
            self.assertEqual(behavior_report["totals"]["host_type_counts"]["progression"], 1)
            self.assertEqual(behavior_report["totals"]["report_only_host_count"], 2)
            self.assertGreaterEqual(behavior_report["totals"]["trigger_counts"]["guide_open"], 1)

    def test_rules_and_mock_llm_plan_quest_layer(self) -> None:
        planner = ModProjectPlanner(AppConfig.default())

        rules_spec = planner.parse_request("Create a quest advancement guidebook for a progression gameplay loop.")
        mock_spec, artifacts = plan_with_llm(
            "Create a quest advancement guidebook for a gameplay loop.",
            MockLLMClient(PROJECT_ROOT),
            config=AppConfig.default(),
        )

        self.assertEqual(artifacts.warnings, [])
        self.assertEqual(len(rules_spec.progressions), 1)
        self.assertEqual(len(rules_spec.quests), 1)
        self.assertEqual(len(mock_spec.quests), 1)
        self.assertIn("Quests", rules_spec.requested_features)
        self.assertIn("Advancements", rules_spec.requested_features)
        self.assertIn("Guidebook", rules_spec.requested_features)
        self.assertEqual(rules_spec.quests[0].target_progression, "ruby_progression")


if __name__ == "__main__":
    unittest.main()
