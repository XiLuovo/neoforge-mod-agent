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

from neoforge_agent import AppConfig, RepairRAGAdvisor


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class RepairRAGTests(unittest.TestCase):
    def test_repair_rag_advisor_retrieves_texture_audit_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))
            workspace = Path(tmp) / "repair-rag-texture"
            workspace.mkdir()

            result = RepairRAGAdvisor(config).advise(
                workspace,
                root_causes=["Missing generated texture for ruby item."],
                repair_plan=[
                    {
                        "id": "inspect_audit_report",
                        "summary": "Read audit-report.json and regenerate managed files from ModSpec.",
                        "artifact": str(workspace / ".agent" / "audit-report.json"),
                    }
                ],
                build_payload={},
                audit_payload={
                    "attempted": True,
                    "success": False,
                    "errors": [
                        {
                            "id": "texture:ruby",
                            "message": "Missing generated texture file src/main/resources/assets/ruby_mod/textures/item/ruby.png in texture-manifest.",
                            "path": "src/main/resources/assets/ruby_mod/textures/item/ruby.png",
                        }
                    ],
                    "audit_report_path": str(workspace / ".agent" / "audit-report.json"),
                },
            )

            self.assertTrue(result.success)
            self.assertTrue(result.attempted)
            self.assertGreater(result.hits_count, 0)
            self.assertTrue(result.report_json_path and result.report_json_path.exists())
            self.assertTrue(result.report_md_path and result.report_md_path.exists())
            self.assertTrue({"texture_audit", "procedural_textures", "assets_models_textures"} & set(result.capabilities))

            payload = json.loads(result.report_json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["hits_count"], result.hits_count)
            self.assertIn("repair audit build failure", payload["query"])


if __name__ == "__main__":
    unittest.main()
