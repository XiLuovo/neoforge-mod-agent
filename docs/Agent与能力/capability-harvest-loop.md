# Capability Harvest Loop（Legacy / Internal）

> 当前定位：这是历史实验能力说明，不是当前推荐 demo 主线，也不是公开能力矩阵的一部分。

## 用途

当 deterministic generator 暂时表达不了某类需求时，Free-Code Lab 曾用于复制已有 generated workspace 到隔离目录，让 LLM 在副本里探索结构化实验 patch。实验结果只产生实验记录和 harvest candidate，不自动进入稳定 generator。

```text
generator gap
-> isolated lab workspace
-> structured experimental patch
-> audit/build/manual checklist
-> harvest candidate
-> future ModSpec / DSL / generator / audit / tests
```

## 与当前主线的关系

当前推荐主线已经收敛为：

```text
agent develop / repair
-> real tool-calling loop
-> Agentic RAG policy / citation trace
-> structured patch
-> reviewer
-> audit/build gate
```

Capability Harvest Loop / Free-Code Lab 只保留为 legacy/internal 背景：如果某个实验模式值得长期保留，必须先沉淀为 ModSpec / DSL / generator / audit / tests，不能依赖 LLM 下次自由发挥。

## 边界

- 只写实验副本，不改原 workspace。
- 不改本工具源码。
- 不自动合并到 generator。
- 不替代 reviewer 或 audit/build gate。
- 成功样本必须转化为规格、模板、audit 和测试后才能进入稳定能力。

## 当前建议

对外介绍和演示不再主动讲 Free-Code Lab。若后续要继续清理，应单独评估 `free_code_lab.py`、`agent lab-generate`、`harvest-report`、相关测试和 Web Demo legacy summary 是否可以分阶段删除。
