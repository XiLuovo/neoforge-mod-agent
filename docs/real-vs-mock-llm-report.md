# 真实 LLM vs Mock LLM 对比报告

> 文档定位：这是 real vs mock LLM 对比专项材料，不是主学习入口。需要区分离线稳定回归和真实模型能力验证时再读。

本报告用于回答一个面试里很容易被追问的问题：这个项目里的 LLM 到底只是演示包装，还是确实跑过真实模型？

结论先说清楚：`mock` 是稳定、离线、可重复的回归基线；真实 `openai-compatible` LLM 已经跑通过多组自然语言 prompt，但稳定性不如 mock，复杂玩法线会受 provider 超时和 schema 覆盖影响。因此本项目的工程取舍是：现场演示默认用 mock，真实 LLM 作为可验证增强路径，并用 `--require-llm`、`llm-stability.json`、audit、build 和手工 runtime 记录证明它不是静态包装。

## 对比口径

| 维度 | Mock LLM | 真实 LLM |
| --- | --- | --- |
| Provider | `mock` | `openai-compatible` |
| 是否联网 | 否 | 是，依赖本地或远程 OpenAI-compatible endpoint |
| 主要用途 | 稳定回归、现场演示、CI 友好 | 验证真实模型能否生成合格 `ModSpec` 或受审查的 direct-code plan |
| 输出边界 | 模拟 LLM 输出 `ModSpec` / direct-code plan 样例 | 真实模型默认输出 `ModSpec`；Direct Code Lane 只接受结构化 workspace 补丁 |
| 风险 | 覆盖范围受 mock 规则影响 | 可能超时、返回不合规 JSON、触发 schema retry 或 fallback |
| 验收方式 | eval + audit 指标 | `llm-stability.json` + audit + Gradle build + runtime 记录 |

## 指标摘要

| 指标 | Mock 基线 | 真实 LLM 证据 |
| --- | --- | --- |
| 默认 eval case | 12/12 成功 | 不使用默认 eval 矩阵；采用 3 个自然语言代表 case |
| Planning 成功率 | 12/12，100% | 2026-05-13 自然 prompt 3/3 得到真实 LLM `ModSpec`；2026-05-14 严格重生成 2/3 成功、1/3 provider 超时 |
| Audit 通过 | 12/12，100% | 2026-05-13 三个 case 最终 audit 通过；2026-05-14 两个 strict real LLM case audit 通过 |
| Gradle build | 默认 eval 未开启 build | 2026-05-13 三个 case build 通过；2026-05-14 两个 strict real LLM case build 通过 |
| 生成文件数 | 合计 258 个，平均 21.5 个 / case | Ruby Basic 66 个，Machine 42 个，Progression retry 117 个 |
| RAG 命中 | 12/12 case 命中，合计 46 条 | 真实 case 均保留 `.agent/rag-context.json` 和 `.agent/llm-used-knowledge.json` |
| 失败暴露 | 主要用于稳定回归 | Progression strict 在 provider 请求阶段超时；runtime 验证暴露 worldgen / dimension / biome / advancement schema 风险 |

## Mock 基线

复现命令：

```powershell
py -3.11 -m agent.cli eval --run-name v80-texture-fix-metrics-eval --planner llm --llm-provider mock --no-build --audit --json
```

证据文件：

```text
workspace/eval-runs/v80-texture-fix-metrics-eval/.agent/eval-report.json
```

关键结果：

- `metrics.total_cases = 12`
- `metrics.success_rate = 1.0`
- `metrics.planning_success_rate = 1.0`
- `metrics.audit_success_rate = 1.0`
- `metrics.generated_files_total = 258`
- `metrics.rag_hit_rate = 1.0`
- `metrics.rag_hits_total = 46`

这组数据适合作为简历里的稳定指标，因为它能离线复现，不依赖 API key、网络或 provider 状态。

## 真实 LLM 运行证据

### 2026-05-13 自然语言 runtime 验证

