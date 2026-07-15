# 真实 LLM 证据总览

这页汇总真实 provider 稳定性实验的结论，用于项目说明和展示复盘。当前 checkout 中没有 `decomposed-planner-5case-ab` 与 `decomposed-real-llm-13case-smoke` 的原始 run；相关数字属于历史实验记录，在补充脱敏原始报告前标为待复验。现有可公开核对的旧 run 见 `evidence/portfolio/real-provider-13case-historical/`，它不是 decomposed planner 证据。

## 一句话结论

mock 证明工程链路可复现；真实 LLM 实验证明 provider 输出可以在可复现 case 上进入 ModSpec、生成和 audit gate，并且失败会被拆成 provider、schema、audit、build、runtime、fallback 等类别。当前证据不是“所有 prompt 都稳定成功”，而是“成功率、失败类型、token 成本和证据边界都能被解释”。

当前对外统计口径分层说明：

- decomposed planner A/B：5 个 real-provider generate case 中，decomposed planner `5/5` strict success、audit `5/5`、fallback `0`；相比 full-schema planner，provider-reported total tokens 从 `254,310` 降到 `5,875`，约降 `97.7%`。
- decomposed 13-case smoke：`12/13` strict real LLM success，audit `12/13`，fallback `0`，total tokens `22,904`；唯一失败是 `ruby_realm_world_structure`，属于 dimension / biome / structure / loot 复合世界生成的 planner/schema 覆盖边界。
- runtime 边界：没有传入 runtime evidence 的 case 只能记为 runtime unverified，不能表述成 Minecraft 客户端或服务端内验证通过。
- build 边界：代表性 real-provider generated workspaces 有 Gradle build follow-up；额外历史 3 个 build case 中 provider/schema/audit 全部通过，依赖重试后 `3/3` strict generated projects 可 Gradle build。

## 证据清单

| 实验 | 日期 | 配置 | 结果 | 证明范围 |
| --- | --- | --- | --- | --- |
| `decomposed-planner-5case-ab` | 2026-06-26 | real provider, audit, no build, no runtime evidence | decomposed `5/5` strict success；audit `5/5`；fallback `0`；total tokens `5,875`；相比 full-schema total tokens 降约 `97.7%` | decomposed planner 相比 full-schema 大 prompt 的 token、延迟和稳定性差异 |
| `decomposed-real-llm-13case-smoke` | 2026-06-26 | real provider, decomposed planner, audit, no build, no runtime evidence | `12/13` strict real LLM success；audit `12/13`；fallback `0`；total tokens `22,904` | decomposed planner 在垂直领域 13-case 集合上的真实 provider 稳定性和覆盖边界 |
| `real-llm-13case-runtime-upgrade` | 2026-06-05 | real provider, audit, no build, no runtime evidence | `12/13` strict real LLM success；`1` schema failure；`13` runtime unverified | 真实 provider 13 case 稳定性、失败分类、runtime 证据边界 |
| `real-llm-10case-after-fix` | 2026-06-04 | real provider, audit, no build | `10/10` strict real LLM success | 真实模型到 ModSpec、生成器、audit 的稳定性 |
| `real-llm-build-3case-20260604-223533` | 2026-06-04 | real provider, audit, build | 原始统计 `1/3` build success；依赖重试后 `3/3` build success | 真实模型生成项目的 Gradle 编译可行性，以及外部依赖失败分类 |

## Decomposed Planner A/B

运行配置：

- provider: `openai-compatible`
- model: `deepseek-v4-flash-ascend`
- response format: none
- cases: 5 个 generate case
- mode: strict real LLM, audit enabled, build disabled
- runtime evidence: none

结果：

| Planner | Strict real LLM | Audit | Fallback | Input Tokens | Output Tokens | Total Tokens | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| `decomposed` | `5/5` | `5/5` | `0` | `3,543` | `2,332` | `5,875` | `25.1s` |
| `full-schema llm` | `5/5*` | `5/5` | `0` | `247,395` | `6,915` | `254,310` | `44.7s` |

`Input Tokens`、`Output Tokens` 和 `Total Tokens` 均来自 provider usage 字段，不是按 prompt 文本估算。`full-schema llm` 的批量运行曾有一个 case 返回空输出并触发 schema failure，单独重试后通过，所以公开说明时写作 `5/5*`，并保留稳定性边界。这个对比证明的是 planner 拆分对 prompt 体量、延迟和长上下文稳定性的影响，不证明 Minecraft runtime。

