from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "quality-gate.yml"


class CiWorkflowTests(unittest.TestCase):
    def test_quality_gate_workflow_exists_and_runs_fast_gate(self) -> None:
        self.assertTrue(WORKFLOW_PATH.exists(), "quality gate workflow should exist")

        content = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("Quality Gate", content)
        self.assertIn("actions/checkout@v4", content)
        self.assertIn("actions/setup-python@v5", content)
        self.assertIn('python-version: "3.11"', content)
        self.assertIn("PYTHONPATH: src", content)
        self.assertIn("python -m agent.cli quality-gate --run-name ci-quality-gate --json", content)
        self.assertIn("actions/upload-artifact@v4", content)
        self.assertIn("workspace/quality-gate-runs/ci-quality-gate/.agent/**", content)
        self.assertIn("workspace/doctor-runs/ci-quality-gate-doctor/.agent/**", content)
        self.assertNotIn("--build-smoke", content)
        self.assertNotIn("--no-doctor", content)


if __name__ == "__main__":
    unittest.main()
