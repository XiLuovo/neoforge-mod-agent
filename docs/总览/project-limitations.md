# Project Limitations

当前项目已经是受控 NeoForge Minecraft Mod Coding Agent，但仍有明确边界。

## 不是通用 Coding Agent

项目只稳定支持 `minecraft.neoforge` domain。LLM 不能自由编辑任意仓库文件，也不能输出无边界 diff。所有写入都必须经过 deterministic generator 或 structured patch executor。

## ModSpec-first 仍是核心

`ModSpec`、DSL 和 deterministic generator 仍是稳定生成的核心。tool-calling loop 用来读取、检索、修复和完善 generated workspace，不是绕过规格层的自由代码生成器。

## Reviewer 不是最终 gate

`LLMReviewer` 可以发现覆盖缺口、unsupported request 和 patch 风险，也可以触发下一轮 repair/refine context。但 reviewer approve 不代表成功；最终 success 必须由 audit/build gate 决定。

## Build 不等于 Minecraft Runtime

audit/build 可以验证结构、引用、资源和 Java 编译，但不能证明游戏内交互、平衡性、AI 行为或玩家体验。Minecraft runtime 自动化验收仍需要未来专门 harness。

## RAG 有边界

RAG 提供本地 NeoForge 知识和 citation，但它不是权威外部文档同步器。知识库需要维护；新 NeoForge API 或 Minecraft 版本变化仍需要人工更新。

## Benchmark 有边界

`agent bench` 已经评测真实 agent 行为，而不是只聚合静态 report。但 benchmark case 仍是小型本地回归集，不能代表全部 Mod 开发需求。

## 辅助能力边界

Direct Code Lane 是辅助/兼容能力，用于解释受控 workspace patch 通道。它不改变当前主线，也不能绕过 ModSpec、deterministic generator、audit/build gate 和 evidence 边界。

## 后续优先级

- 增加更真实的 NeoForge runtime smoke harness。
- 扩充 repair/develop benchmark case。
- 持续维护 RAG 知识库和 citation。
- 把成功的受控补丁模式沉淀为新的 `ModSpec` / DSL / generator / audit / tests。
