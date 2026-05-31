# README 术语表

> 文档定位：这是术语词典，不是主学习路线。先按 [project-learning-plan-cn.md](project-learning-plan-cn.md) 学 Day 01-07；遇到词看不懂时，再回到本文按词查。

## 最先记住的一句话

```text
LLM 负责理解和规划，ModSpec / DSL 负责把想法变成结构化设计图，generator 负责稳定生成文件，audit/build/repair/eval/replay 负责证明它能用、能修、能复盘。
```

## 核心架构词

| 词 | 一句话理解 |
| --- | --- |
| NeoForge | Minecraft Java 版的 Mod 开发框架，本项目面向 NeoForge 26.1。 |
| Mod | Minecraft 模组，用来给游戏添加物品、方块、机制或资源。 |
| LLM | 大语言模型，在本项目里主要负责理解需求和规划结构化意图。 |
| Agent | 不是单次聊天，而是 planner/reviewer/executor/auditor/repair/trace 组成的 workflow。 |
| ModSpec | NeoForge Mod 的结构化设计图，也是 generator / audit / repair 的核心真相源。 |
| DomainSpec | 更抽象的领域规格层；`ModSpec` 是 `minecraft.neoforge` domain 的稳定实现。 |
| DSL | 领域专用小语言，例如 Behavior DSL、Machine DSL、Entity DSL。 |
| deterministic generator | 确定性生成器，同一个规格应稳定生成同样的 Java / JSON / PNG / resources。 |
| intent contract | Agent 阶段之间传递的结构化意图，可以包含 ModSpec、DSL、patch plan 或 routing decision。 |
| routing decision | planner/reviewer 判断需求走 ModSpec、Direct Code Lane 还是实验通道的路由结果。 |

## 当前两条扩展路线

| 词 | 一句话理解 |
| --- | --- |
| Direct Code Lane | 生产 agent run 的受控补丁通道，只允许结构化 `write_file` / `replace_text` workspace 补丁。 |
| rollback evidence | Direct Code Lane 写文件前后的快照、diff、rollback report，用来说明失败时怎么恢复。 |
| Capability Harvest Loop | 能力采集闭环：generate gap 先实验，成功后再固化进稳定 generator。 |
| Free-Code Lab | 隔离实验区，复制已有 workspace 后让 LLM 在副本里做结构化实验补丁。 |
| harvest candidate | Free-Code Lab 产出的候选报告，记录 gap、结果、失败原因和是否值得固化。 |
| manual runtime checklist | 人工游戏内测试清单，例如能否进世界、物品是否出现、GUI 是否能打开。 |

详细机制以 [direct-code-lane.md](direct-code-lane.md) 和 [capability-harvest-loop.md](capability-harvest-loop.md) 为准。

## 验证和证据词

| 词 | 一句话理解 |
| --- | --- |
| audit | 静态审计，检查生成文件、路径、资源引用、配方、worldgen、注册等是否一致。 |
| build | Gradle 编译验证；能发现 Java/Gradle 编译问题，但不能替代 Minecraft runtime 测试。 |
| repair | 失败后的受控恢复流程，优先根据 ModSpec 重生成 managed files。 |
| eval | 固定题集评测，用来比较生成质量和能力覆盖。 |
| benchmark | 对比不同 provider、模型或版本的表现。 |
| replay | 离线回放一次 agent run，帮助复盘 planner、executor、auditor、repair 的过程。 |
| evidence chain | 把 spec、trace、audit、build、repair、eval、dashboard 等证据串起来。 |
| failure lab | 主动制造坏 workspace，再验证 audit 和 repair 能否发现与恢复。 |
| quality gate | 串联 compile、unit test、schema、example、eval、failure lab、repair eval 等检查。 |

## LLM / RAG / Tool 词

| 词 | 一句话理解 |
| --- | --- |
| mock provider | 离线稳定的模拟 LLM，用于学习、回归和演示，不代表真实模型能力。 |
| real provider | 真实 OpenAI-compatible LLM，需要单独配置和验证。 |
| fallback | 真实 provider 失败时可能降级到 rules/mock；fallback 成功不能算真实 LLM 成功。 |
| RAG | 本地 NeoForge 知识检索层，给 planner 和 repair 提供上下文。 |
| tool manifest | 内部工具能力的 schema 化契约，不等于已经运行的 MCP server。 |
| MCP | Model Context Protocol；本项目目前只是有 tool manifest 作为未来映射基础。 |

## Minecraft / 资源词

| 词 | 一句话理解 |
| --- | --- |
| item / block / ore | 物品、方块、矿石，是基础 Mod 内容类型。 |
| tool / armor | 工具和护甲，可以由材料、配方和资源共同生成。 |
| recipe | 合成配方 JSON。 |
| loot table | 掉落表 JSON。 |
| worldgen | 世界生成，例如矿石生成高度、次数和规则。 |
| resources | `src/main/resources` 下的 lang、model、texture、blockstate、datapack 等资源。 |
| GUI | 图形界面；当前 machine GUI 有受控模板，任意复杂 GUI 仍是边界。 |
| BlockEntity | Minecraft 中用于方块持久状态和交互逻辑的组件，machine 能力会用到。 |

## 边界词

| 词 | 一句话理解 |
| --- | --- |
| 模板化 | 用固定模板和结构化规则生成，牺牲部分自由度换取稳定和可审计。 |
| 结构化 | 把需求拆成字段、列表和规则，而不是一大段自由文本。 |
| 可审计 | 生成结果能被规则检查和证据复盘。 |
| 受控 patch 模式 | 不是任意改代码，而是在限定范围里生成补丁计划、检查、执行和回滚。 |
| runtime 测试 | 真正打开 Minecraft 后验证游戏内行为；当前 audit/build 不能完全替代它。 |

## 最该先记的 12 个词

| 英文 | 中文 | 一句话理解 |
| --- | --- | --- |
| LLM | 大语言模型 | 负责理解需求和规划，不直接裸写最终文件 |
| Agent | 工作流角色 | 把规划、生成、检查、修复串起来 |
| ModSpec | 模组规格 | Minecraft Mod 的结构化设计图 |
| DomainSpec | 领域规格 | 比 ModSpec 更抽象的规格层 |
| DSL | 领域小语言 | 用受控语法描述行为、机器、实体等 |
| generator | 生成器 | 根据规格稳定生成 Java/JSON/PNG |
| audit | 审计 | 检查文件、路径、资源引用是否正确 |
| build | 构建 | 用 Gradle 验证项目能否编译 |
| repair | 修复 | 出错后受控恢复生成文件 |
| eval | 评测 | 固定题集测试生成质量 |
| benchmark | 基准比较 | 比较模型或版本效果 |
| replay | 回放 | 复盘一次 agent 运行过程 |