关键结论：

- decomposed planner 将输入 token 从 `247,395` 降到 `3,543`，约降 `98.6%`。
- decomposed planner 将 total tokens 从 `254,310` 降到 `5,875`，约降 `97.7%`。
- 平均延迟从 `44.7s` 降到 `25.1s`。
- decomposed planner 在 5-case 批量 strict run 中没有 fallback；full-schema planner 的长上下文批量运行出现过空输出，需要单 case 重试。

## Decomposed 13-Case Smoke

运行配置：

- provider: `openai-compatible`
- model: `deepseek-v4-flash-ascend`
- response format: none
- planner: `decomposed`
- cases: 13 个 generate case
- mode: strict real LLM, audit enabled, build disabled
- timeout: 每次 provider request 900s
- runtime evidence: none

结果：

| Metric | Value |
|---|---:|
| Target cases | `13` |
| Strict real LLM success | `12/13` |
| Audit success | `12/13` |
| Representative Gradle build smoke | `2/2` |
| Fallback used | `0` |
| Total tokens | `22,904` |
| Average latency on successful cases | `46.4s` |

通过 case 包括 `basic_ruby`、`ruby_charm_behavior`、`speed_crystal_behavior`、`ruby_apple_effect`、`ruby_sword_ignite`、`ruby_pickaxe_tool`、`ruby_tool_set`、`ruby_armor_set`、`ruby_block_variants`、`ruby_ore_worldgen`、`ruby_goblin_entity` 和 `progression_gameplay_loop`。

失败 case 是 `ruby_realm_world_structure`。观察到的原因是 decomposed planner 当前 feature-plan 路径没有完整覆盖或保留 `dimension`、`biome`、`world_feature`、`structure`、`loot_pool` 复合世界生成能力，后续规范化 ModSpec 时围绕 ore drop reference 产生不合法结构。这是 planner/schema 覆盖边界，不是 provider timeout，不是 JSON mode 兼容问题，也不是 Minecraft runtime 失败。

## 13 Case Runtime Upgrade Run

运行配置：

- run id: `real-llm-13case-runtime-upgrade`
- provider: `openai-compatible`
- model: `deepseek-v4-flash`
- build: disabled
- audit: enabled
- fallback probe: enabled
- runtime evidence: none

关键指标：

- total cases: `13`
- strict success: `12`
- real LLM success: `12`
- strict / real LLM success rate: `92.31%`
- provider failure: `0`
- schema failure: `1`
- audit failure: `0`
- build failure: `0`（本轮 `--no-build`，不是 build 通过声明）
- runtime failure: `0`（本轮没有 runtime evidence，不代表 runtime 通过）
- runtime checked: `0`
- runtime success: `0`
- runtime unverified: `13`
- fallback success: `0`
- retry attempts: `3`
- schema retry attempts: `1`
- total tokens: `2,224,022`
- average latency: `30,168.31 ms`

失败样本：

- `ruby_realm_world_structure`: `schema_failure`
- 现象：LLM planner 多次返回 invalid JSON，报告中记录 `LLM planner returned invalid JSON.`
- 解释：这是结构化输出/schema 契约失败，不是 provider 连接失败、audit 失败、build 失败或 fallback 成功。

代表性保留 workspace：

- `workspace/real-llm-stability-runs/real-llm-13case-runtime-upgrade/runs/01-basic_ruby-strict`
- `workspace/real-llm-stability-runs/real-llm-13case-runtime-upgrade/runs/11-ruby_goblin_entity-strict`
- `workspace/real-llm-stability-runs/real-llm-13case-runtime-upgrade/runs/13-progression_gameplay_loop-strict`

原始报告：

- `workspace/real-llm-stability-runs/real-llm-13case-runtime-upgrade/.agent/real-llm-stability.json`
- `workspace/real-llm-stability-runs/real-llm-13case-runtime-upgrade/.agent/real-llm-stability.md`

## 10 Case Real Provider

运行配置：

- provider: `openai-compatible`
- model: `deepseek-v4-flash`
- build: disabled
- audit: enabled
- fallback probe: enabled

关键指标：

- total cases: `10`
- strict success: `10`
- real LLM success: `10`
- provider failure: `0`
- schema failure: `0`
- audit failure: `0`
- fallback success: `0`
- JSON repair applied: `0`
- total tokens: `1,707,714`
- average latency: `44,312.2 ms`

代表性保留 workspace：

