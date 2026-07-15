# Showcase Report

Success: true
Run ID: `public-build-smoke-clean`
Showcase dir: `<repo>\workspace\showcase-runs\public-build-smoke-clean`
Passed: 5
Failed: 0
Skipped: 1

## Story

This showcase run demonstrates the current agent pipeline:

- environment doctor preflight
- mock LLM multi-role agent generation
- modify existing workspace with worldgen update
- benchmark eval smoke
- development e2e eval for progression generation and repeat-safe modification
- optional quality gate

## Steps

- `doctor` `pass`: Environment doctor preflight completed.
  - doctor_report_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\doctor-runs\public-build-smoke-clean-doctor\.agent\doctor-report.json`
  - doctor_report_md: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\doctor-runs\public-build-smoke-clean-doctor\.agent\doctor-report.md`
  - metrics: `{'passed': 22, 'warnings': 0, 'failed': 0, 'skipped': 1}`
- `agent_generate` `pass`: Generated a behavior item workspace through the multi-role agent workflow.
  - workspace: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-generate`
  - agent_run_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-generate\.agent\agent-run.json`
  - agent_run_md: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-generate\.agent\agent-run.md`
  - agent_trace_summary_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-generate\.agent\agent-trace-summary.json`
  - agent_trace_summary_md: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-generate\.agent\agent-trace-summary.md`
  - prompt_trace_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-generate\.agent\prompt-trace.json`
  - metrics: `{'steps': 5, 'decisions': 5, 'prompt_traces': 1, 'audit_success': True, 'build_attempted': True}`
