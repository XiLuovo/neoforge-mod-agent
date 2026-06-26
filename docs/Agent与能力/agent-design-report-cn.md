# Agent 设计报告

## 项目定位

RC1 的 NeoForge Mod Agent 是一个领域受控 Coding Agent。它把自然语言目标转成 `ModSpec`，生成 baseline workspace，再通过真实 tool-calling loop、RAG、structured patch、LLM reviewer、audit/build gate 和 benchmark evidence 完成闭环。

## 为什么不是普通生成器

普通 generator 的核心问题是：生成完就结束，失败时缺少可解释的 repair/refine 过程。RC1 把失败 observation、RAG、文件内容和 reviewer feedback 放回 LLM 下一轮，让模型选择受控工具继续修复。

## 为什么不让 LLM 自由写项目

NeoForge Mod 涉及 Java、JSON、resources、Gradle 和 registry 约束。自由 diff 容易越界、破坏 workspace 或制造不可回滚的状态。RC1 选择：

- `ModSpec-first`；
- deterministic generator；
- structured patch；
- path safety；
- snapshot / rollback evidence；
- audit/build gate。

## 关键模块

- `agent_orchestrator.py`：develop/repair/bench 的高层编排。
- `tool_calling_agent.py`：真实 tool-calling loop 和 structured patch executor。
- `llm_reviewer.py`：结构化 reviewer。
- `agent_runtime.py`：trace writer 和 evidence 汇总。
- `benchmark_report.py`：真实 agent benchmark。
- `llm_client.py`：mock / real provider 抽象。

## 设计取舍

项目牺牲了通用性，换来可控性：

- 只稳定支持 `minecraft.neoforge`。
- LLM 不能自由改仓库。
- reviewer 不决定最终成功。
- benchmark 使用小型真实链路 case，不声称覆盖全部 Mod 开发。

## 一句话

> RC1 的价值不是“模型会写更多代码”，而是“模型每一步都被工具契约、workspace 安全、reviewer、audit/build 和 evidence 链约束住”。
