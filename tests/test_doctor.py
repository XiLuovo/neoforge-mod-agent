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

from neoforge_agent import AppConfig, EnvironmentDoctor


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class DoctorTests(unittest.TestCase):
    def test_doctor_writes_reports_and_checks_core_layout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = EnvironmentDoctor(config).run(
                run_name="unit-doctor",
                check_java=False,
            )

            self.assertTrue(result.success)
            self.assertTrue(result.doctor_report_json_path.exists())
            self.assertTrue(result.doctor_report_md_path.exists())

            statuses = {check.id: check.status for check in result.checks}
            self.assertEqual(statuses["python.version"], "pass")
            self.assertEqual(statuses["template.root"], "pass")
            self.assertEqual(statuses["template.gradlew_bat"], "pass")
            self.assertIn(statuses["llm.openai_compatible"], {"pass", "warning"})
            self.assertEqual(statuses["java.version"], "skip")


if __name__ == "__main__":
    unittest.main()
