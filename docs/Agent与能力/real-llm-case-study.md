# Real LLM Case Study

> 文档定位：这份材料记录 2026-05-28 的真实 LLM smoke/e2e 样本，用来证明项目不是只接了 mock provider，也不是把 fallback 伪装成真实模型成功。

## 结论

本轮真实 LLM 测试可以作为项目证据使用。5 个 `agent generate` case 都通过了严格模式验证：

- planner 使用 `llm`
- provider 使用 `openai-compatible`
- 生成时启用 `--require-llm`
- `fallback_detected = false`
- 输出通过 schema parse / validation
- 生成 workspace 通过 audit，且 `errors_count = 0`、`warnings_count = 0`

这说明真实 provider 至少能完成从自然语言需求到 `ModSpec`，再到确定性 NeoForge workspace 生成与 audit 的闭环。

## 测试样本

| Run | 能力覆盖 | 请求模型 | Provider 回传模型 | Retry | Audit |
| --- | --- | --- | --- | --- | --- |
| `real-llm-ruby-01` | item + block | `deepseek-v4-flash` | `deepseek-v4-flash` | 2 | 通过，65 checks，0 errors，0 warnings |
| `real-llm-sapphire-01` | item + block | `deepseek-v4-pro` | `deepseek-ai/deepseek-v4-flash` | 1 | 通过，65 checks，0 errors，0 warnings |
| `real-llm-cobalt-ore-01` | item + block + ore worldgen | `deepseek-v4-flash` | `deepseek-v4-flash` | 0 | 通过，128 checks，0 errors，0 warnings |
| `real-llm-topaz-charm-01` | right-click behavior item | `deepseek-v4-flash` | `deepseek-v4-flash` | 0 | 通过，74 checks，0 errors，0 warnings |
| `real-llm-mint-food-deepseek-01` | food effect + block | `deepseek-v4-flash` | `deepseek-v4-flash` | 0 | 通过，61 checks，0 errors，0 warnings |

说明：`real-llm-sapphire-01` 中 requested model 和 provider usage model 不一致，原因是 OpenAI-compatible 网关可能做了模型映射或路由。记录时应同时保留“请求模型”和“服务端回传模型”，不要只写其中一个。

`glm-5.1` provider 对照尝试在真实请求阶段返回 HTTP 403 / `error code: 1010`，没有生成 workspace，不计入成功样本。`real-llm-mint-food-deepseek-01` 是同一个 food effect prompt 在 DeepSeek-compatible provider 上的成功样本。

`real-llm-mint-food-deepseek-01` 运行时的 `timeout_seconds=1000000`、`max_retries=20` 更像调试配置。正式展示或再次复现实验时建议改回 `timeout_seconds=60`、`max_retries=2`，让证据链更接近真实工程默认值。

## 复现命令模式

每次真实 LLM 测试前先确保当前 PowerShell 会话已设置项目路径：

```powershell
Set-Location -Path "L:\projects\MinecraftMods\idea-copy-copy"
$env:PYTHONPATH = (Resolve-Path .\src).Path
```

生成命令使用严格模式：

```powershell
py -3.11 -m agent.cli agent generate "<request>" `
  --planner llm `
  --llm-provider openai-compatible `
  --require-llm `
  --workspace-name <run-name> `
  --overwrite `
  --no-build `
  --json
```

生成后运行 audit 和 LLM 工程报告：

```powershell
py -3.11 -m agent.cli audit workspace/<run-name> --json

py -3.11 -m agent.cli llm-engineering-report workspace/<run-name> --run-name <run-name> --json
```

## 证据文件

每个成功 run 都应保留这些文件：

```text
workspace/<run>/.agent/agent-run.json
workspace/<run>/.agent/agent-run.md
workspace/<run>/.agent/prompt-trace.json
workspace/<run>/.agent/llm-stability.json
workspace/<run>/.agent/llm-plan-raw.json
workspace/<run>/.agent/llm-plan-normalized.json
workspace/<run>/.agent/modspec.json
workspace/<run>/.agent/audit-report.json
workspace/llm-engineering-runs/<run>/.agent/llm-engineering-report.json
workspace/llm-engineering-runs/<run>/.agent/llm-engineering-report.md
```

最关键的字段：

- `planner = llm`
- `llm_provider = openai-compatible`
- `provider_config.api_key_present = true`
- `fallback_detected = false`
- `parse_attempts_count >= 1`
- `schema_validation_attempts_count >= 1`
- `json_repair_applied_count = 0` 或记录实际修复次数
- `errors_count = 0`
- `warnings_count = 0`

## 工程意义

这批样本的价值不是证明真实 LLM 永远稳定，而是证明系统有真实模型接入后的工程边界：

- `--require-llm` 能阻止 provider timeout 后 fallback 被误算成真实成功。
- `prompt-trace.json` 和 `llm-stability.json` 能记录 provider、模型、prompt 指纹、retry、usage、schema validation 等证据。
- LLM 只负责规划 `ModSpec`，Java、资源文件、loot table、tag、texture 等由确定性生成器落地。
- audit 负责验证生成产物和 `ModSpec` 的一致性。
- mock provider 仍适合离线回归；真实 provider 适合 smoke/e2e 证明。

## 简历表述

可以压缩成一条简历 bullet：

> 接入 mock 与 OpenAI-compatible 真实 LLM provider 双路径，支持 `--require-llm` 严格模式、prompt trace、retry、schema validation、token usage 与 fallback 识别；使用 DeepSeek-compatible provider 跑通 Ruby/Sapphire/Cobalt/Topaz/Mint 多组真实生成 case，覆盖 item/block、ore worldgen、right-click behavior、food effect，产物通过 65/128/74/61 项 audit 检查且 `fallback_detected=false`。

更工程化一点的版本：

> 设计 NeoForge Mod 生成 Agent 的 LLM 工程链路：真实模型输出受控 `ModSpec`，后续由确定性 generator 生成 Java 和资源文件，并用 audit / LLM engineering report 记录 provider health、prompt 指纹、retry、token usage、schema validation 和 fallback 状态；真实 OpenAI-compatible provider 多组 smoke case 均通过 audit，避免将规则 fallback 误计为 real LLM 成功。

## 面试讲法

可以这样展开：

> 我把 mock 和真实 LLM 分成两条链路。mock 用来做离线、稳定、可复现的回归；真实 LLM 用来证明模型确实能完成自然语言到 ModSpec 的规划。真实模型调用时我会打开 `--require-llm`，所以如果 provider 超时或 schema 不合格，命令会失败，不会 fallback 后假装成功。成功的 case 会留下 prompt trace、LLM stability、token usage、retry、schema validation 和 audit 报告，所以可以复盘到底是模型问题、provider 问题、schema 问题，还是生成器问题。

如果被问到 `pro` 和 `flash` 同时出现：

> 我记录了 requested model 和 provider-reported model。OpenAI-compatible 网关可能会把请求模型路由到另一个实际后端，所以报告里会同时保留本地配置模型和服务端 usage 返回模型。这不是 fallback，fallback 要看 `fallback_detected=false` 和 agent run 的 planner/provider 证据。

## 当前边界

- 这些样本是 smoke/e2e 证据，不代表真实 LLM 成功率是 100%。
- 当前运行使用 `--no-build`，audit 已通过；如果要展示编译闭环，可以挑 1-2 个 case 再跑 build。
- token/cost 取决于 provider 是否返回 usage 和本地是否配置单价；当前 `estimated_cost_usd` 为空。
- 真实 provider 可能 timeout，retry 成功也应如实记录。