| Case | Workspace | Planner | Audit | Build | Runtime |
| --- | --- | --- | --- | --- | --- |
| Machine | `workspace/real-llm-natural-machine-20260513` | `llm:openai-compatible` | 128 checks, 0 errors | pass | 通过 |
| Ruby Basic | `workspace/real-llm-natural-ruby-basic-20260513` | `llm:openai-compatible` | 329 checks, 0 errors | pass | 修复 runtime worldgen 问题后通过 |
| Progression | `workspace/real-llm-natural-progression-retry-20260513` | `llm:openai-compatible` | 541 checks, 0 errors | pass | 修复 worldgen / dimension / biome / advancement 问题后通过 |

这里的价值不是声称真实 LLM 一次永远成功，而是证明它能完成真实自然语言到 `ModSpec` 的规划，并且 runtime 验证暴露的问题已经反向推动生成器和 audit 加固。

### 2026-05-14 严格重生成检查

本轮要求真实 LLM 失败时不能静默算成功；`llm->rules` fallback 不计入 real LLM 成功。

| Case | Workspace | LLM result | Audit | Build | 结论 |
| --- | --- | --- | --- | --- | --- |
| Ruby Basic | `workspace/real-llm-regen2-ruby-basic-20260514` | `agent:llm:openai-compatible` | 304 checks, 0 errors | pass | 通过 |
| Machine | `workspace/real-llm-regen2-machine-20260514` | `agent:llm:openai-compatible` | 160 checks, 0 errors | pass | 通过 |
| Progression strict | `workspace=null` via `real-llm-regen4-progression-strict-20260514` request | provider timed out | not reached | not reached | 未通过 real LLM 标准 |
| Progression fallback hardening | `workspace/real-llm-regen3-progression-after-hardening-20260514` | `agent:llm->rules:openai-compatible` | 287 checks, 0 errors | pass | 只证明 fallback 产物可 build，不计入 real LLM 成功 |

这个结果适合面试时主动讲：真实 LLM 路径不是被包装成 100% 成功；系统已经能区分 real LLM 成功、provider 超时、以及 fallback 成功。

## 关键证据文件

每个真实 LLM workspace 里最值得展示的是：

```text
.agent/planner-mode.txt
.agent/llm-stability.json
.agent/llm-plan-raw.json
.agent/llm-plan-normalized.json
.agent/rag-context.json
.agent/llm-used-knowledge.json
.agent/audit-report.json
.agent/logs/gradle-build.log
```

其中 `.agent/llm-stability.json` 重点看：

- `provider = openai-compatible`
- `provider_config.api_key_present = true`
- `provider_config.model`
- `provider_health.status`
- `retry_attempts`
- `schema_retry_attempts`
- `json_repair_applied`
- `parse_attempts`
- `schema_validation_attempts`

这些字段可以证明真实 LLM 调用不是口头描述，也不会泄露 API key。

## 面试解释建议

可以这样讲：

> 我没有把真实 LLM 成功率包装成 100%。mock LLM 是稳定的离线基线，默认 12 个 eval case 全部通过；真实 LLM 路径我用 openai-compatible provider 跑过自然语言 case，成功生成了 Ruby Basic、Machine 和 Progression 的 `ModSpec`，并通过 audit/build/runtime 验证。复杂 Progression 严格重生成时出现过 provider timeout，所以我补了 `--require-llm`，避免 fallback 被误算成真实 LLM 成功。

更短一点：

> mock 用来保证可复现，真实 LLM 用来验证实际模型规划能力；系统用 `ModSpec`、schema retry、fallback 标记、audit、build 和 runtime 证据把两者区分开。

## 当前不足

- 真实 LLM 还没有纳入默认 12-case eval，因为这会引入网络、API key 和成本依赖。
- Progression 这类长 prompt 对 provider 超时敏感，需要更细粒度 case、缓存或分阶段规划。
- 现有真实 LLM 证据以本地 workspace 和文档记录为主，后续可以补一个只跑 2-3 个关键 case 的轻量 `real-llm-smoke` 命令。
- audit/build 仍不能完全替代游戏内 runtime 验证；worldgen、dimension、biome 和 advancement 的问题已经证明这一点。

## 推荐简历表述

- 建立 mock LLM 与真实 OpenAI-compatible provider 的对比验证链路：mock 基线默认 12/12 eval audit 通过，真实 LLM 在 Ruby Basic、Machine 等自然语言 case 上可生成 `ModSpec` 并通过 audit/build；严格模式下区分 provider timeout 与 fallback，避免把规则降级误计为 real LLM 成功。
