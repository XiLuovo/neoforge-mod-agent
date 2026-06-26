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

from neoforge_agent import AppConfig
from neoforge_agent.tools import prepare_workspace_dir, resolve_workspace_child
from neoforge_agent.workspace_materializer import WorkspaceMaterializer


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class WorkspaceSafetyTests(unittest.TestCase):
    def test_prepare_workspace_dir_rejects_path_escape_names(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp) / "workspace")
            config.workspace_root.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()

            with self.assertRaises(ValueError):
                prepare_workspace_dir(config, "ruby_mod", workspace_name="..\\outside", overwrite=True)

            with self.assertRaises(ValueError):
                prepare_workspace_dir(config, "ruby_mod", workspace_name=str(outside), overwrite=True)

            self.assertTrue(outside.exists())

    def test_resolve_workspace_child_allows_simple_names_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            root = Path(tmp) / "workspace"
            target = resolve_workspace_child(root, "safe-ruby")

            self.assertEqual(target, (root / "safe-ruby").resolve())
            with self.assertRaises(ValueError):
                resolve_workspace_child(root, "../escape")
            with self.assertRaises(ValueError):
                resolve_workspace_child(root, "nested/name")

    def test_cleanup_managed_files_ignores_paths_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            workspace = Path(tmp) / "workspace" / "ruby"
            agent_dir = workspace / ".agent"
            agent_dir.mkdir(parents=True)
            safe_file = workspace / "src" / "main" / "resources" / "pack.mcmeta"
            safe_file.parent.mkdir(parents=True)
            safe_file.write_text("safe", encoding="utf-8")
            outside_file = Path(tmp) / "outside.txt"
            outside_file.write_text("outside", encoding="utf-8")
            (agent_dir / "generation-summary.json").write_text(
                json.dumps(
                    {
                        "generated_files": [
                            "src/main/resources/pack.mcmeta",
                            "../../outside.txt",
                            str(outside_file),
                        ]
                    }
                ),
                encoding="utf-8",
            )

            WorkspaceMaterializer(test_config(Path(tmp) / "workspace")).cleanup_managed_files(workspace)

            self.assertFalse(safe_file.exists())
            self.assertTrue(outside_file.exists())


if __name__ == "__main__":
    unittest.main()
