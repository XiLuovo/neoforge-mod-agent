# RAG 更新与 Chunk 策略

> 文档定位：这是 RAG chunk 和索引策略专项材料，不是主学习入口。需要解释为什么这样切知识库时再读。

这份文档回答面试里很容易被追问的几个问题：

- RAG 知识条目怎么切？
- 为什么不直接按固定 token 数切？
- 什么时候关键词检索更适合？
- 知识库怎么更新，怎么避免过期？

结论先说：这个项目的 RAG 不是用来读长文章，而是给 planner 和 repair 提供可执行的 NeoForge 约束。所以 chunk 应该按“能约束生成或修复的知识单元”来切，而不是按整篇文档或固定长度硬切。

## 当前 RAG 定位

本项目的 RAG 是本地、确定性、可回放的知识层：

- planner 阶段：给 LLM 提供 NeoForge API、资源路径、worldgen schema、受控扩展边界。
- repair 阶段：根据 audit/build root cause 检索修复规则。
- eval 阶段：用 `rag-eval` 量化 Recall@K、MRR、category/capability hit 和 query rewrite 效果。

它不是实时网页爬虫，也不是外部向量数据库。这样做的好处是本地演示稳定、证据可复现、面试时边界好讲。

## Chunk 怎么切

推荐按这几类切：

- API 规则：比如注册入口、Identifier、resource location、NeoForge event hook。
- 资源结构：比如 item model path、blockstate path、lang key、loot table path。
- 数据 schema：比如 configured feature、placed feature、biome modifier、recipe、tag。
- 错误类型：比如缺 texture、缺 model、JSON path 错误、worldgen runtime schema 错误。
- 修复规则：比如 managed files 重生成、repair-loop 可以修什么、不能修什么。
- 项目边界：比如默认走 `ModSpec-first`；Direct Code Lane 只能产出结构化 workspace 补丁，不能自由写 Gradle 或任意 Java。

不推荐按“每 500 token 一段”作为第一原则。固定长度切分适合长文档问答，但这里的目标是工程生成和修复，chunk 必须足够短、足够稳定、足够能落到 validator/audit/build 上。

## 好 Chunk 的标准

一个好的知识条目应该满足：

- 有唯一 `id`，例如 `worldgen.ore_rule_test`。
- 有明确 `category`，例如 `worldgen`、`assets`、`audit`。
- 有 `capability` 或 tags，方便 eval 按能力统计命中。
- 内容只讲一个可执行约束，不混进太多不相关上下文。
- 能回答“它会影响哪个生成器、哪个 audit 规则、哪个修复动作”。
- 过期时可以单独替换，不需要重写整篇知识库。

例子：

```text
worldgen.ore_rule_test
category: worldgen
capability: ore_worldgen
content: overworld ore should use configured_feature + placed_feature + biome_modifier ...
```

这比把整篇 worldgen 文档塞成一个 chunk 更适合本项目，因为 planner 只需要明确的生成约束，repair 只需要明确的修复线索。

## 关键词、语义检索和 Hybrid

NeoForge 这种场景符号很多，关键词检索非常重要：

- `configured_feature`
- `placed_feature`
- `loot_table`
- `pack.mcmeta`
- `Identifier.fromNamespaceAndPath`
- `assets/<modid>/models/item`

这些符号如果被向量化后语义漂移，反而可能不如关键词稳定。

但自然语言需求也需要 query expansion：

```text
红宝石矿石在地下自然生成
-> ruby ore overworld underground worldgen configured_feature placed_feature biome_modifier
```

所以当前最稳的路线是：

```text
keyword retrieval + query expansion + rag-eval
```

后续如果知识库变大，再考虑：

- `multi_query`：从用户请求拆出多个检索 query。
- `hybrid keyword + semantic`：符号走关键词，自然语言走语义。
- `rerank`：先粗召回，再按 capability、category、query token 覆盖重排。

不建议第一步就上外部向量数据库，因为当前项目更需要本地可复现证据，而不是引入额外服务和依赖。

## 知识库怎么更新

推荐流程：

1. 从新失败样例、audit 规则、生成器变更或 NeoForge 文档变化中提取一个最小知识点。
2. 给知识点分配稳定 id、category、capability、tags。
3. 把它写成单一约束，不写成泛泛解释。
4. 给 `examples/rag_eval_cases.json` 补一个能命中它的 case。
5. 跑 `rag-eval`，确认新增知识没有破坏已有检索命中。

这样知识更新不是“改 prompt 靠感觉”，而是“改知识库 + 改 eval case + 看指标”。

## 怎么避免过期知识

本项目可以用低成本方式控制过期风险：

- 每条知识写清适用版本，例如 NeoForge 26.1。
- 把 upstream 文档链接或来源备注放进知识条目 metadata，而不是散落在 prompt 里。
- RAG 命中只作为 planner/repair 依据，最终仍由 schema、validator、audit/build 兜底。
- 用 `rag-eval` 发现 query 命中错误 category 或旧规则。
- 版本升级时先跑 eval / audit / build，而不是直接相信旧知识。

面试时可以这样说：

> RAG 不能替代验证。我的项目把 RAG 当作可追踪的知识输入，命中会写进 trace，但最终产物必须通过 ModSpec validation、deterministic generator、audit 和 build。知识库更新后还要补 rag-eval case，看 Recall@K 和 category hit 有没有回归。

## 和简历主线的关系

这份策略文档可以支撑一个更硬的说法：

> 我不是只把文档塞进 prompt，而是把 RAG 做成可维护的本地知识层：按 API、资源结构、错误类型和修复规则切 chunk，用 query expansion 提升自然语言请求召回，再用 rag-eval 量化 Recall@K、MRR 和 category/capability hit。
