## V4.7 Real LLM Agent Stability

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_llm_stability tests.test_agent_eval tests.test_capabilities tests.test_dashboard -v
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli agent generate "做一个红宝石模组，添加红宝石。" --planner llm --llm-provider openai-compatible --workspace-name v47-real-llm-fallback --overwrite --json
py -3.11 -m agent.cli capabilities --run-name v47-capabilities --json
```

Expected:

- `compileall` succeeds for `src` and `tests`.
- V4.7 focused tests pass for LLM stability, agent fallback, capabilities, and dashboard.
- Full unittest discovery passes.
- `doctor --no-java` reports LLM provider health without exposing secrets.
- Missing real LLM env causes `openai-compatible` to recommend fallback.
- If the machine already has a valid real provider, set `NEOFORGE_AGENT_LLM_BASE_URL=not-a-url` in the current shell to force the unhealthy-provider fallback smoke.
- `agent generate` with unhealthy `openai-compatible` still succeeds through deterministic rules fallback.
- Planner mode is reported as `llm->rules` when fallback is used.
- `.agent/llm-stability.json` records `provider_health`, `schema_retry_attempts`, and `schema_validation_attempts` when LLM artifacts are produced.
- `.agent/rag-context.json` records `quality`.
- Capability Matrix includes `real_llm_health_check`, `llm_schema_retry`, and `llm_rules_fallback`.
- Project version reports `4.7.0`.
