from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from build_portfolio_evidence import (
    build_portfolio,
    find_public_safety_violations,
    sanitize_json,
    sanitize_text,
    verify_portfolio,
)


class PortfolioEvidenceTests(unittest.TestCase):
    def test_sanitize_text_removes_repo_path_and_common_secrets(self) -> None:
        text = f'path={PROJECT_ROOT} api_key=secret-value Authorization:Bearer abcdef sk-example123456789'
        sanitized = sanitize_text(text, PROJECT_ROOT)
        self.assertNotIn(str(PROJECT_ROOT), sanitized)
        self.assertNotIn("secret-value", sanitized)
        self.assertNotIn("abcdef", sanitized)
        self.assertNotIn("sk-example123456789", sanitized)
        self.assertIn("<repo>", sanitized)
        self.assertIn("<redacted>", sanitized)

    def test_build_portfolio_records_missing_sources_without_inventing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            output = repo / "evidence" / "portfolio"
            manifest = build_portfolio(repo, output)
            self.assertTrue((output / "manifest.json").is_file())
            loaded = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertTrue(all(entry["status"] == "incomplete" for entry in loaded["entries"]))
            self.assertTrue(all(entry["missing_files"] for entry in loaded["entries"]))

    def test_sanitize_json_redacts_secret_fields_but_keeps_presence_flags(self) -> None:
        sanitized = sanitize_json(
            {
                "api_key": ".env.local:KEY",
                "api_key_present": True,
                "model_source": ".env.local:MODEL",
                "nested": {"access_token": "abc"},
            },
            PROJECT_ROOT,
        )
        self.assertEqual(sanitized["api_key"], "<redacted>")
        self.assertTrue(sanitized["api_key_present"])
        self.assertEqual(sanitized["model_source"], "<local-config-source-redacted>")
        self.assertEqual(sanitized["nested"]["access_token"], "<redacted>")

    def test_public_safety_scan_rejects_bearer_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "report.md").write_text("Authorization: Bearer abcdefghijklmnop", encoding="utf-8")
            self.assertEqual(find_public_safety_violations(root), ["report.md: bearer token"])

    def test_verify_portfolio_detects_tampered_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            source = repo / "workspace" / "eval-runs" / "public-polish-decomposed-e2e-20260627" / ".agent"
            source.mkdir(parents=True)
            (source / "eval-report.json").write_text("{}", encoding="utf-8")
            (source / "eval-report.md").write_text("ok", encoding="utf-8")
            output = repo / "evidence" / "portfolio"
            build_portfolio(repo, output)
            report = output / "mock-development-e2e-20260627" / "eval-report.md"
            report.write_text("tampered", encoding="utf-8")
            errors = verify_portfolio(output)
            self.assertTrue(any("mock-development-e2e-20260627" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
