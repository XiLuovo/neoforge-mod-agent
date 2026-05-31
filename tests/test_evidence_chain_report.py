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

from neoforge_agent import AppConfig, EvidenceChainReportRunner


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class EvidenceChainReportTests(unittest.TestCase):
    def test_evidence_chain_report_aggregates_all_layers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = EvidenceChainReportRunner(config).run(
                run_name="unit-evidence-chain",
                eval_limit=1,
                repair_limit=1,
            )

            self.assertTrue(result.success)
            self.assertTrue(result.evidence_chain_report_json_path.exists())
            self.assertTrue(result.evidence_chain_report_md_path.exists())

            layer_ids = {layer.identifier for layer in result.layers}
            self.assertEqual(layer_ids, {"stable", "behavior", "patch_agent"})
            self.assertEqual(result.metrics["layers_passed"], 3)
            self.assertEqual(result.metrics["acceptance_success_rate"], 1.0)
            self.assertEqual(result.metrics["recovery_rate"], 1.0)
            self.assertEqual(result.metrics["runtime_validation_pass_rate"], 1.0)
            self.assertGreater(result.metrics["generated_files_total"], 0)
            self.assertEqual(result.metrics["failure_samples_total"], 3)

            for layer in result.layers:
                self.assertTrue(layer.acceptance_samples)
                self.assertTrue(layer.failure_samples)
                self.assertTrue(layer.recovery_samples)
                self.assertGreaterEqual(layer.generated_files_count, 0)
                self.assertEqual(layer.success_rate, 1.0)
                self.assertEqual(layer.recovery_rate, 1.0)

            patch_layer = next(layer for layer in result.layers if layer.identifier == "patch_agent")
            self.assertTrue(any(sample.identifier == "patch_repair_ore_initial_failure" for sample in patch_layer.failure_samples))
            self.assertTrue(any(sample.runtime_validation.get("repair_loop") == "recovered" for sample in patch_layer.recovery_samples))

            report = result.evidence_chain_report_md_path.read_text(encoding="utf-8")
            self.assertIn("Stable ModSpec Layer", report)
            self.assertIn("Behavior DSL Layer", report)
            self.assertIn("Controlled Patch Agent Layer", report)


if __name__ == "__main__":
    unittest.main()
