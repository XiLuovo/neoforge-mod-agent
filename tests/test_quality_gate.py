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

from neoforge_agent import AppConfig, QualityGateRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class QualityGateTests(unittest.TestCase):
    def test_quality_gate_can_run_schema_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = QualityGateRunner(config).run(
                run_name="unit-quality-gate",
                run_compile=False,
                run_unittest=False,
                run_schema=True,
                run_examples=False,
                run_eval=False,
                run_golden=False,
                run_failure_lab=False,
                run_repair_eval=False,
                run_build_smoke=False,
            )

            self.assertTrue(result.success)
            statuses = {check.name: check.status for check in result.checks}
            self.assertEqual(statuses["doctor_environment"], "pass")
            self.assertEqual(statuses["print_schema"], "pass")
            self.assertEqual(statuses["unittest"], "skip")
            self.assertEqual(statuses["golden_tests"], "skip")
            self.assertEqual(statuses["failure_lab"], "skip")
            self.assertEqual(statuses["repair_eval"], "skip")
            self.assertTrue(result.quality_gate_report_json_path.exists())
            self.assertTrue(result.quality_gate_report_md_path.exists())

    def test_quality_gate_can_skip_doctor(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = QualityGateRunner(config).run(
                run_name="unit-quality-gate-no-doctor",
                run_doctor=False,
                run_compile=False,
                run_unittest=False,
                run_schema=False,
                run_examples=False,
                run_eval=False,
                run_golden=False,
                run_failure_lab=False,
                run_repair_eval=False,
                run_build_smoke=False,
            )

            self.assertTrue(result.success)
            statuses = {check.name: check.status for check in result.checks}
            self.assertEqual(statuses["doctor_environment"], "skip")

    def test_quality_gate_can_run_failure_lab_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = QualityGateRunner(config).run(
                run_name="unit-quality-gate-failure-lab",
                run_doctor=False,
                run_compile=False,
                run_unittest=False,
                run_schema=False,
                run_examples=False,
                run_eval=False,
                run_golden=False,
                run_failure_lab=True,
                run_repair_eval=False,
                run_build_smoke=False,
            )

            self.assertTrue(result.success)
            statuses = {check.name: check.status for check in result.checks}
            self.assertEqual(statuses["failure_lab"], "pass")

    def test_quality_gate_can_run_repair_eval_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = QualityGateRunner(config).run(
                run_name="unit-quality-gate-repair-eval",
                run_doctor=False,
                run_compile=False,
                run_unittest=False,
                run_schema=False,
                run_examples=False,
                run_eval=False,
                run_golden=False,
                run_failure_lab=False,
                run_repair_eval=True,
                run_build_smoke=False,
            )

            self.assertTrue(result.success)
            statuses = {check.name: check.status for check in result.checks}
            self.assertEqual(statuses["repair_eval"], "pass")


if __name__ == "__main__":
    unittest.main()
