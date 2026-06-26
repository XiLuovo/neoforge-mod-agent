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


class BalancePlannerTests(unittest.TestCase):
    def test_balance_plan_from_dict_round_trips_features_and_top_level_list(self) -> None:
        data = json.loads((PROJECT_ROOT / "examples" / "balance_gameplay_loop.json").read_text(encoding="utf-8"))

        spec = ModSpec.from_dict(data)
        payload = spec.to_dict()

        self.assertEqual(len(spec.balance_plans), 1)
        self.assertEqual(spec.balance_plans[0].identifier, "ruby_balance_plan")
        self.assertEqual(spec.balance_plans[0].target_progression, "ruby_progression")
        self.assertIn("balance_plans", payload)
        self.assertIn("balance_plan", {feature["type"] for feature in payload["features"]})

    def test_balance_validator_rejects_unknown_target_progression(self) -> None:
        spec = ModSpec.from_dict(
            {
                "mod_id": "balance_mod",
                "mod_name": "Balance Mod",
                "package": "com.generated.balance_mod",
                "version": "0.1.0",
                "features": [
                    {
                        "type": "balance_plan",
                        "id": "bad_balance_plan",
                        "title": "Bad Balance Plan",
                        "target_progression": "missing_loop",
                    }
                ],
                "requested_features": ["Balance Planner"],
            }
        )

        report = validate_mod_spec(spec, AppConfig.default())

        self.assertFalse(report.is_valid)
        self.assertTrue(any("target_progression" in issue.message for issue in report.errors))

    def test_balance_generation_passes_audit_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            spec = planner.spec_from_file(PROJECT_ROOT / "examples" / "balance_gameplay_loop.json")

            result = planner.execute_spec(
                spec,
                workspace_name="balance",
                overwrite=True,
                run_build=False,
            )
            audit = WorkspaceAuditor(config).audit_workspace(result.workspace_dir)

            self.assertTrue(result.succeeded)
            self.assertTrue(audit.success)
            self.assertIn(".agent\\balance-report.json", result.generated_files)
            self.assertIn(".agent\\balance-report.md", result.generated_files)
            summary = json.loads((result.workspace_dir / ".agent" / "generation-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["features_count"]["balance_plans"], 1)
            report = json.loads((result.workspace_dir / ".agent" / "balance-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["version"], "7.1")
            self.assertEqual(report["totals"]["plan_count"], 1)
            self.assertGreaterEqual(report["totals"]["recipe_recommendations_count"], 2)
            self.assertGreaterEqual(report["totals"]["missing_recipe_suggestions_count"], 1)
            self.assertGreaterEqual(report["totals"]["machine_balance_rules_count"], 1)
            self.assertGreaterEqual(report["totals"]["entity_drop_rules_count"], 1)
            self.assertGreaterEqual(report["totals"]["loot_weight_rules_count"], 1)
            self.assertEqual(report["plans"][0]["missing_recipes"][0]["target"], "ruby_compressor")

    def test_rules_and_mock_llm_plan_balance_layer(self) -> None:
        planner = ModProjectPlanner(AppConfig.default())

        rules_spec = planner.parse_request("Create a recipe loot balance economy gameplay loop with rarity, machine cost, and energy cost.")
        mock_spec, artifacts = plan_with_llm(
            "Create a recipe loot balance economy gameplay loop.",
            MockLLMClient(PROJECT_ROOT),
            config=AppConfig.default(),
        )

        self.assertEqual(artifacts.warnings, [])
        self.assertEqual(len(rules_spec.progressions), 1)
        self.assertEqual(len(rules_spec.balance_plans), 1)
        self.assertEqual(len(mock_spec.balance_plans), 1)
        self.assertIn("Balance Planner", rules_spec.requested_features)
        self.assertEqual(rules_spec.balance_plans[0].target_progression, "ruby_progression")


if __name__ == "__main__":
    unittest.main()
