# 真实 LLM 证据总览

这页汇总真实 provider 稳定性实验的结论，用于简历主项目说明和面试答辩。原始报告仍保留在 `workspace/real-llm-stability-runs`，本页只做结论整理，不替代原始 JSON。

## 一句话结论

mock 证明工程链路可复现；真实 LLM 实验证明 provider 输出可以在可复现 case 上进入 ModSpec、生成和 audit gate，并且失败会被拆成 provider、schema、audit、build、runtime、fallback 等类别。最新 13 case 真实跑批暴露出 1 个复杂世界/结构 prompt 的 schema failure，因此当前证据不是“所有 prompt 都稳定成功”，而是“成功率、失败类型和证据边界都能被解释”。

当前对外统计口径：最新 13 个 no-build + audit real LLM case 中 `12/13` strict success，`1/13` schema failure，provider/audit/fallback failure 均为 `0`，没有传入 runtime evidence，因此 `13/13` 只能记为 runtime unverified；额外历史 3 个 build case 中 provider/schema/audit 全部通过，依赖重试后 `3/3` strict generated projects 可 Gradle build；本地 unittest 当前可发现 185 个 case，2026-06-09 最近一次完整回归 185/185 通过。

## 证据清单

| 实验 | 日期 | 配置 | 结果 | 证明范围 |
| --- | --- | --- | --- | --- |
| `real-llm-13case-runtime-upgrade` | 2026-06-05 | real provider, audit, no build, no runtime evidence | `12/13` strict real LLM success；`1` schema failure；`13` runtime unverified | 真实 provider 13 case 稳定性、失败分类、runtime 证据边界 |
| `real-llm-10case-after-fix` | 2026-06-04 | real provider, audit, no build | `10/10` strict real LLM success | 真实模型到 ModSpec、生成器、audit 的稳定性 |
| `real-llm-build-3case-20260604-223533` | 2026-06-04 | real provider, audit, build | 原始统计 `1/3` build success；依赖重试后 `3/3` build success | 真实模型生成项目的 Gradle 编译可行性，以及外部依赖失败分类 |

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

面试时不要把所有数字混在一起说。

- `mock success`: 证明 deterministic pipeline、CI、replay、工程链路稳定。
- `real LLM success`: 真实 provider 严格生成成功，且没有 fallback。
- `provider failure`: API key、base URL、HTTP、timeout、provider 权限或网络问题。
- `schema failure`: 模型返回 JSON 或 ModSpec 不符合结构契约。
- `audit failure`: 生成完成，但 agent audit gate 不通过。
- `build failure`: 生成和 audit 完成，但 Gradle 编译不通过，可能是代码问题，也可能是外部依赖问题。
- `runtime unverified`: 没有传入 runtime evidence，不能算 runtime success。
- `fallback success`: 严格 real LLM 失败后 fallback 成功，只能单独记录，不能计入 real LLM success。

## 面试说法

可以这样讲：

> 我没有只用 mock 结果包装项目。mock 用来证明工程链路可复现；真实 provider 单独跑了最新 13 个 case，统计 provider、schema、audit、build、runtime、fallback 各类结果。最新一轮 `12/13` strict real LLM success，唯一失败是复杂世界/结构 prompt 的 schema failure，provider、audit、fallback failure 都是 `0`。我也明确记录了这轮没有 runtime evidence，所以 `13/13` 是 runtime unverified，不能包装成游戏内验证通过。随后我又保留了 3 个 build follow-up case，依赖重试后 3 个 strict generated projects 都能 Gradle build 成功。再加上本地 unittest 最近一次完整回归 185/185 通过，所以我能区分模型失败、结构化输出失败、审计失败、构建失败、runtime 未验证、外部环境失败和工程回归质量。

## 简历表述

可压缩成一条 bullet：

> Built a Minecraft NeoForge mod-generation agent with schema-constrained real-LLM planning, deterministic generation, audit gates, fallback isolation, runtime-evidence accounting, and replayable evidence reports; validated a 13-case real-provider run with 92.31% strict success, isolated one schema failure, and kept no-runtime cases separate from runtime success claims.

中文投递口径可写成：

> 完成最新 13 case real provider 稳定性验证：12/13 strict real LLM success，唯一失败归类为 schema failure；provider/audit/fallback failure 均为 0，并将缺失 runtime evidence 的 case 单独记为 runtime unverified；额外 build follow-up 中依赖重试后 3/3 strict generated projects 可 Gradle build，本地 unittest 最近一次完整回归 185/185 通过。

## 没有声称的部分

当前证据不声称已经完成 Minecraft 客户端内的人工游玩验证，也不声称所有 future prompts 都能成功。最新 13 case 明确有 1 个 schema failure，并且没有 runtime evidence 的 case 均记为 runtime unverified。它证明的是：在这批可复现 case 上，真实 provider 输出、schema 约束、生成器、audit gate、Gradle build follow-up 和 runtime 证据边界可以被分层统计和解释。
