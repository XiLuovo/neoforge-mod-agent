from __future__ import annotations

import json
import os
import subprocess
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

from neoforge_agent import AppConfig, DomainSpecRegistry, ModSpec


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class DomainSpecTests(unittest.TestCase):
    def test_default_registry_exposes_stable_neoforge_and_planned_future_domains(self) -> None:
        registry = DomainSpecRegistry.default()
        payload = registry.to_dict()

        domain_ids = {domain["domain_id"] for domain in payload["domains"]}
        self.assertIn("minecraft.neoforge", domain_ids)
        self.assertIn("spring.api", domain_ids)
        self.assertIn("unity.component", domain_ids)
        self.assertEqual(payload["stable_count"], 1)
        self.assertEqual(payload["planned_count"], 2)

    def test_modspec_is_domain_spec_and_round_trips_through_registry(self) -> None:
        registry = DomainSpecRegistry.default()
        spec = ModSpec(
            raw_request="Create a ruby item.",
            mod_id="ruby_mod",
            display_name="Ruby Mod",
            package_name="com.generated.ruby_mod",
        )

        self.assertEqual(spec.domain_id, "minecraft.neoforge")
        self.assertEqual(spec.domain_spec_type, "ModSpec")

        dumped = registry.get("minecraft.neoforge").dump(spec)
        self.assertEqual(dumped["domain"], "minecraft.neoforge")
        self.assertEqual(dumped["domain_spec_type"], "ModSpec")

        loaded = registry.load(dumped)
        self.assertIsInstance(loaded, ModSpec)
        self.assertEqual(loaded.mod_id, "ruby_mod")
        self.assertEqual(loaded.domain_id, "minecraft.neoforge")

        legacy_alias_loaded = registry.load({**dumped, "domain": "neoforge"})
        self.assertIsInstance(legacy_alias_loaded, ModSpec)
        self.assertEqual(legacy_alias_loaded.mod_id, "ruby_mod")

    def test_neoforge_plugin_validates_existing_modspec_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            registry = DomainSpecRegistry.default()
            plugin = registry.get("minecraft.neoforge")
            spec = plugin.load(
                {
                    "domain": "minecraft.neoforge",
                    "domain_spec_type": "ModSpec",
                    "raw_request": "Create a ruby item.",
                    "mod_id": "ruby_mod",
                    "mod_name": "Ruby Mod",
                    "package": "com.generated.ruby_mod",
                    "features": [
                        {
                            "type": "item",
                            "id": "ruby",
                            "display_name_en_us": "Ruby",
                        }
                    ],
                }
            )

            report = plugin.validate(spec, test_config(Path(tmp)))
            description = plugin.describe(spec)

            self.assertTrue(report.is_valid)
            self.assertEqual(description["domain_id"], "minecraft.neoforge")
            self.assertEqual(description["feature_count"], 1)
            self.assertEqual(description["feature_counts"]["item"], 1)

    def test_planned_domain_cannot_load_until_plugin_is_implemented(self) -> None:
        registry = DomainSpecRegistry.default()
        plugin = registry.get("spring.api")

        self.assertTrue(plugin.can_load({"domain": "spring.api", "domain_spec_type": "SpringApiSpec"}))
        with self.assertRaises(NotImplementedError):
            plugin.load({"domain": "spring.api", "domain_spec_type": "SpringApiSpec"})

    def test_domains_cli_lists_registry_as_json(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent.cli",
                "domains",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONPATH": str(SRC_ROOT)},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(completed.stdout)
        domain_ids = {domain["domain_id"] for domain in payload["domains"]}

        self.assertTrue(payload["success"])
        self.assertIn("minecraft.neoforge", domain_ids)
        self.assertIn("spring.api", domain_ids)
        self.assertIn("unity.component", domain_ids)


if __name__ == "__main__":
    unittest.main()
