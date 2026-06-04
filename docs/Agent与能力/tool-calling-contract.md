# Tool Calling Contract

> 文档定位：这是工具调用契约专项材料，不是主学习入口。它说明内部 tool manifest，不代表项目已经实现完整 MCP server。

## Direct Code Lane Update

`agent_generate` and `agent_modify` now expose `code_lane` in the tool manifest:

```text
hybrid  -> ModSpec first, optional Direct Code Lane
modspec -> previous ModSpec-only behavior
direct  -> baseline workspace plus reviewed Direct Code Patch
```

This does not turn the project into an open-ended tool-using coding agent. The model still produces structured intent. Direct Code Lane allows only JSON `write_file` / `replace_text` changes under approved generated-workspace roots, with review, snapshots, audit/build gates, and rollback evidence.

Current limitations and follow-up work are tracked in [project-limitations.md](../总览/project-limitations.md).

## Capability Harvest Loop Update

`tools-manifest` now also exposes the Capability Harvest Loop tools:

- `free_code_lab_generate`: maps to `agent lab-generate`; copies a generated workspace into an isolated lab run, applies structured experimental patches, and writes harvest evidence.
- `harvest_report`: maps to `harvest-report`; aggregates Free-Code Lab candidates and summarizes readiness, blockers, generate gaps, and harvest directions.

These tools are deliberately not a backdoor for free repo editing. Free-Code Lab acts only on copied generated workspaces under `workspace/free-code-lab-runs/<run-id>/workspace`, rejects unsafe paths and risky content, and never updates stable generator code automatically.

这份文档解释项目里的“工具调用”怎么讲。

结论先说清楚：当前项目没有实现完整 MCP server，也不是让 LLM 自由调用任意函数。它更像内部受控工具编排：`AgentRuntime` 固定阶段，planner 产出结构化意图，executor / auditor / repair / eval 这些工具由系统按边界调用。

新增的 `tools-manifest` 命令把这些内部能力导出成机器可读契约，方便后续包装成 Function Calling 或 MCP。

## 运行命令

```powershell
py -3.11 -m agent.cli tools-manifest --run-name local-tools --json
```

输出位置：

```text
workspace/tool-manifest-runs/<run-id>/.agent/tools-manifest.json
workspace/tool-manifest-runs/<run-id>/.agent/tools-manifest.md
```

## Manifest 里有什么

每个工具都会声明：

- `name`：工具名，例如 `agent_generate`、`audit_workspace`。
- `description`：这个工具解决什么工程问题。
- `cli_mapping`：对应现有 CLI 命令。
- `input_schema`：可包装成 Function Calling / MCP 的输入 schema。
- `output_artifacts`：运行后会留下哪些证据文件。
- `safety_boundaries`：安全边界，比如只能写 managed files、build 要显式开启。
- `side_effects`：是否会创建、修改或重生成文件。
- `maps_to`：未来可以映射到 Function Calling tool 还是 MCP tool/resource。

## 当前导出的核心工具

- `agent_generate`：从自然语言需求生成 NeoForge workspace，并保留 agent trace、prompt trace、audit / repair 证据。
- `agent_modify`：对已有 workspace 做受控修改，保留 patch plan、before/after ModSpec 和 rollback 报告。
- `free_code_lab_generate`：复制已有 generated workspace 到实验区，应用结构化实验补丁，并写出 `harvest-candidate.json`。
- `harvest_report`：汇总 Free-Code Lab 候选，帮助判断哪些样本保留、拒绝或后续固化。
- `audit_workspace`：对生成结果做确定性审计，只写报告，不修文件。
- `repair_loop`：基于 `.agent/modspec.json` 和 managed files 做安全修复。
- `rag_eval`：量化 RAG 召回质量，输出 Recall@K、MRR、category/capability hit。
- `evidence_chain_report`：聚合 Stable ModSpec、Behavior DSL、controlled patch-agent 三层证据。

## 和 Function Calling 的关系

Function Calling 的本质是：模型按 schema 选择函数和参数，外部系统执行函数，再把结果交回模型。

本项目现在没有把这些工具直接暴露给模型自由选择，而是先把工具 schema 标准化：

```text
internal CLI capability
  -> tools-manifest schema
  -> future Function Calling wrapper
```

这样做的好处是安全边界先清楚，再考虑协议包装。

## 和 MCP 的关系

MCP 更像一套把工具、资源、上下文开放给模型客户端的协议。这个项目目前没有 MCP server，所以简历和面试里不要说“实现了 MCP”。

更稳的说法是：

> 我先做了 tool manifest，把 generate、audit、repair、rag-eval、evidence-chain 这些内部能力整理成 schema、artifact 和安全边界。后续如果要接 MCP，可以把 manifest 中的工具包装成 MCP tools，把报告和 `.agent` 证据包装成 MCP resources。

## 为什么不直接做完整 MCP

因为当前项目的核心风险不是“怎么多接一个协议”，而是 NeoForge 代码生成是否可控：

- LLM 不能直接裸写任意 Java / JSON / Gradle 文件；Direct Code Lane 也只能输出结构化 workspace 补丁计划。
- 修改必须受 managed files、patch plan、direct-code review、audit/build/rollback gate 限制。
- repair 必须从 ModSpec 和受控生成器恢复，而不是让模型自由改文件。
- 面试最需要证明的是工程边界和证据链，而不是协议包装层。

所以 `tools-manifest` 是低成本但很有价值的一步：它证明你理解 tool schema、Function Calling 和 MCP 的关系，同时不夸大项目现状。

## 面试 30 秒说法

> 我这个项目没有硬蹭 MCP，而是先把内部工具能力标准化成 `tools-manifest`。里面每个工具都有 input schema、CLI 映射、输出证据、side effects 和安全边界。比如 `agent_generate` 会生成 workspace 并留下 agent trace，`audit_workspace` 只写审计报告，`repair_loop` 只能基于 ModSpec 重生成 managed files。这样后续可以自然包装成 Function Calling 或 MCP，但当前主线仍然是受控代码生成和验证闭环。
