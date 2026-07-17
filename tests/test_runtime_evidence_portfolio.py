from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from runtime_evidence_portfolio import build_draft, summary, validate


class RuntimeEvidencePortfolioTests(unittest.TestCase):
    def test_draft_is_explicitly_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            definitions = []
            for index in range(3):
                workspace = repo / f"workspace-{index}"
                (workspace / "build" / "libs").mkdir(parents=True)
                (workspace / ".agent" / "logs").mkdir(parents=True)
                (workspace / "build" / "libs" / "example.jar").write_bytes(f"jar-{index}".encode())
                (workspace / ".agent" / "modspec.json").write_text("{}", encoding="utf-8")
                (workspace / ".agent" / "audit-report.json").write_text("{}", encoding="utf-8")
                (workspace / ".agent" / "logs" / "gradle-build.json").write_text("{}", encoding="utf-8")
                definitions.append(
                    {
                        "id": f"case-{index}",
                        "title": f"Case {index}",
                        "workspace": f"workspace-{index}",
                        "jar": "build/libs/example.jar",
                        "checks": (("launch", "Client launches."),),
                    }
                )
            with patch("runtime_evidence_portfolio.CASES", tuple(definitions)):
                payload = build_draft(repo)
                self.assertTrue(all(case["status"] == "runtime_unverified" for case in payload["runtime_evidence_cases"]))
                metrics = summary(payload)
                self.assertEqual(metrics["checked"], 0)
                self.assertEqual(metrics["runtime_unverified"], 3)
                self.assertIsNone(metrics["checked_pass_rate"])
                self.assertEqual(validate(payload, repo), [])

    def test_rejects_status_and_passed_mismatch(self) -> None:
        payload = build_draft(PROJECT_ROOT)
        payload["runtime_evidence_cases"][0]["passed"] = True
        errors = validate(payload, PROJECT_ROOT)
        self.assertTrue(any("conflicts" in error for error in errors))

    def test_require_complete_rejects_unverified_draft(self) -> None:
        payload = build_draft(PROJECT_ROOT)
        errors = validate(payload, PROJECT_ROOT, require_complete=True)
        self.assertEqual(sum("runtime remains unverified" in error for error in errors), 4)

    def test_checked_case_requires_attachment(self) -> None:
        payload = build_draft(PROJECT_ROOT)
        case = payload["runtime_evidence_cases"][0]
        case["status"] = "passed"
        case["passed"] = True
        case["tested_at"] = "2026-07-15T12:00:00+08:00"
        for check in case["checks"]:
            check["status"] = "passed"
        errors = validate(payload, PROJECT_ROOT)
        self.assertTrue(any("requires at least one attachment" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
