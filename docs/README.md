# NeoForge Mod Agent 文档入口

这是公开文档的总入口。RC1 之后，项目定位已经从“一次性 generator”收敛为受控 NeoForge Minecraft Mod Coding Agent：规划、生成、工具调用修复、审查、验证、评测和证据链都围绕同一个可回放工作流组织。RC2 继续把 RAG 从普通检索升级成 Agentic RAG：有检索策略、query rewrite、多跳检索、citation trace、reviewer evidence sufficiency 和 RAG on/off ablation。

当前主线（RC1 基础闭环 + RC2 Agentic RAG）：

```text
Natural language
-> planner / ModSpec
-> deterministic generator baseline
-> real tool-calling repair/refine loop
-> Agentic RAG policy / multi-hop retrieve_rag / read files
-> structured patch with citation evidence
-> LLM reviewer evidence sufficiency check
-> audit/build gate
-> trace-backed benchmark / RAG ablation
-> replayable evidence
```

## 当前阅读入口

建议按这个顺序重新理解项目：

1. [RC1 学习与项目讲解入口](总览/rc1-learning-guide.md)
2. [总览](总览/README.md)
3. [Agent 与能力](Agent与能力/README.md)
4. [Agentic RAG](Agent与能力/rag.md)
5. [验证与可靠性](验证与可靠性/README.md)
6. [RAG Ablation Benchmark](验证与可靠性/benchmark-report.md)
7. [规格与生成](规格与生成/README.md)
8. [展示材料](发布与展示/showcase.md)

## 文档结构

- [总览](总览/README.md)：项目定位、架构、能力矩阵、边界和术语。
- [Agent 与能力](Agent与能力/README.md)：真实 tool-calling loop、RAG、LLM reviewer、provider、trace、辅助实验能力。
- [规格与生成](规格与生成/README.md)：ModSpec-first、DomainSpec、DSL 和 deterministic generator 的输入层。
- [验证与可靠性](验证与可靠性/README.md)：audit/build gate、repair loop、trace-backed `agent bench`、测试和证据链。
- [发布与展示](发布与展示/README.md)：RC1/RC2 demo、showcase、截图说明和发布检查清单。

## 公开口径

- 推荐 demo 入口是 `agent develop`、`agent repair`、`agent bench`。
- RC2 推荐补充展示 `agent bench --rag-ablation`，用 RAG on/off paired run 说明项目能评测 RAG 是否改变修复行为。
- 旧生成/修改命令、Direct Code Lane 和旧 eval/report 命令可以作为兼容或辅助能力讲解，但不是当前主线。
- reviewer 负责审查覆盖和风险，不能替代 deterministic audit/build gate。
- `.agent/` evidence 是演示和复盘的核心，而不是附属报告。
