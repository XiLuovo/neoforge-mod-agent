from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from neoforge_agent import load_manual_runtime_evidence_cases, summarize_manual_runtime_evidence
from neoforge_agent.manual_runtime_evidence import (
    MANUAL_RUNTIME_EVIDENCE_KIND,
    MANUAL_RUNTIME_EVIDENCE_SCHEMA_VERSION,
)


class ManualRuntimeEvidenceTests(unittest.TestCase):
    def test_loads_json_schema_and_summarizes_manual_runtime_cases(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-evidence-", dir=TMP_ROOT) as tmp:
            evidence_path = Path(tmp) / "runtime-evidence.json"
            evidence_path.write_text(
                json.dumps(
                    {
                        "runtime_evidence_cases": [
                            {
                                "id": "basic_ruby",
                                "workspace": "workspace/basic-ruby",
                                "status": "passed",
                                "passed": True,
                                "notes": "Manual client launch and creative inventory smoke passed.",
                            },
                            {
                                "id": "blocked_case",
                                "workspace": "workspace/blocked",
                                "status": "blocked",
                                "notes": "Local launcher missing.",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            cases = load_manual_runtime_evidence_cases(evidence_path)
            summary = summarize_manual_runtime_evidence(cases).to_dict()

            self.assertEqual(len(cases), 2)
            self.assertEqual(cases[0].schema_version, MANUAL_RUNTIME_EVIDENCE_SCHEMA_VERSION)
            self.assertEqual(cases[0].evidence_kind, MANUAL_RUNTIME_EVIDENCE_KIND)
            self.assertTrue(cases[0].passed)
            self.assertFalse(cases[1].passed)
            self.assertEqual(summary["runtime_cases_total"], 2)
            self.assertEqual(summary["runtime_passed_count"], 1)
            self.assertEqual(summary["runtime_blocked_count"], 1)
            self.assertEqual(summary["runtime_pass_rate"], 0.5)

    def test_loads_markdown_table_with_optional_heading(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-evidence-", dir=TMP_ROOT) as tmp:
            evidence_path = Path(tmp) / "runtime-evidence.md"
            evidence_path.write_text(
                "\n".join(
                    [
                        "# Runtime Notes",
                        "",
                        "## 2026-05-13 Real LLM Natural Prompt Runtime Validation",
                        "",
                        "| Case | Workspace | Result | Manual runtime checks |",
                        "| --- | --- | --- | --- |",
                        "| Machine | `workspace/machine` | passed | Client loaded and GUI opened. |",
                        "| Ruby Basic | `workspace/ruby` | failed | Startup crash reproduced. |",
                    ]
                ),
                encoding="utf-8",
            )

            cases = load_manual_runtime_evidence_cases(
                evidence_path,
                markdown_heading="## 2026-05-13 Real LLM Natural Prompt Runtime Validation",
            )
            summary = summarize_manual_runtime_evidence(cases).to_dict()

            self.assertEqual([case.identifier for case in cases], ["Machine", "Ruby Basic"])
            self.assertTrue(cases[0].passed)
            self.assertFalse(cases[1].passed)
            self.assertEqual(summary["runtime_cases_total"], 2)
            self.assertEqual(summary["runtime_failed_count"], 1)
            self.assertEqual(summary["runtime_pass_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