- `workspace/real-llm-stability-runs/real-llm-10case-after-fix/runs/10-ruby_ore_worldgen-strict`

原始报告：

- `workspace/real-llm-stability-runs/real-llm-10case-after-fix/.agent/real-llm-stability.json`
- `workspace/real-llm-stability-runs/real-llm-10case-after-fix/.agent/real-llm-stability.md`

## 3 Case Build Follow-up

运行配置：

- provider: `openai-compatible`
- model: `deepseek-v4-flash`
- build: enabled
- audit: enabled
- fallback probe: enabled

原始统计：

- total cases: `3`
- strict success: `1`
- real LLM success: `1`
- provider failure: `0`
- schema failure: `0`
- audit failure: `0`
- build failure: `2`
- fallback success: `0`
- JSON repair applied: `0`
- total tokens: `511,342`

两个原始 build failure 都发生在 Gradle `:createMinecraftArtifacts` 阶段，错误集中在访问 `https://maven.neoforged.net` 下载 NeoForge/Minecraft artifacts 时的 TLS/依赖解析问题。provider、schema、audit gate 均未失败。

依赖缓存打通后，不重新调用 LLM，直接重试两个 strict workspace 的 Gradle build：

- `01-basic_ruby-strict`: `BUILD SUCCESSFUL in 16s`
- `02-ruby_charm_behavior-strict`: `BUILD SUCCESSFUL in 12s`
- `03-speed_crystal_behavior-strict`: 原始 strict build already successful

因此 build follow-up 的最终解释是：`3/3` generated strict projects can build after dependency retry。原始 `2` 个 build failure 应归类为瞬时外部依赖/TLS/cache 问题，而不是真实模型、schema、audit 或生成代码失败。

代表性保留 workspace：

- `workspace/real-llm-stability-runs/real-llm-build-3case-20260604-223533/runs/03-speed_crystal_behavior-strict`

原始报告：

- `workspace/real-llm-stability-runs/real-llm-build-3case-20260604-223533/.agent/real-llm-stability.json`
- `workspace/real-llm-stability-runs/real-llm-build-3case-20260604-223533/.agent/real-llm-stability.md`

## 分类口径

公开说明时不要把所有数字混在一起说。

- `mock success`: 证明 deterministic pipeline、CI、replay、工程链路稳定。
- `real LLM success`: 真实 provider 严格生成成功，且没有 fallback。
- `provider failure`: API key、base URL、HTTP、timeout、provider 权限或网络问题。
- `schema failure`: 模型返回 JSON 或 ModSpec 不符合结构契约。
- `audit failure`: 生成完成，但 agent audit gate 不通过。
- `build failure`: 生成和 audit 完成，但 Gradle 编译不通过，可能是代码问题，也可能是外部依赖问题。
- `runtime unverified`: 没有传入 runtime evidence，不能算 runtime success。
- `fallback success`: 严格 real LLM 失败后 fallback 成功，只能单独记录，不能计入 real LLM success。

## 项目讲解口径

可以这样讲：

> mock 用来证明工程链路可复现；真实 provider 证据必须绑定具体 run ID、模型、planner、token 统计和 build/runtime 状态。当前公开包保留了一轮历史 non-decomposed 13-case 报告；decomposed 13-case 和 5-case A/B 的原始报告仍待补齐。完整回归是否通过以当前 CI 或本轮测试输出为准，不在长期文档中固定测试数量。

## 公开摘要

可压缩成一条公开摘要：

> Built a Minecraft NeoForge mod-generation agent with schema-constrained real-LLM planning, deterministic generation, audit gates, fallback isolation, runtime-evidence accounting, and replayable evidence reports; validated a 13-case real-provider run with 92.31% strict success, isolated one schema failure, and kept no-runtime cases separate from runtime success claims.

中文公开摘要可写成：

> 真实 provider 稳定性结果应按 run 单独陈述：不要把 decomposed 13-case、历史 non-decomposed 13-case 和独立 build follow-up 合并成一次运行。完整回归结果以当前 CI 或命令输出为准。

## 没有声称的部分

当前证据不声称已经完成 Minecraft 客户端内的人工游玩验证，也不声称所有 future prompts 都能成功。最新 13 case 明确有 1 个 schema failure，并且没有 runtime evidence 的 case 均记为 runtime unverified。它证明的是：在这批可复现 case 上，真实 provider 输出、schema 约束、生成器、audit gate、Gradle build follow-up 和 runtime 证据边界可以被分层统计和解释。
