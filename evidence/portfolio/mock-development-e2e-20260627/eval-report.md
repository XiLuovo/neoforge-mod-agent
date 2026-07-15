# Eval Report

Success: true
Run ID: `public-polish-decomposed-e2e-20260627`
Planner: `decomposed`
LLM provider: `mock`
Require LLM: false
Build enabled: false
Audit enabled: true

## Metrics

- `total_cases`: 2
- `success_count`: 2
- `success_rate`: 1.0
- `feature_expectation_cases`: 2
- `feature_expectation_success_count`: 2
- `feature_expectation_success_rate`: 1.0
- `expected_features_total`: 6
- `expected_features_matched`: 6
- `expected_feature_match_rate`: 1.0
- `category_expectation_cases`: 2
- `category_expectation_success_count`: 2
- `category_expectation_success_rate`: 1.0
- `expected_categories_total`: 13
- `expected_categories_matched`: 13
- `expected_category_match_rate`: 1.0
- `content_categories_expected`: ['item', 'machine', 'modify', 'ore', 'ore_worldgen', 'progression', 'progression_report', 'recipe', 'sword', 'tool', 'worldgen']
- `content_categories_covered`: ['item', 'machine', 'modify', 'ore', 'ore_worldgen', 'progression', 'progression_report', 'recipe', 'sword', 'tool', 'worldgen']
- `content_categories_missing`: []
- `content_coverage_rate`: 1.0
- `planning_success_count`: 2
- `planning_success_rate`: 1.0
- `audit_attempted_count`: 2
- `audit_success_count`: 2
- `audit_success_rate`: 1.0
- `build_attempted_count`: 0
- `build_success_count`: 0
- `build_success_rate`: 0.0
- `generated_files_total`: 64
- `average_generated_files`: 32.0
- `modify_cases`: 1
- `modify_step_total`: 1
- `multi_step_modify_cases`: 0
- `multi_step_modify_success_count`: 0
- `multi_step_modify_success_rate`: 0.0
- `modify_added_total`: 0
- `modify_updated_total`: 1
- `modify_skipped_total`: 0
- `modify_llm_calls_total`: 2
- `modify_total_tokens`: 2752
- `modify_max_input_tokens_per_call`: 1472
- `modify_average_input_tokens_per_call`: 1182.5
- `decomposed_modify_used_count`: 1
- `decomposed_modify_used_rate`: 1.0
- `modify_context_compaction_ratio`: 0.4363
- `agent_trace_present_count`: 2
- `agent_trace_present_rate`: 1.0
- `agent_decisions_present_count`: 2
- `agent_decisions_present_rate`: 1.0
- `prompt_trace_present_count`: 2
- `prompt_trace_present_rate`: 1.0
- `agent_trace_summary_present_count`: 2
- `agent_trace_summary_present_rate`: 1.0
- `agent_artifacts_complete_count`: 2
- `agent_artifacts_complete_rate`: 1.0
- `rag_hit_cases`: 2
- `rag_hit_rate`: 1.0
- `rag_hits_total`: 8
- `average_rag_hits`: 4.0
- `rag_categories_covered`: ['assets', 'content', 'data', 'worldgen']
- `rag_capabilities_covered`: ['overworld_ore', 'procedural_textures', 'recipes_loot_tags', 'tools_armor', 'world_structure_dsl']
- `repeat_modify_cases`: 1
- `repeat_modify_success_count`: 1
- `repeat_modify_success_rate`: 1.0

## Cases

- `develop_progression_loop` `generate`: pass
  - workspace: `<repo>\workspace\eval-runs\public-polish-decomposed-e2e-20260627\01-develop_progression_loop`
  - expected features: matched=5/5
  - expected categories: matched=9/9
  - agent artifacts: run=true, decisions=true, prompt_trace=true, trace_summary=true
  - rag: hits=4, categories=content, data, worldgen, capabilities=overworld_ore, recipes_loot_tags, tools_armor, world_structure_dsl
- `modify_add_worldgen_repeat` `modify`: pass
  - workspace: `<repo>\workspace\eval-runs\public-polish-decomposed-e2e-20260627\02-modify_add_worldgen_repeat-base`
  - merge: added=0, updated=1, skipped=0
  - modify steps: 1
    - `modify_add_worldgen_repeat:modify`: pass, added=0, updated=1, skipped=0, decomposed=true
  - expected features: matched=1/1
  - expected categories: matched=4/4
  - agent artifacts: run=true, decisions=true, prompt_trace=true, trace_summary=true
  - rag: hits=4, categories=assets, content, worldgen, capabilities=overworld_ore, procedural_textures, tools_armor, world_structure_dsl
  - repeat modify: success=true, skipped=1
