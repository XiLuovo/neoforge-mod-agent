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


class ProgressionDslTests(unittest.TestCase):
    def test_progression_from_dict_round_trips_features_and_top_level_list(self) -> None:
        data = json.loads((PROJECT_ROOT / "examples" / "progression_gameplay_loop.json").read_text(encoding="utf-8"))

        spec = ModSpec.from_dict(data)
        payload = spec.to_dict()

        self.assertEqual(len(spec.progressions), 1)
        self.assertEqual(spec.progressions[0].identifier, "ruby_progression")
        self.assertEqual(spec.progressions[0].stages[0].identifier, "mine_ruby_ore")
        self.assertIn("progressions", payload)
        self.assertIn("progression", {feature["type"] for feature in payload["features"]})

    def test_progression_validator_warns_for_missing_references(self) -> None:
        spec = ModSpec.from_dict(
            {
                "mod_id": "progression_mod",
                "mod_name": "Progression Mod",
                "package": "com.generated.progression_mod",
                "version": "0.1.0",
                "features": [
                    {"type": "item", "id": "ruby", "display_name_en_us": "Ruby"},
                    {
                        "type": "progression",
                        "id": "missing_reference_loop",
                        "title": "Missing Reference Loop",
                        "stages": [
                            {
                                "id": "start",
                                "type": "material",
                                "title": "Start",
                                "evidence": ["ruby", "missing_relic"],
                            }
                        ],
                    },
                ],
                "requested_features": ["Progression"],
            }
        )

        report = validate_mod_spec(spec, AppConfig.default())

        self.assertTrue(report.is_valid)
        self.assertTrue(any("missing_relic" in issue.message for issue in report.warnings))

    def test_progression_validator_rejects_unknown_link_stage(self) -> None:
        spec = ModSpec.from_dict(
            {
                "mod_id": "progression_mod",
                "mod_name": "Progression Mod",
                "package": "com.generated.progression_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "progression",
                        "id": "bad_link_loop",
                        "title": "Bad Link Loop",
                        "stages": [
                            {"id": "start", "type": "milestone", "title": "Start"},
                        ],
                        "links": [
                            {"from": "start", "to": "missing_stage"},
                        ],
                    }
                ],
            }
        )

        report = validate_mod_spec(spec, AppConfig.default())

        self.assertFalse(report.is_valid)
        self.assertTrue(any("unknown to stage" in issue.message for issue in report.errors))

    def test_progression_generation_passes_audit_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "progression_gameplay_loop.json")

            result = planner.execute_spec(
                spec,
                workspace_name="progression",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            self.assertIn(".agent\\progression-report.json", result.generated_files)
            self.assertIn(".agent\\progression-report.md", result.generated_files)
            self.assertIn(".agent\\behavior-report.json", result.generated_files)
            self.assertIn(".agent\\behavior-report.md", result.generated_files)
            summary = json.loads((result.workspace_dir / ".agent" / "generation-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["features_count"]["progressions"], 1)
            report = json.loads((result.workspace_dir / ".agent" / "progression-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["version"], "7.0")
            self.assertEqual(report["totals"]["loop_count"], 1)
            self.assertEqual(report["totals"]["missing_references_total"], 0)
            self.assertTrue(report["progressions"][0]["graph"]["entry_reaches_end"])
            self.assertIsNotNone(report["progressions"][0]["behavior"])
            behavior_report = json.loads((result.workspace_dir / ".agent" / "behavior-report.json").read_text(encoding="utf-8"))
            self.assertEqual(behavior_report["totals"]["host_type_counts"]["progression"], 1)
            self.assertEqual(behavior_report["totals"]["host_type_counts"]["machine"], 1)
            self.assertEqual(behavior_report["totals"]["host_type_counts"]["entity"], 1)
            self.assertEqual(behavior_report["totals"]["report_only_host_count"], 3)
            self.assertGreaterEqual(behavior_report["totals"]["chain_action_count"], 1)

    def test_rules_and_mock_llm_plan_progression_loop(self) -> None:
        planner = ModProjectPlanner(AppConfig.default())

        rules_spec = planner.parse_request("Create a progression gameplay loop: ore -> material -> machine -> equipment -> structure -> dimension.")
        mock_spec, artifacts = plan_with_llm(
            "Create a progression gameplay loop for a full mod.",
            MockLLMClient(PROJECT_ROOT),
            config=AppConfig.default(),
        )

        self.assertEqual(artifacts.warnings, [])
        self.assertEqual(len(rules_spec.progressions), 1)
        self.assertEqual(len(mock_spec.progressions), 1)
        self.assertIn("Progression", rules_spec.requested_features)
        self.assertEqual(rules_spec.progressions[0].end_stage, "enter_ruby_realm")


if __name__ == "__main__":
    unittest.main()
