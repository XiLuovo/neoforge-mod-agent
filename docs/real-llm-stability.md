# Real LLM Stability

> 文档定位：这是真实 LLM 稳定性专项材料，不是主学习入口。需要理解 provider health、fallback、JSON repair 和 schema retry 时再读。

V4.7 把真实 LLM 路径从“能调用”增强为“适合演示”。当前主线已经升级为 `ModSpec-first + Direct Code Lane`：系统会先检查 provider 配置，再让 LLM 输出 ModSpec、patch plan、repair plan 或受审查的 direct-code plan；如果 JSON 解析失败、schema 校验失败、provider 不健康，都会记录证据并安全降级。

## 核心原则

- LLM 默认输出 ModSpec、modify patch 或 repair plan。
- 当 ModSpec 表达不足时，Direct Code Lane 只接受 JSON `write_file` / `replace_text` 补丁计划，不能自由 diff、越界写文件或修改工具项目源码。
- generator、audit、build、repair 仍然是确定性链路。
- 默认测试不依赖真实 LLM API。

## Unified Provider Layer

本轮升级补上统一 LLM provider contract。`mock` 和 `openai-compatible` 现在都通过同一组抽象暴露：

- `LLMProviderMetadata`：provider、model、capabilities、默认 request options、retry policy。
- `LLMModelCapabilities`：是否支持 JSON mode、streaming event、system prompt、tool calling、上下文窗口等。
- `LLMUsage` / `LLMPricing`：记录 input/output/total tokens，并在配置单价后估算 USD 成本。
- `LLMStreamEvent`：统一的 `start -> delta -> complete` 事件流接口。

当前 streaming 是 provider 层事件接口：`mock` 为 synthetic streaming，`openai-compatible` 先用 full-completion fallback 包装成事件流；后续可以替换为原生 SSE，而 planner 不需要改调用契约。

成本估算默认不写死模型价格。可选配置：

```powershell
$env:NEOFORGE_AGENT_LLM_INPUT_COST_PER_1M = "2.5"
$env:NEOFORGE_AGENT_LLM_OUTPUT_COST_PER_1M = "10"
```

这些信息会进入 `.agent/llm-stability.json` 和 `.agent/prompt-trace.json`：

```json
{
  "provider_metadata": {
    "provider": "openai-compatible",
    "capabilities": {
      "supports_json_mode": true,
      "supports_streaming": true
    }
  },
  "completion_usage": {
    "usage": {
      "input_tokens": 1234,
      "output_tokens": 567,
      "total_tokens": 1801
    },
    "estimated_cost_usd": 0.008755
  }
}
```

## Provider Health Check

`check_llm_provider_health("openai-compatible")` 默认只做 config-only 检查，不联网。这样可以在本地、CI、课堂演示环境中稳定运行。

检查内容：

- API key 是否存在。
- model 是否存在。
- base URL 是否存在。
- base URL 是否是 `http://` 或 `https://`。
- timeout / retry 配置是否能解析。

支持的环境变量：

```powershell
$env:NEOFORGE_AGENT_LLM_API_KEY = "..."
$env:NEOFORGE_AGENT_LLM_MODEL = "..."
$env:NEOFORGE_AGENT_LLM_BASE_URL = "https://api.openai.com/v1"
$env:NEOFORGE_AGENT_LLM_TIMEOUT_SECONDS = "60"
$env:NEOFORGE_AGENT_LLM_MAX_RETRIES = "2"
$env:NEOFORGE_AGENT_LLM_SCHEMA_RETRIES = "1"
$env:NEOFORGE_AGENT_LLM_INPUT_COST_PER_1M = "2.5"
$env:NEOFORGE_AGENT_LLM_OUTPUT_COST_PER_1M = "10"
```

兼容 OpenAI 风格变量：

```powershell
$env:OPENAI_API_KEY = "..."
$env:OPENAI_MODEL = "..."
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
$env:OPENAI_SCHEMA_RETRIES = "1"
```

## Fallback

当真实 provider 不健康或 LLM planning 失败时，agent 会降级到 rules planner：

```text
llm  -> llm->rules
auto -> auto->rules
```

这意味着演示时就算没有真实 key，命令也能继续跑通，并且 JSON 输出会明确显示 fallback。

## Schema Retry

V4.7 不只处理坏 JSON，也会处理“JSON 合法但 ModSpec 不合法”的情况。

流程：

```text
LLM response
  -> JSON parse / repair
  -> normalize
  -> validate_mod_spec
  -> validator errors sent back to LLM
  -> retry until schema attempts are exhausted
```

默认 schema retry 为 1 次，也就是最多 2 次 schema validation attempt。

## RAG Quality

planner 会记录 RAG 命中质量：

```json
{
  "hits_count": 3,
  "top_score": 0.91,
  "average_score": 0.74,
  "categories": ["behavior", "worldgen"],
  "capabilities": ["item_behavior", "ore_worldgen"],
  "quality": "strong"
}
```

