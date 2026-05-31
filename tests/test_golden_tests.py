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

from neoforge_agent import AppConfig, GoldenTestRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class GoldenTestRunnerTests(unittest.TestCase):
    def test_golden_runner_writes_report_and_checks_basic_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = GoldenTestRunner(config).run(run_name="unit-golden", limit=1)

            self.assertTrue(result.success)
            self.assertEqual(len(result.cases), 1)
            self.assertTrue(result.golden_report_json_path.exists())
            self.assertTrue(result.golden_report_md_path.exists())

            payload = json.loads(result.golden_report_json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["cases_count"], 1)
            self.assertEqual(payload["passed_count"], 1)
            case = payload["cases"][0]
            self.assertEqual(case["id"], "basic_ruby_item")
            self.assertIn("ruby", case["feature_ids"])
            self.assertGreaterEqual(case["generated_files_count"], 7)
            check_ids = {check["id"] for check in case["checks"]}
            self.assertIn("json:src/main/resources/assets/ruby_mod/models/item/ruby.json:field:parent", check_ids)
            self.assertIn("path:src/main/resources/assets/ruby_mod/models/item/ruby.json", check_ids)


if __name__ == "__main__":
    unittest.main()
