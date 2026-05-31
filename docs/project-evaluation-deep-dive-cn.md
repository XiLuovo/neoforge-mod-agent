# 项目评价与深度补充

> 文档定位：这是深度补充材料，不是主入口。需要展开项目价值、不足、后续路线或追问时，再读本文。当前边界以 [project-limitations.md](project-limitations.md) 为准。

## 先看哪里

如果只是为了学懂项目，先不要从本文开始。推荐顺序：

```text
docs/README.md
-> architecture.md
-> agent-workflow.md
-> direct-code-lane.md
-> capability-harvest-loop.md
-> project-limitations.md
```

本文只回答三个问题：

- 这个项目为什么比普通 Minecraft Mod 生成器更像 AI 工程项目？
- 当前亮点和不足分别是什么？
- 后续最值得推进的方向是什么？

## 项目价值

这个项目的价值不在“生成了一个 Minecraft Mod”，而在把 LLM 代码生成变成了一个可控工程闭环：

```text
自然语言需求
-> ModSpec / DSL / patch plan
-> deterministic generator / reviewed patch lane
-> Java / JSON / PNG / resources
-> audit / build / repair
-> eval / benchmark / replay / harvest evidence
```

最重要的设计取舍是：LLM 默认不直接裸写最终工程文件，而是先产出可校验意图；确定性 generator 和受控补丁通道负责落地；audit、build、repair、eval、replay 负责证明结果不是只看起来成功。

详细架构见 [architecture.md](architecture.md)，Agent 阶段见 [agent-workflow.md](agent-workflow.md)。

## 主要亮点

- **边界清楚**：稳定路径是 `ModSpec-first`，Direct Code Lane 也只接受结构化 workspace 补丁。
- **结果可复现**：同一个 `ModSpec` 可以由 deterministic generator 稳定生成。
- **失败可诊断**：`.agent/` 下保留 modspec、summary、audit、prompt trace、agent run、repair、diff、rollback 等证据。
- **质量可量化**：eval、benchmark、repair-eval、evidence-chain、test-matrix 让能力覆盖和失败类型可查。
- **后续可沉淀**：Free-Code Lab 把 generate gap 先放进隔离实验区，再由 harvest candidate 决定是否固化回 generator。

Direct Code Lane 机制见 [direct-code-lane.md](direct-code-lane.md)，能力采集闭环见 [capability-harvest-loop.md](capability-harvest-loop.md)。

## 当前不足

- 稳定落地的完整 domain 仍然只有 `minecraft.neoforge`，`spring.api` 和 `unity.component` 还是 planned。
- 生成能力仍偏模板化，复杂多方块结构、复杂 GUI、网络同步、完整 runtime 行为仍需要更强 DSL 或实验后固化。
- Direct Code Lane 第一版只支持 `write_file` 和精确一次 `replace_text`，没有 AST patch、事务式自动恢复或自动二轮 direct-code repair。
- audit/build 能发现结构、资源和编译问题，但不能替代真实 Minecraft runtime 自动化测试。
- mock LLM 基线稳定，真实 LLM 覆盖和成本/延迟/失败类型统计仍可继续增强。

更完整边界见 [project-limitations.md](project-limitations.md)。

## 后续路线

当前最值得做的是把 `Capability Harvest Loop` 跑完整：

```text
gap detected
-> Free-Code Lab
-> audit / build / manual runtime checklist
-> harvest candidate
-> ModSpec / DSL / generator / audit / test upgrade
-> regression protected
```

第一批固化目标建议继续围绕高级 machine GUI / BlockEntity，因为它能覆盖 Java、Menu、Screen、BlockEntity、资源 JSON、audit/build 和人工游戏内测试路径。

`SpringApiSpec` / `UnityComponentSpec` 仍有长期价值，但应放在第一个 NeoForge harvest 样本固化之后，用来证明 DomainSpec 抽象可以跨领域复用。

## 复述版本

30 秒：

> 这是一个面向 NeoForge 的受控 LLM 代码生成项目。它不是让模型直接写完整 Mod，而是把自然语言先转成 `ModSpec`、DSL 或受审查 patch plan，再由确定性 generator 和 Direct Code Lane 落地，最后用 audit、build、repair、eval 和 replay 留下证据。下一步主线是 Capability Harvest Loop：让 LLM 在隔离实验区探索 generate gap，成功后再固化回稳定 generator。

2 分钟：

> 项目的核心问题是 LLM 直接写 NeoForge 工程不稳定，容易错 API、资源路径、注册和 JSON。我的设计是 `ModSpec-first`：LLM 负责规划，validator/reviewer 负责检查，executor 用 generator 生成 Java/JSON/PNG，auditor/build 检查产物，repair 在失败后受控恢复。对于 ModSpec 表达不了的小范围源码修改，Direct Code Lane 允许结构化 `write_file` / `replace_text`，但必须经过 review、snapshot、audit/build 和 rollback evidence。后续 Free-Code Lab 会把稳定 generate 覆盖不了的需求放进实验副本，通过自动检查和人工 runtime checklist 后，再决定是否沉淀成 generator 能力。

## 常见追问

- 为什么不让 LLM 直接写整个 Mod？  
  因为 NeoForge 工程有强结构约束，直接写代码不可复现、难审计、难修复；结构化意图加 deterministic generator 更稳定。

- `DomainSpec` 和 `ModSpec` 有什么区别？  
  `DomainSpec` 是跨领域抽象，`ModSpec` 是 NeoForge domain 的稳定实现。

- Direct Code Lane 是不是通用 Coding Agent？  
  不是。它只允许结构化 workspace 补丁，路径、操作、内容、snapshot、audit/build 和 rollback 都受控。

- 怎么证明不是 demo？  
  看 `.agent/` 证据、unittest、audit/build、repair eval、benchmark、replay 和 failure lab。

- 下一步做什么最有价值？  
  先完成一个 Free-Code Lab 成功样本到 generator 固化的闭环，再考虑第二个 domain。
