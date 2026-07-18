# Real LLM Stability Report

Success: `True`
Run ID: `resume-ab-20260718-decomposed-basic-retry`
Provider: `openai-compatible`
Planner: `decomposed`
Model: `deepseek-v4-flash-ascend`
Provider config valid: `True`
Build enabled: `False`
Audit enabled: `True`
Fallback probe: `False`
Runtime evidence: `none`
Require runtime: `False`

## Metrics

- total cases: `1`
- strict success: `1`
- real LLM success: `1`
- provider failure: `0`
- schema failure: `0`
- audit failure: `0`
- build failure: `0`
- runtime failure: `0`
- runtime checked: `0`
- runtime success: `0`
- runtime unverified: `1`
- fallback success: `0`
- fallback failure: `0`
- JSON repair applied: `0`
- retry attempts: `0`
- schema retry attempts: `0`
- total tokens: `3615`
- estimated cost USD: `None`
- average latency ms: `37356.0`

## Cases

- `basic_ruby`: `real_success` strict=true fallback=false failure=none runtime=not_checked
  - workspace: `<repo>\workspace\real-llm-stability-runs\resume-ab-20260718-decomposed-basic-retry\runs\01-basic_ruby-strict`

## Interview Note

Mock runs prove the deterministic engineering path. This report separates strict provider-backed success from provider/schema/audit/build/runtime failures and records fallback success without counting it as real LLM success.
