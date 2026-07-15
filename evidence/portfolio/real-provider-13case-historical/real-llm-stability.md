# Real LLM Stability Report

Success: `True`
Run ID: `real-llm-13case-runtime-upgrade`
Provider: `openai-compatible`
Model: `deepseek-v4-flash`
Provider config valid: `True`
Build enabled: `False`
Audit enabled: `True`
Fallback probe: `True`
Runtime evidence: `none`
Require runtime: `False`

## Metrics

- total cases: `13`
- strict success: `12`
- real LLM success: `12`
- provider failure: `0`
- schema failure: `1`
- audit failure: `0`
- build failure: `0`
- runtime failure: `0`
- runtime checked: `0`
- runtime success: `0`
- runtime unverified: `13`
- fallback success: `0`
- fallback failure: `0`
- JSON repair applied: `0`
- retry attempts: `3`
- schema retry attempts: `1`
- total tokens: `2224022`
- estimated cost USD: `None`
- average latency ms: `30168.31`

## Cases

- `basic_ruby`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\01-basic_ruby-strict`
- `ruby_charm_behavior`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\02-ruby_charm_behavior-strict`
- `speed_crystal_behavior`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\03-speed_crystal_behavior-strict`
- `ruby_apple_effect`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\04-ruby_apple_effect-strict`
- `ruby_sword_ignite`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\05-ruby_sword_ignite-strict`
- `ruby_pickaxe_tool`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\06-ruby_pickaxe_tool-strict`
- `ruby_tool_set`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\07-ruby_tool_set-strict`
- `ruby_armor_set`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\08-ruby_armor_set-strict`
- `ruby_block_variants`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\09-ruby_block_variants-strict`
- `ruby_ore_worldgen`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\10-ruby_ore_worldgen-strict`
- `ruby_goblin_entity`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\11-ruby_goblin_entity-strict`
- `ruby_realm_world_structure`: `schema_failure` strict=false fallback=false failure=schema_failure runtime=not_checked
  - fallback workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\12-ruby_realm_world_structure-fallback`
  - error: LLM planner returned invalid JSON.
- `progression_gameplay_loop`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\real-llm-13case-runtime-upgrade\runs\13-progression_gameplay_loop-strict`

## Interview Note

Mock runs prove the deterministic engineering path. This report separates strict provider-backed success from provider/schema/audit/build/runtime failures and records fallback success without counting it as real LLM success.
