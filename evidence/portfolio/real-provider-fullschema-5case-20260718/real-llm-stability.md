# Real LLM Stability Report

Success: `True`
Run ID: `resume-ab-20260718-fullschema-5case`
Provider: `openai-compatible`
Planner: `llm`
Model: `deepseek-v4-flash-ascend`
Provider config valid: `True`
Build enabled: `False`
Audit enabled: `True`
Fallback probe: `False`
Runtime evidence: `none`
Require runtime: `False`

## Metrics

- total cases: `5`
- strict success: `5`
- real LLM success: `5`
- provider failure: `0`
- schema failure: `0`
- audit failure: `0`
- build failure: `0`
- runtime failure: `0`
- runtime checked: `0`
- runtime success: `0`
- runtime unverified: `5`
- fallback success: `0`
- fallback failure: `0`
- JSON repair applied: `0`
- retry attempts: `0`
- schema retry attempts: `0`
- total tokens: `253819`
- estimated cost USD: `None`
- average latency ms: `46005.0`

## Cases

- `basic_ruby`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\resume-ab-20260718-fullschema-5case\runs\01-basic_ruby-strict`
- `ruby_charm_behavior`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\resume-ab-20260718-fullschema-5case\runs\02-ruby_charm_behavior-strict`
- `speed_crystal_behavior`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\resume-ab-20260718-fullschema-5case\runs\03-speed_crystal_behavior-strict`
- `ruby_apple_effect`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\resume-ab-20260718-fullschema-5case\runs\04-ruby_apple_effect-strict`
- `ruby_sword_ignite`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\resume-ab-20260718-fullschema-5case\runs\05-ruby_sword_ignite-strict`

## Interview Note

Mock runs prove the deterministic engineering path. This report separates strict provider-backed success from provider/schema/audit/build/runtime failures and records fallback success without counting it as real LLM success.
