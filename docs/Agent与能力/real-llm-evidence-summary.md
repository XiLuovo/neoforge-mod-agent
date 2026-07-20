# 真实 LLM 证据总览

这页汇总真实 provider 稳定性实验的结论，用于项目说明和展示复盘。2026-07-18 已重新运行 5-case full-schema / decomposed A/B；2026-07-19 又完成 post-fix decomposed 13-case。两轮当前实验的脱敏 raw report 均已纳入 `evidence/portfolio/`，更早的 2026-06-26 数字只作历史对照。

## 一句话结论

mock 证明工程链路可复现；真实 LLM 实验证明 provider 输出可以在可复现 case 上进入 ModSpec、生成和 audit gate，并且失败会被拆成 provider、schema、audit、build、runtime、fallback 等类别。当前证据不是“所有 prompt 都稳定成功”，而是“成功率、失败类型、token 成本和证据边界都能被解释”。

当前对外统计口径分层说明：

- 当前 5-case A/B：修复后的 decomposed batch `5/5` strict + audit、semantic `3/5`；full-schema batch `5/5` strict + audit、semantic `4/5`。decomposed total tokens `6,917`，full-schema `253,819`，约降 `97.3%`；平均延迟约 `10.9s` 对 `46.0s`。修复前的 `4/5` batch 失败仍作为独立 evidence 保留。
- 当前 decomposed 13-case：`12/13` strict real LLM success，成功 case audit `12/12`，semantic `7/13`，feature match `15/33`，category match `22/37`，fallback `0`，total tokens `29,497`，平均延迟 `33.1s`；唯一 strict 失败是 `ruby_realm_world_structure`。这说明流程稳定性和需求语义覆盖必须分开统计。
- runtime 边界：没有传入 runtime evidence 的 case 只能记为 runtime unverified，不能表述成 Minecraft 客户端或服务端内验证通过。
- build 边界：代表性 real-provider generated workspaces 有 Gradle build follow-up；额外历史 3 个 build case 中 provider/schema/audit 全部通过，依赖重试后 `3/3` strict generated projects 可 Gradle build。

## 证据清单

| 实验 | 日期 | 配置 | 结果 | 证明范围 |
| --- | --- | --- | --- | --- |
| `resume-ab-20260718-decomposed-5case-fix1` | 2026-07-18 | real provider, decomposed, audit, no build, no runtime evidence | `5/5` strict + audit；total tokens `6,917`；平均延迟 `10.9s` | 修复后 decomposed planner 的当前可复验结果 |
| `resume-ab-20260718-fullschema-5case` | 2026-07-18 | real provider, full-schema, audit, no build, no runtime evidence | `5/5` strict + audit；total tokens `253,819`；平均延迟 `46.0s` | 同条件 full-schema 对照 |
| `resume-ab-20260718-decomposed-5case` | 2026-07-18 | real provider, decomposed, audit, no build, no runtime evidence | 修复前 `4/5`；`basic_ruby` 单独 retry `1/1` | 失败→修复前基线；不能被 retry 改写 |
| `resume-decomposed-13case-postfix-20260719` | 2026-07-19 | real provider, decomposed, audit, no build, no runtime evidence | `12/13` strict；audit `12/12`；semantic `7/13`；feature `15/33`；category `22/37`；fallback `0` | 当前可复验的 13-case 流程稳定性、unsupported capability 和语义 warning 边界 |
| `decomposed-planner-5case-ab` | 2026-06-26 | historical summary only; raw run unavailable | 历史记录：decomposed `5/5`、full-schema `5/5*`；total tokens 约降 `97.7%` | 仅作历史对照，不作为当前可复验主指标 |
| `decomposed-real-llm-13case-smoke` | 2026-06-26 | real provider, decomposed planner, audit, no build, no runtime evidence | `12/13` strict real LLM success；audit `12/13`；fallback `0`；total tokens `22,904` | decomposed planner 在垂直领域 13-case 集合上的真实 provider 稳定性和覆盖边界 |
| `real-llm-13case-runtime-upgrade` | 2026-06-05 | real provider, audit, no build, no runtime evidence | `12/13` strict real LLM success；`1` schema failure；`13` runtime unverified | 真实 provider 13 case 稳定性、失败分类、runtime 证据边界 |
| `real-llm-10case-after-fix` | 2026-06-04 | real provider, audit, no build | `10/10` strict real LLM success | 真实模型到 ModSpec、生成器、audit 的稳定性 |
| `real-llm-build-3case-20260604-223533` | 2026-06-04 | real provider, audit, build | 原始统计 `1/3` build success；依赖重试后 `3/3` build success | 真实模型生成项目的 Gradle 编译可行性，以及外部依赖失败分类 |

