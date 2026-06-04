## V4.7 真实 LLM Agent 稳定化

目标：让真实 OpenAI-compatible LLM 更适合现场演示。即使 provider 没配置、返回坏 JSON、返回不合法 ModSpec，系统也能留下诊断证据，并安全降级到确定性的 rules planner。

完成内容：
- 新增 `LLMProviderHealth` 和 `check_llm_provider_health`，默认做不联网的 config-only provider health check。
- `doctor` 会报告 LLM provider 健康状态，并给出 fallback 推荐。
- `plan_with_llm` 和 `plan_modification_with_llm` 支持 validator schema retry，不只重试 JSON 解析失败，也会重试不合法 ModSpec。
- 新增 `NEOFORGE_AGENT_LLM_SCHEMA_RETRIES` / `OPENAI_SCHEMA_RETRIES`，默认 schema retry 为 1 次。
- `agent generate`、`modify`、普通 `generate` 的 LLM 路径都支持失败降级，planner mode 会显示为 `llm->rules` 或 `auto->rules`。
- RAG artifact 新增 `rag_quality`，记录 hit 数量、top score、平均分、分类覆盖和质量等级。
- prompt trace 和 agent trace 会带上 provider health、schema retry attempts、schema validation attempts、RAG quality。
- `.agent/llm-stability.json` 记录 provider health、JSON repair、parse attempts 和 schema validation attempts。
- Capability Matrix 新增：
  - `real_llm_health_check`
  - `llm_schema_retry`
  - `llm_rules_fallback`
- package metadata 更新到 `4.7.0`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_llm_stability tests.test_agent_eval tests.test_capabilities tests.test_dashboard -v
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli agent generate "做一个红宝石模组，添加红宝石。" --planner llm --llm-provider openai-compatible --workspace-name v47-real-llm-fallback --overwrite --json
py -3.11 -m agent.cli capabilities --run-name v47-capabilities --json
```

边界：
- 默认 health check 不联网，只检查配置完整性，避免测试依赖真实 API。
- LLM 仍然不能直接写 Java、JSON、PNG 或 Gradle。
- 降级到 rules 后，项目仍通过 deterministic generator、audit、build、repair 链路。