- `agent_modify` `pass`: Modified an existing workspace to add ore worldgen through the agent workflow.
  - workspace: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-modify-base`
  - agent_run_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-modify-base\.agent\agent-run.json`
  - agent_run_md: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-modify-base\.agent\agent-run.md`
  - agent_trace_summary_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-modify-base\.agent\agent-trace-summary.json`
  - agent_trace_summary_md: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-modify-base\.agent\agent-trace-summary.md`
  - prompt_trace_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-modify-base\.agent\prompt-trace.json`
  - patch_agent_plan_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-modify-base\.agent\patch-agent-plan.json`
  - patch_agent_report_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-modify-base\.agent\patch-agent-report.json`
  - patch_agent_rollback_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\showcase-agent-modify-base\.agent\patch-agent-rollback-report.json`
  - metrics: `{'added': 0, 'updated': 1, 'skipped': 0, 'decisions': 6, 'prompt_traces': 1, 'audit_success': True, 'build_attempted': True, 'patch_agent_status': 'pass'}`
- `eval_smoke` `pass`: Ran the offline agent benchmark smoke suite.
  - eval_report_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\eval-runs\public-build-smoke-clean-eval\.agent\eval-report.json`
  - eval_report_md: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\eval-runs\public-build-smoke-clean-eval\.agent\eval-report.md`
  - metrics: `{'total_cases': 2, 'success_count': 2, 'success_rate': 1.0, 'feature_expectation_cases': 2, 'feature_expectation_success_count': 2, 'feature_expectation_success_rate': 1.0, 'expected_features_total': 2, 'expected_features_matched': 2, 'expected_feature_match_rate': 1.0, 'category_expectation_cases': 2, 'category_expectation_success_count': 2, 'category_expectation_success_rate': 1.0, 'expected_categories_total': 4, 'expected_categories_matched': 4, 'expected_category_match_rate': 1.0, 'content_categories_expected': ['behavior', 'item', 'right_click_heal'], 'content_categories_covered': ['behavior', 'item', 'right_click_heal'], 'content_categories_missing': [], 'content_coverage_rate': 1.0, 'planning_success_count': 2, 'planning_success_rate': 1.0, 'audit_attempted_count': 2, 'audit_success_count': 2, 'audit_success_rate': 1.0, 'build_attempted_count': 0, 'build_success_count': 0, 'build_success_rate': 0.0, 'generated_files_total': 25, 'average_generated_files': 12.5, 'modify_cases': 0, 'modify_step_total': 0, 'multi_step_modify_cases': 0, 'multi_step_modify_success_count': 0, 'multi_step_modify_success_rate': 0.0, 'modify_added_total': 0, 'modify_updated_total': 0, 'modify_skipped_total': 0, 'modify_llm_calls_total': 0, 'modify_total_tokens': 0, 'modify_max_input_tokens_per_call': 0, 'modify_average_input_tokens_per_call': 0, 'decomposed_modify_used_count': 0, 'decomposed_modify_used_rate': 0.0, 'modify_context_compaction_ratio': None, 'agent_trace_present_count': 2, 'agent_trace_present_rate': 1.0, 'agent_decisions_present_count': 2, 'agent_decisions_present_rate': 1.0, 'prompt_trace_present_count': 2, 'prompt_trace_present_rate': 1.0, 'agent_trace_summary_present_count': 2, 'agent_trace_summary_present_rate': 1.0, 'agent_artifacts_complete_count': 2, 'agent_artifacts_complete_rate': 1.0, 'rag_hit_cases': 2, 'rag_hit_rate': 1.0, 'rag_hits_total': 6, 'average_rag_hits': 3.0, 'rag_categories_covered': ['behavior', 'content', 'java'], 'rag_capabilities_covered': ['block_variants', 'registration', 'right_click_behavior', 'shared_behavior_report', 'sword_ignite', 'tools_armor'], 'repeat_modify_cases': 0, 'repeat_modify_success_count': 0, 'repeat_modify_success_rate': 0.0}`
- `development_e2e` `pass`: Ran the development e2e eval suite for progression generation and repeat-safe worldgen modification.
  - cases: `<repo>\examples\agent_development_e2e.json`
  - eval_report_json: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\eval-runs\public-build-smoke-clean-development-e2e\.agent\eval-report.json`
  - eval_report_md: `<repo>\workspace\showcase-runs\public-build-smoke-clean\workspaces\eval-runs\public-build-smoke-clean-development-e2e\.agent\eval-report.md`
  - metrics: `{'total_cases': 2, 'success_count': 2, 'success_rate': 1.0, 'feature_expectation_cases': 2, 'feature_expectation_success_count': 2, 'feature_expectation_success_rate': 1.0, 'expected_features_total': 6, 'expected_features_matched': 6, 'expected_feature_match_rate': 1.0, 'category_expectation_cases': 2, 'category_expectation_success_count': 2, 'category_expectation_success_rate': 1.0, 'expected_categories_total': 13, 'expected_categories_matched': 13, 'expected_category_match_rate': 1.0, 'content_categories_expected': ['item', 'machine', 'modify', 'ore', 'ore_worldgen', 'progression', 'progression_report', 'recipe', 'sword', 'tool', 'worldgen'], 'content_categories_covered': ['item', 'machine', 'modify', 'ore', 'ore_worldgen', 'progression', 'progression_report', 'recipe', 'sword', 'tool', 'worldgen'], 'content_categories_missing': [], 'content_coverage_rate': 1.0, 'planning_success_count': 2, 'planning_success_rate': 1.0, 'audit_attempted_count': 2, 'audit_success_count': 2, 'audit_success_rate': 1.0, 'build_attempted_count': 2, 'build_success_count': 2, 'build_success_rate': 1.0, 'generated_files_total': 81, 'average_generated_files': 40.5, 'modify_cases': 1, 'modify_step_total': 1, 'multi_step_modify_cases': 0, 'multi_step_modify_success_count': 0, 'multi_step_modify_success_rate': 0.0, 'modify_added_total': 0, 'modify_updated_total': 1, 'modify_skipped_total': 0, 'modify_llm_calls_total': 1, 'modify_total_tokens': 81180, 'modify_max_input_tokens_per_call': 81023, 'modify_average_input_tokens_per_call': 81023.0, 'decomposed_modify_used_count': 0, 'decomposed_modify_used_rate': 0.0, 'modify_context_compaction_ratio': None, 'agent_trace_present_count': 2, 'agent_trace_present_rate': 1.0, 'agent_decisions_present_count': 2, 'agent_decisions_present_rate': 1.0, 'prompt_trace_present_count': 2, 'prompt_trace_present_rate': 1.0, 'agent_trace_summary_present_count': 2, 'agent_trace_summary_present_rate': 1.0, 'agent_artifacts_complete_count': 2, 'agent_artifacts_complete_rate': 1.0, 'rag_hit_cases': 2, 'rag_hit_rate': 1.0, 'rag_hits_total': 8, 'average_rag_hits': 4.0, 'rag_categories_covered': ['behavior', 'content', 'data', 'worldgen'], 'rag_capabilities_covered': ['food_effects', 'overworld_ore', 'recipes_loot_tags', 'sword_ignite', 'tools_armor', 'world_structure_dsl'], 'repeat_modify_cases': 1, 'repeat_modify_success_count': 1, 'repeat_modify_success_rate': 1.0, 'eval_success': True, 'audit_success': True, 'build_attempted': True, 'build_success': True, 'repeat_modify_success': True}`
- `quality_gate` `skip`: Quality gate was not requested. Pass --quality-gate to include it.