## 当前可复验的 5-Case A/B（2026-07-18）

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
| `decomposed` post-fix batch | `5/5` | `5/5` | `0` | `4,715` | `2,202` | `6,917` | `10.9s` |
| `full-schema llm` batch | `5/5` | `5/5` | `0` | `246,052` | `7,767` | `253,819` | `46.0s` |

`Input Tokens`、`Output Tokens` 和 `Total Tokens` 均来自 provider usage 字段，不是按 prompt 文本估算。修复前 decomposed batch 的 `basic_ruby` 因生成无效 ModSpec 归为 `agent_failure`；修复后同一 5-case 集合达到 `5/5`。修复后报告仍可能记录 progression link 等语义警告，因此这里证明的是 strict planning + audit 稳定性，不是所有自然语言语义都已 runtime 验收。

离线 semantic coverage 刷新复用了 evaluator 的 feature/category 匹配规则，不重新调用 provider。当前 post-fix decomposed 为 feature `5/5`、category `9/13`、semantic `3/5`；full-schema 为 feature `5/5`、category `12/13`、semantic `4/5`。semantic success 是独立指标，不改写 strict success。

关键结论：

- decomposed post-fix 将输入 token 从 `246,052` 降到 `4,715`，约降 `98.1%`。
- decomposed post-fix 将 total tokens 从 `253,819` 降到 `6,917`，约降 `97.3%`。
- 平均延迟从 `46.0s` 降到 `10.9s`。
- 修复前 `4/5`、修复后 `5/5` 的并列证据说明：prompt 拆分带来显著成本/延迟收益，同时确定性 hardening 修复了由 unsupported dependency、vanilla namespace 和 recipe ID collision 造成的失败。

脱敏冻结报告见 [Portfolio Evidence](../../evidence/portfolio/README.md)。

已有 stability report 可离线刷新 semantic coverage，不会重新调用 provider：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 scripts/refresh_real_llm_semantics.py `
  --report workspace/real-llm-stability-runs/<run>/.agent/real-llm-stability.json `
  --cases examples/real_llm_stability_cases.json
```

脚本会在同一 `.agent/` 目录写出 `semantic-coverage.json` 和 `semantic-coverage.md`。semantic coverage 复用 evaluator 的 feature/category 规则；它不等于 build 或 Minecraft runtime 验收。

## 历史 5-Case A/B（2026-06-26，待复验）

历史摘要记录 decomposed `5/5`、full-schema `5/5*`，total tokens `254,310 -> 5,875`、平均延迟 `44.7s -> 25.1s`。对应 raw run 不在当前 checkout，因此这些数字只作演进对照，不作为当前公开主指标。

## 当前可复验的 Decomposed 13-Case（2026-07-19）

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
| Audit success | `12/12 attempted` |
| Fallback used | `0` |
| Total tokens | `29,497` |
| Average latency | `33.1s` |
| Semantic success | `7/13` |
| Expected feature match | `15/33` |
| Expected category match | `22/37` |

通过 case 包括 `basic_ruby`、`ruby_charm_behavior`、`speed_crystal_behavior`、`ruby_apple_effect`、`ruby_sword_ignite`、`ruby_pickaxe_tool`、`ruby_tool_set`、`ruby_armor_set`、`ruby_block_variants`、`ruby_ore_worldgen`、`ruby_goblin_entity` 和 `progression_gameplay_loop`。

失败 case 是 `ruby_realm_world_structure`。模型返回的 `dimension`、`biome`、`world_feature`、`structure` 和 `loot_pool` 均不在 decomposed v1 的受支持 feature type 集合中，确定性 planner 将其忽略后没有剩余可执行 feature，因此以 `agent_failure` 结束。它没有进入 audit；这不是 provider timeout、schema JSON 解析错误或 Minecraft runtime 失败。

成功 case 也必须结合 warning 解读：`ruby_sword_ignite` 曾移除空 behavior，`ruby_block_variants` 的 block feature 被 decomposed v1 忽略，部分 progression 输出存在 missing links、unknown references 或缺少 quest chain 的提示。因此这轮 `12/13` 证明真实 provider 输出能够进入受控 ModSpec/generator/audit 流程，但不能单独证明 12 个自然语言请求都获得了完整语义覆盖。

脱敏冻结报告见 [Portfolio Evidence](../../evidence/portfolio/README.md)。

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

本页汇总的上述 real-provider runs 没有附带 Minecraft 客户端人工 runtime evidence，也不声称所有 future prompts 都能成功。对应 13-case run 明确有 1 个 schema failure，且该 run 中没有 runtime evidence 的 case 均记为 runtime unverified。仓库后来补充的独立人工 runtime 验收见 `evidence/runtime/`，不能反向改写这些历史 provider runs 的验证状态。
