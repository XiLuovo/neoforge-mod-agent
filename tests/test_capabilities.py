from __future__ import annotations

import tempfile
import tomllib
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

from neoforge_agent import AppConfig, CapabilityCatalog


def test_config(workspace_root: Path) -> AppConfig:
    base = AppConfig.default()
    return replace(base, workspace_root=workspace_root)


class CapabilityCatalogTests(unittest.TestCase):
    def test_capability_catalog_writes_reports_and_includes_core_sections(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neoforge-agent-", dir=TMP_ROOT) as tmp:
            config = test_config(Path(tmp))

            result = CapabilityCatalog(config).build(run_name="unit-capabilities")

            self.assertTrue(result.success)
            project_metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
            self.assertEqual(result.version, project_metadata["project"]["version"])
            self.assertTrue(result.capability_report_json_path.exists())
            self.assertTrue(result.capability_report_md_path.exists())

            section_ids = {section.identifier for section in result.sections}
            self.assertIn("workflows", section_ids)
            self.assertIn("domain_specs", section_ids)
            self.assertIn("content", section_ids)
            self.assertIn("reliability", section_ids)

            capability_ids = {
                capability.identifier
                for section in result.sections
                for capability in section.capabilities
            }
            self.assertIn("generate", capability_ids)
            self.assertIn("domain_spec_registry", capability_ids)
            self.assertIn("neoforge_domain_spec", capability_ids)
            self.assertIn("planned_spring_api_spec", capability_ids)
            self.assertIn("planned_unity_component_spec", capability_ids)
            self.assertIn("quality_gate", capability_ids)
            self.assertIn("showcase", capability_ids)
            self.assertIn("portfolio_demo", capability_ids)
            self.assertIn("portfolio_release_package", capability_ids)
            self.assertIn("capabilities", capability_ids)
            self.assertIn("tools_manifest", capability_ids)
            self.assertIn("web_dashboard", capability_ids)
            self.assertIn("repair_loop", capability_ids)
            self.assertIn("agent_prompt_trace", capability_ids)
            self.assertIn("agent_decision_log", capability_ids)
            self.assertIn("multi_agent_trace", capability_ids)
            self.assertIn("agent_replay", capability_ids)
            self.assertIn("multi_agent_dashboard", capability_ids)
            self.assertIn("repair_plan", capability_ids)
            self.assertIn("web_demo_live_logs", capability_ids)
            self.assertIn("web_demo_knowledge_browser", capability_ids)
            self.assertIn("web_demo_self_healing", capability_ids)
            self.assertIn("web_demo_repair_rag", capability_ids)
            self.assertIn("rag_hit_dashboard", capability_ids)
            self.assertIn("dashboard_repair_summary", capability_ids)
            self.assertIn("dashboard_repair_rag", capability_ids)
            self.assertIn("knowledge_categories", capability_ids)
            self.assertIn("rag_used_knowledge", capability_ids)
            self.assertIn("rag_eval_metrics", capability_ids)
            self.assertIn("eval_coverage_metrics", capability_ids)
            self.assertIn("eval_compare", capability_ids)
            self.assertIn("llm_eval_report", capability_ids)
            self.assertIn("llm_engineering_report", capability_ids)
            self.assertIn("real_llm_eval_compare", capability_ids)
            self.assertIn("golden_tests", capability_ids)
            self.assertIn("failure_lab", capability_ids)
            self.assertIn("repair_eval", capability_ids)
            self.assertIn("evidence_chain_report", capability_ids)
            self.assertIn("explainable_rag_citations", capability_ids)
            self.assertIn("dashboard_rag_citation_chain", capability_ids)
            self.assertIn("real_llm_health_check", capability_ids)
            self.assertIn("llm_schema_retry", capability_ids)
            self.assertIn("llm_rules_fallback", capability_ids)
            self.assertIn("golden_snapshot_checks", capability_ids)
            self.assertIn("content_coverage_dashboard", capability_ids)
            self.assertIn("procedural_textures", capability_ids)
            self.assertIn("resource_quality_profiles", capability_ids)
            self.assertIn("texture_atlas_preview", capability_ids)
            self.assertIn("model_variant_report", capability_ids)
            self.assertIn("dashboard_resource_preview", capability_ids)
            self.assertIn("texture_audit", capability_ids)
            self.assertIn("resource_quality_audit", capability_ids)
            self.assertIn("knowledge_query", capability_ids)
            self.assertIn("rag_planner_context", capability_ids)
            self.assertIn("tool", capability_ids)
            self.assertIn("armor", capability_ids)
            self.assertIn("equipment_sets", capability_ids)
            self.assertIn("equipment_recipes", capability_ids)
            self.assertIn("progression_dsl", capability_ids)
            self.assertIn("progression_report", capability_ids)
            self.assertIn("balance_planner", capability_ids)
            self.assertIn("economy_report", capability_ids)
            self.assertIn("quest_dsl", capability_ids)
            self.assertIn("advancement_generation", capability_ids)
            self.assertIn("guidebook_generation", capability_ids)
            self.assertIn("block_variants", capability_ids)
            self.assertIn("interactive_blocks", capability_ids)
            self.assertIn("machine", capability_ids)
            self.assertIn("block_entity_gui", capability_ids)
            self.assertIn("machine_progress_energy", capability_ids)
            self.assertIn("entity", capability_ids)
            self.assertIn("entity_attributes", capability_ids)
            self.assertIn("entity_loot_spawn", capability_ids)
            self.assertIn("entity_ai_goals", capability_ids)
            self.assertIn("dimension", capability_ids)
            self.assertIn("biome", capability_ids)
            self.assertIn("world_feature", capability_ids)
            self.assertIn("structure", capability_ids)
            self.assertIn("structure_preview", capability_ids)
            self.assertIn("structure_set", capability_ids)
            self.assertIn("loot_pool", capability_ids)
            self.assertIn("world_structure_dsl", capability_ids)
            self.assertIn("controlled_java_extension", capability_ids)
            self.assertIn("direct_code_lane", capability_ids)
            self.assertIn("free_code_lab", capability_ids)
            self.assertIn("capability_harvest_report", capability_ids)
            self.assertIn("capability_harvest_loop", capability_ids)
            self.assertIn("machine_gui_harvest_target", capability_ids)
            self.assertIn("direct_code_patch_plan", capability_ids)
            self.assertIn("direct_code_review_gate", capability_ids)
            self.assertIn("direct_code_build_audit_gate", capability_ids)
            self.assertIn("free_code_lab_safety_gate", capability_ids)
            self.assertIn("patch_agent", capability_ids)
            self.assertIn("shared_behavior_report", capability_ids)
            self.assertIn("behavior_combo_state_resource_chain", capability_ids)
            self.assertIn("behavior_report_only_hosts", capability_ids)
            self.assertIn("java_extension_sandbox", capability_ids)
            self.assertIn("java_extension_audit", capability_ids)
            self.assertIn("java_extension_build_gate", capability_ids)
            self.assertIn("java_extension_diff_report", capability_ids)
            self.assertIn("java_extension_rollback_report", capability_ids)
            self.assertIn("llm_provider_config_check", capability_ids)
            self.assertIn("llm_json_repair", capability_ids)
            self.assertIn("llm_retry", capability_ids)
            self.assertIn("llm_eval_preflight", capability_ids)
            self.assertIn("repair_agent_execute", capability_ids)
            self.assertIn("repair_rag", capability_ids)
            self.assertIn("replay_repair_rag", capability_ids)
            self.assertIn("safe_repair_execution", capability_ids)
            self.assertIn("self_healing_demo", capability_ids)


if __name__ == "__main__":
    unittest.main()
