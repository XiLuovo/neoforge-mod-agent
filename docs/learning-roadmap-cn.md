# 从零学会这个项目的拆解路线

> 文档定位：这是旧版学习导航的瘦身版，保留作为补充材料。当前唯一主学习路线是 [project-learning-plan-cn.md](project-learning-plan-cn.md)；本文只告诉你“如果想再加深，按什么顺序补”。

## 先读哪一份

只想 7 天内学懂项目：读 [project-learning-plan-cn.md](project-learning-plan-cn.md)。

想查文档地图：读 [README.md](README.md)。

想补术语：读 [readme-glossary-cn.md](readme-glossary-cn.md)。

想看不足和边界：读 [project-limitations.md](project-limitations.md)。

## 学习主线

这条线不用背代码，目标是能讲清数据流：

```text
自然语言需求
-> ModSpec-first routing
-> deterministic generation / optional direct code patch
-> audit / build / repair
-> eval / replay / dashboard
-> Free-Code Lab sample
-> harvest into generator
```

## 五个阶段

### 阶段 1：跑通最小闭环

读：根 [../README.md](../README.md)、[project-learning-plan-cn.md](project-learning-plan-cn.md)。

跑：`doctor`、`agent generate --llm-provider mock --no-build`、`audit`。

看：`.agent/modspec.json`、`.agent/generation-summary.json`、`.agent/audit-report.json`、`.agent/agent-run.json`、`.agent/prompt-trace.json`。

你要能回答：一句自然语言如何变成一个 workspace？

### 阶段 2：理解规格和生成

读：[domain-spec.md](domain-spec.md)、[modspec.md](modspec.md)、[architecture.md](architecture.md)。

源码：`models.py`、`validator.py`、`project_generator.py`、`code_generator.py`、`asset_generator.py`、`worldgen_generator.py`。

你要能回答：为什么 `ModSpec` 是真相源？为什么 Java / JSON / PNG 不是 LLM 随机写出来的？

### 阶段 3：理解验证和修复

读：[testing.md](testing.md)、[failure-repair-demo.md](failure-repair-demo.md)、[project-limitations.md](project-limitations.md)。

源码：`auditor.py`、`builder.py`、`repair_loop.py`、`repair.py`。

你要能回答：audit 能发现什么？build 能保证什么？repair 什么时候不能修？

### 阶段 4：理解 Agent / LLM / RAG

读：[agent-workflow.md](agent-workflow.md)、[agent-design-report-cn.md](agent-design-report-cn.md)、[llm-engineering-report.md](llm-engineering-report.md)、[rag-indexing-strategy-cn.md](rag-indexing-strategy-cn.md)、[tool-calling-contract.md](tool-calling-contract.md)。

源码：`agent_runtime.py`、`agent_orchestrator.py`、`llm_client.py`、`knowledge_base.py`、`tool_manifest.py`。

你要能回答：planner、reviewer、executor、auditor、repair 各自负责什么？mock LLM 和 real LLM 分别证明什么？

### 阶段 5：理解 Direct Code Lane 和能力采集

读：[direct-code-lane.md](direct-code-lane.md)、[capability-harvest-loop.md](capability-harvest-loop.md)、[capabilities.md](capabilities.md)。

源码：`direct_code_agent.py`、`free_code_lab.py`，以及对应测试。

你要能回答：Direct Code Lane 为什么不是无边界 coding agent？Free-Code Lab 成功后为什么还要 harvest 回 generator？

## 源码阅读地图

按数据流读，不按文件名硬背：

| 数据流位置 | 解决什么问题 | 先看什么 |
| --- | --- | --- |
| CLI | 把命令参数变成一次生成、修改、审计或实验任务 | `agent/cli.py` |
| Agent Runtime | 固定 planner/reviewer/executor/auditor/repair 阶段 | `agent_runtime.py` |
| Planner / LLM | 把自然语言变成结构化意图 | `llm_client.py`、`planner.py` |
| ModSpec / Validator | 定义可稳定生成的真相源 | `models.py`、`validator.py` |
| Generator | 生成 Java、JSON、PNG、resources | `project_generator.py` |
| Direct Code Lane | 在受控边界内补 ModSpec 表达不足 | `direct_code_agent.py` |
| Auditor / Builder / Repair | 验证和有限恢复 | `auditor.py`、`builder.py`、`repair_loop.py` |
| Eval / Replay / Dashboard | 证明流程可复现、可比较、可回放 | `evaluator.py`、`replay.py`、`dashboard.py` |

## 最后自测

- `agent generate` 和 `generate-from-spec` 的差别是什么？
- `.agent/` 目录中哪些文件证明规划、生成、审计、修复发生过？
- 为什么 `build` 通过不等于 Minecraft runtime 一定通过？
- 如果 Direct Code Lane 失败，你先看哪三个报告？
- 如果一个 Free-Code Lab 样本人工测试成功，下一步怎样固化进稳定 generator？

## 不再重复的内容

本文不再展开面试话术、完整文档索引、Direct Code Lane 机制和 Capability Harvest Loop 机制。对应内容分别看：

- [interview-script.md](interview-script.md)
- [README.md](README.md)
- [direct-code-lane.md](direct-code-lane.md)
- [capability-harvest-loop.md](capability-harvest-loop.md)
