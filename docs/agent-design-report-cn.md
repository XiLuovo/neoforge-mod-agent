# NeoForge Mod Agent 设计报告

> 文档定位：这是 Agent 设计取舍专项材料，不是主入口。先看 [architecture.md](architecture.md)、[agent-workflow.md](agent-workflow.md) 和 [project-limitations.md](project-limitations.md)，再用本文理解为什么采用受控 workflow，而不是开放式 ReAct。

## 结论

本项目更接近 `Plan-and-Execute + verification/reflection`，不是开放式 ReAct，也不是通用 Coding Agent。

核心取舍：LLM 负责规划，系统负责执行边界和验证。Planner 产出 `ModSpec` / DSL / patch plan / direct-code plan，Reviewer 做 schema 和安全检查，Executor 生成或应用受控补丁，Auditor / Builder 给出外部验证，Repair 根据失败证据做有限恢复。

## 为什么需要 Agent Runtime

直接 `prompt -> model -> final code` 有三个问题：

1. NeoForge Java、Gradle、JSON、resource 路径和注册逻辑容易错。
2. 失败后很难判断是规划错、生成错、资源错还是构建环境错。
3. 没有稳定证据链，无法 replay、eval、benchmark 或 repair。

所以项目拆成固定阶段：

```text
request
-> plan
-> review
-> execute
-> audit / build
-> repair when needed
-> trace / replay
```

## 为什么不是开放式 ReAct

ReAct 适合开放式搜索和工具探索。本项目的核心风险不是“不知道下一步调哪个工具”，而是“模型输出能不能安全转成可构建工程”。

因此 workflow 是固定的：模型不能无限行动，也不能随意改文件。失败恢复也由 audit/build 证据驱动，而不是让模型反复自我猜测。

## Agent 与 Domain Plugin

| 层 | 职责 | 当前状态 |
| --- | --- | --- |
| `AgentRuntime` | 通用阶段编排：plan/review/execute/audit/repair/trace | 已落地 |
| `NeoForgeRuntimePlugin` | 把 runtime 阶段映射到 NeoForge 生成、审计、修复 | 已落地 |
| `ModSpec` | 当前最稳定的 NeoForge domain spec | 已落地 |
| `spring.api` / `unity.component` | 跨领域扩展方向 | 规划/占位，不能夸成完成 |
| `FreeCodeLabRunner` | 隔离实验 generate gap，产出 harvest candidate | 已落地为实验通道 |

## 角色拆分

| 角色 | 输入 | 输出 | 主要证据 |
| --- | --- | --- | --- |
| Planner | 用户需求、RAG、provider 配置 | intent contract / `ModSpec` / direct-code plan | `.agent/prompt-trace.json` |
| Reviewer | planner 输出 | schema、validator、边界检查结果 | `.agent/agent-decisions.md`、`.agent/direct-code-review.json` |
| Executor | 已通过 review 的意图 | workspace 文件、summary、diff/report | `.agent/generation-summary.json`、`.agent/direct-code-report.json` |
| Auditor | workspace 与 `.agent/modspec.json` | audit errors/warnings | `.agent/audit-report.json` |
| Builder | workspace | Gradle build result | `.agent/agent-run.json` |
| Repair | audit/build 失败证据 | repair plan 与恢复结果 | `.agent/repair-loop-report.json` |
| Trace Writer | 全阶段状态 | 可回放证据 | `.agent/agent-run.json`、`.agent/agent-run-replay.html` |

## Reflection 在哪里

这里的 reflection 是工程化的 failure-driven recovery：

```text
audit/build failure
-> root cause classification
-> repair RAG context
-> repair plan
-> managed-file regeneration or rollback guidance
-> rerun verification
```

它不等于让模型自由反思并乱改代码。当前 repair 第一版保持保守：优先基于 `.agent/modspec.json` 和 managed files 恢复，Direct Code Lane 失败时给 rollback evidence。

## Direct Code Lane 和 Free-Code Lab 的位置

Direct Code Lane 是稳定 agent 路径里的“受控补丁通道”：当 ModSpec 表达不足时，允许在生成 workspace 内应用结构化 `write_file` / `replace_text` 计划，并强制 review、snapshot、audit/build 和 rollback evidence。详见 [direct-code-lane.md](direct-code-lane.md)。

Free-Code Lab 是实验通道：让 LLM 在隔离 workspace 中探索 generate 覆盖不了的需求，成功后产出 `harvest-candidate.json`，再人工整理成 ModSpec / DSL / generator / audit / tests。详见 [capability-harvest-loop.md](capability-harvest-loop.md)。

## 为什么不直接用 LangChain / AutoGen / CrewAI

这些框架适合通用 agent 编排，但本项目最重要的是领域文件边界、可审计 artifact、稳定测试和 replay。轻量自研 runtime 更容易把以下规则固化下来：

- 阶段固定，失败出口明确。
- 文件修改必须落在 workspace / managed files / allowlist 内。
- `.agent/*` 证据格式稳定。
- 离线 mock provider 可复现。
- 后续如果要接 Function Calling / MCP，可以基于 [tool-calling-contract.md](tool-calling-contract.md) 包装。

## 一分钟复述

> 这个项目的 Agent 不是开放式 ReAct，而是领域受控的 Plan-and-Execute workflow。LLM 只负责把自然语言规划成 `ModSpec`、DSL 或补丁计划；系统用 reviewer、deterministic generator、auditor、builder、repair-loop 和 replay trace 保证结果可验证、可恢复、可回放。V8.5 之后 Free-Code Lab 又把 generate gap 放进隔离实验区，成功样本再 harvest 回稳定 generator。

## 继续阅读

- 整体架构：[architecture.md](architecture.md)
- Agent 阶段真相源：[agent-workflow.md](agent-workflow.md)
- Direct Code Lane：[direct-code-lane.md](direct-code-lane.md)
- Capability Harvest Loop：[capability-harvest-loop.md](capability-harvest-loop.md)
- 工具契约：[tool-calling-contract.md](tool-calling-contract.md)