质量等级包括：

- `strong`
- `moderate`
- `weak`
- `none`

## Artifacts

关键产物：

```text
.agent/llm-stability.json
.agent/rag-context.json
.agent/llm-plan-raw.json
.agent/llm-plan-normalized.json
.agent/llm-plan-warnings.json
.agent/prompt-trace.json
.agent/agent-run.json
```

`llm-stability.json` 适合面试展示真实 LLM 稳定化能力，重点看：

- `provider_health`
- `retry_attempts`
- `schema_retry_attempts`
- `schema_validation_attempts`
- `json_repair_applied`
- `parse_attempts`

## 2026-05-13 Runtime Validation Notes

已完成三组真实 LLM 自然语言 prompt 的游戏内验证：

| Case | Workspace | Status |
| --- | --- | --- |
| Machine | `workspace/real-llm-natural-machine-20260513` | `real LLM + audit + build + 游戏内验证` 通过。 |
| Ruby Basic | `workspace/real-llm-natural-ruby-basic-20260513` | `real LLM + audit + build + 游戏内验证` 通过；验证过程中发现并修复 worldgen runtime 问题。 |
| Progression | `workspace/real-llm-natural-progression-retry-20260513` | `real LLM + audit + build + 游戏内验证` 通过；验证过程中发现并修复 worldgen、dimension type、biome carvers 和 advancement 背景资源问题。 |

本次暴露的稳定性经验：

- `compileJava`、`processResources`、`build` 不会完整验证 Minecraft runtime registry 语义。
- 矿石生成的 `configured_feature` 在进入世界时才会被 Minecraft registry 加载。
- 错误形态：`"target": "minecraft:stone_ore_replaceables"`。
- 正确形态：`"target": {"predicate_type": "minecraft:tag_match", "tag": "minecraft:stone_ore_replaceables"}`。
- MC 26.1 的 dimension type 需要 `has_ender_dragon_fight`，且 `monster_spawn_light_level` 使用顶层 `min_inclusive/max_inclusive`。
- MC 26.1 的 biome `carvers` 需要数组形态，不能是 `{}`。
- 根 advancement 的 `display.background` 需要 GUI sprite id，例如 `minecraft:gui/advancements/backgrounds/stone`，不能使用旧式 `textures/...png` 路径。
- audit 需要覆盖这类 build-valid 但 runtime-invalid 的 worldgen JSON。

## 2026-05-14 Regeneration Check

目标：用修复后的生成器重新生成 3 个 real LLM 固定 case，不手工 patch 生成 workspace。

| Case | Workspace | Real LLM | Audit | Build | Result |
| --- | --- | --- | --- | --- | --- |
| Ruby Basic | `workspace/real-llm-regen2-ruby-basic-20260514` | `planner_mode=llm` | 304 checks, 0 errors | pass | 通过 |
| Machine | `workspace/real-llm-regen2-machine-20260514` | `planner_mode=llm` | 160 checks, 0 errors | pass | 通过 |
| Progression | `workspace/real-llm-regen4-progression-strict-20260514` | `planner_mode=llm` but provider timed out | not reached | not reached | 未通过 real LLM 标准 |

本轮结论：不是 3/3 一次过。Ruby Basic 和 Machine 已经证明自然 prompt -> real LLM ModSpec -> audit/build 可以干净跑通；Progression 在 provider 请求阶段超时，没有得到 real LLM ModSpec。

同时沉淀了 3 个源码级修复：

- LLM model 配置如果读到 `gpt-5.5;gpt-image-2` 这类组合串，会自动取第一个 text model，并在 `.agent/llm-stability.json` 记录 warning。
- `agent generate --require-llm` 会在 LLM 失败时直接失败，不再把 `llm->rules` fallback 误算为 real LLM 成功。
- entity 模板已按 MC 26.1 API 修复：`Identifier`、`clientTrackingRange`、`updateInterval`、`NoopRenderer`、新版 `EventBusSubscriber`；`examples/entity_ruby_goblin.json` 的 audit/build 回归通过。

## Smoke Commands

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli agent generate "做一个红宝石模组，添加红宝石。" --planner llm --llm-provider openai-compatible --workspace-name v47-real-llm-fallback --overwrite --json
py -3.11 -m agent.cli capabilities --run-name v47-capabilities --json
```

如果本机已经配置了真实 provider，但只想验证 fallback 而不发起真实请求，可以在当前 PowerShell 会话里临时设置：

```powershell
$env:NEOFORGE_AGENT_LLM_BASE_URL = "not-a-url"
```

预期结果：

- 没有真实 LLM env 时，provider health 为 fail。
- 输出不会泄露 secret。
- agent 自动 fallback 到 `llm->rules`。
- 生成项目仍然成功。
- capability matrix 报告版本为 `4.7.0`。
