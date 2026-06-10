# NeoForge Mod Agent 文档入口

这是公开文档的总入口。RC1 之后，项目定位已经从“一次性 generator”收敛为受控 NeoForge Minecraft Mod Coding Agent：规划、生成、工具调用修复、审查、验证、评测和证据链都围绕同一个可回放工作流组织。

当前主线（RC1 / Phase 0-4）：

```text
Natural language
-> planner / ModSpec
-> deterministic generator baseline
-> real tool-calling repair/refine loop
-> RAG / read files / structured patch / audit
-> LLM reviewer
-> audit/build gate
-> trace-backed benchmark
-> replayable evidence
```

## 当前阅读入口

建议按这个顺序重新理解项目：

1. [RC1 学习与面试入口](总览/rc1-learning-guide.md)
2. [总览](总览/README.md)
3. [Agent 与能力](Agent与能力/README.md)
4. [规格与生成](规格与生成/README.md)
5. [验证与可靠性](验证与可靠性/README.md)
6. [RC1 展示材料](发布与展示/agent-rc1-showcase.md)

## 文档结构

- [总览](总览/README.md)：项目定位、架构、能力矩阵、边界和术语。
- [Agent 与能力](Agent与能力/README.md)：真实 tool-calling loop、RAG、LLM reviewer、provider、trace、辅助实验能力。
- [规格与生成](规格与生成/README.md)：ModSpec-first、DomainSpec、DSL 和 deterministic generator 的输入层。
- [验证与可靠性](验证与可靠性/README.md)：audit/build gate、repair loop、trace-backed `agent bench`、测试和证据链。
- [发布与展示](发布与展示/README.md)：RC1 demo、showcase、截图说明和发布检查清单。
- [学习笔记](学习笔记/README.md)：个人学习、简历、面试和复盘材料，不作为架构真相源。
- [历史档案](历史档案/README.md)：旧 test matrix、旧 version history、旧评估报告和迁移记录。

## 公开口径

- 推荐 demo 入口是 `agent develop`、`agent repair`、`agent bench`。
- 旧生成/修改命令、Direct Code Lane、Free-Code Lab 和旧 eval/report 命令可以作为兼容或辅助能力讲解，但不是 RC1 主线。
- reviewer 负责审查覆盖和风险，不能替代 deterministic audit/build gate。
- `.agent/` evidence 是演示和复盘的核心，而不是附属报告。
