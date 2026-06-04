# V4.1 Agent Run Replay / 历史运行回放

> 文档定位：这是 replay 机制专项材料，不是主学习入口。先看 [agent-workflow.md](../Agent与能力/agent-workflow.md)，需要理解历史 run 如何离线复盘时再读本文。

`replay` 用来把历史 `.agent/agent-run.json` 转成一份可阅读的回放报告。它适合两个场景：

- 面试展示：不用现场重跑复杂流程，也能讲清楚 Agent 每一步做了什么。
- 调试复盘：快速查看 planner、reviewer、executor、auditor、repair agent 的输入、输出、决策和 artifact。

## 命令

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli replay workspace/v41-replay-source --json
```

也可以直接传入文件：

```powershell
py -3.11 -m agent.cli replay workspace/v41-replay-source/.agent/agent-run.json --json
```

## 输入

`target` 支持三种形式：

- workspace 路径或 workspace 名称
- `.agent` 目录
- `agent-run.json` 文件路径

## 输出

```text
<workspace>/.agent/agent-run-replay.json
<workspace>/.agent/agent-run-replay.md
<workspace>/.agent/agent-run-replay.html
```

JSON 用于 dashboard 或后续自动分析，Markdown 用于人类阅读和面试讲解，HTML 是可直接打开的 session trace viewer。

注意：`replay` 输出里的 `success` 表示“回放报告是否生成成功”。原始历史运行是否成功会记录在 `metrics.original_run_success`。

## 回放内容

回放报告会整理：

- run metadata：mode、request、planner、provider、workspace
- role steps：每个 agent role 的状态、摘要、警告和错误
- decisions：每个角色的 decision、rationale、inputs、outputs
- prompt traces：planner 输入、provider、prompt kind、RAG 命中、JSON repair、retry
- LLM telemetry：provider metadata、model capability、streaming support、token usage、estimated cost
- artifacts：从历史 payload 中收集到的关键 path
- metrics：steps、decisions、prompt traces、RAG hits、used knowledge、JSON repair、retry、artifact 数量

## Trace Viewer

`agent-run-replay.html` 是一个静态页面，不需要启动服务。它把同一份 replay JSON 渲染成：

- 顶部 run metadata 和 metrics。
- 左侧 timeline 导航。
- 事件过滤按钮：按 `role_step`、`decision`、`prompt_trace`、`repair_rag`、`artifacts` 或 status 过滤。
- 每个 event 的 details、warning、error 和 artifact links。
- 内嵌 replay JSON，方便现场核对报告没有二次加工。

这让 `.agent/agent-run.json` 更像一次可回放 session，而不是单纯的日志文件。

## 安全边界

`replay` 是只读回放功能。它不会重新执行：

- LLM provider
- deterministic generator
- audit
- Gradle build
- repair loop

它只读取已经存在的 `.agent/agent-run.json`，并写出新的回放报告。

## 面试讲法

可以这样讲：

```text
我的 Agent 不是黑箱生成。每次运行都会保存 agent-run.json、prompt-trace.json、agent-decisions.md 和 audit/repair artifacts。
V4.1 的 replay 命令可以把这些历史记录整理成时间线，所以我可以复盘每个角色的输入、输出、决策理由和验证结果。
```

这能自然引出项目的核心设计：

- LLM 负责规划 `ModSpec`、Behavior DSL、受控扩展意图或 repair plan。
- generator 和受控扩展层确定性地产生 Java / JSON / PNG。
- auditor / builder / repair 负责验证和恢复。
- replay 负责把历史证据链变成可展示的故事。
