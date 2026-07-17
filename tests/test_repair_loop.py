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

from neoforge_agent import AppConfig, AutoRepairRunner, ModProjectPlanner, WorkspaceAuditor


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class RepairLoopTests(unittest.TestCase):
    def test_repair_loop_regenerates_missing_managed_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            generation = planner.execute(
                "Create a ruby mod with ruby.",
                workspace_name="repair-loop-ruby",
                overwrite=True,
                run_build=False,
            )
            self.assertTrue(generation.succeeded)

            workspace = generation.workspace_dir
            model_path = workspace / "src" / "main" / "resources" / "assets" / "ruby_mod" / "models" / "item" / "ruby.json"
            self.assertTrue(model_path.exists())
            model_path.unlink()

            broken_audit = WorkspaceAuditor(config).audit_workspace(workspace)
            self.assertFalse(broken_audit.success)

            result = AutoRepairRunner(config).run(
                workspace,
                max_attempts=1,
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(result.success)
            self.assertTrue(result.repaired)
            self.assertEqual(len(result.attempts), 2)
            self.assertEqual(result.attempts[1].action, "regenerate_managed_files")
            self.assertTrue(model_path.exists())
            self.assertTrue(result.repair_loop_report_json_path.exists())
            self.assertTrue(result.repair_loop_report_md_path.exists())

    def test_repair_loop_healthy_workspace_is_noop(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            generation = planner.execute(
                "Create a ruby mod with ruby.",
                workspace_name="repair-loop-healthy",
                overwrite=True,
                run_build=False,
            )
            self.assertTrue(generation.succeeded)

            result = AutoRepairRunner(config).run(
                generation.workspace_dir,
                max_attempts=1,
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(result.success)
            self.assertFalse(result.repaired)
            self.assertEqual(len(result.attempts), 1)

    def test_repair_loop_regenerates_missing_texture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            generation = planner.execute(
                "Create a ruby mod with ruby.",
                workspace_name="repair-loop-texture",
                overwrite=True,
                run_build=False,
            )
            self.assertTrue(generation.succeeded)

            workspace = generation.workspace_dir
            texture_path = workspace / "src" / "main" / "resources" / "assets" / "ruby_mod" / "textures" / "item" / "ruby.png"
            self.assertTrue(texture_path.exists())
            texture_path.unlink()

            broken_audit = WorkspaceAuditor(config).audit_workspace(workspace)
            self.assertFalse(broken_audit.success)

            result = AutoRepairRunner(config).run(
                workspace,
                max_attempts=1,
                run_build=False,
                run_audit=True,
            )

            self.assertTrue(result.success)
            self.assertTrue(result.repaired)
            self.assertTrue(texture_path.exists())

    def test_repair_loop_regenerates_broken_ore_rule_test(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            planner = ModProjectPlanner(config)
            generation = planner.execute(
                "Add ruby ore that generates underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk.",
                workspace_name="repair-loop-ore-rule-test",
                overwrite=True,
                run_build=False,
            )
            self.assertTrue(generation.succeeded)

            workspace = generation.workspace_dir
            configured = workspace / "src" / "main" / "resources" / "data" / "ruby_mod" / "worldgen" / "configured_feature" / "ruby_ore.json"
            payload = json.loads(configured.read_text(encoding="utf-8"))
            payload["config"]["targets"][0]["target"] = "minecraft:stone_ore_replaceables"
            configured.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            broken_audit = WorkspaceAuditor(config).audit_workspace(workspace)
            self.assertFalse(broken_audit.success)
            self.assertTrue(any(issue.id == "ore:ruby_ore:configured_rule_test" for issue in broken_audit.errors))

            result = AutoRepairRunner(config).run(
                workspace,
                max_attempts=1,
                run_build=False,
                run_audit=True,
            )

            repaired = json.loads(configured.read_text(encoding="utf-8"))
            repaired_targets = repaired["config"]["targets"]
            rule_test = repaired_targets[0]["target"]
            self.assertTrue(result.success)
            self.assertTrue(result.repaired)
            self.assertEqual(rule_test["predicate_type"], "minecraft:tag_match")
            self.assertEqual(rule_test["tag"], "minecraft:stone_ore_replaceables")
            self.assertEqual(repaired_targets[1]["target"]["tag"], "minecraft:deepslate_ore_replaceables")
            self.assertTrue(all(target["state"]["Name"] == "ruby_mod:ruby_ore" for target in repaired_targets))


if __name__ == "__main__":
    unittest.main()
