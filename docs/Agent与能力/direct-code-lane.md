# Direct Code Lane

> RC1 定位：Direct Code Lane 是辅助/兼容能力，用来解释受控 workspace patch 的早期形态。当前推荐主线是 `agent develop` / `agent repair` 的真实 tool-calling loop。

## 它现在是什么

Direct Code Lane 不是通用代码编辑器。它只允许结构化 workspace patch，并且必须经过：

- path allowlist；
- review；
- snapshot；
- diff/report；
- audit/build gate；
- rollback evidence。

这套思想已经进入 RC1 的 `apply_structured_patch` tool：LLM 不写自由 diff，而是提交受控 JSON action，由 runtime 执行。

## 和 RC1 Tool Loop 的关系

```text
Direct Code Lane idea
-> structured patch contract
-> snapshot / rollback evidence
-> RC1 apply_structured_patch tool
```

项目讲解时可以说明：Direct Code Lane 是项目演进过程中把“LLM 不能自由写代码”落实到工程边界的早期实验；RC1 已经把这个边界放入 develop/repair 的真实 tool-calling loop。

## 不要误解

- 不把它说成当前主线。
- 不把它说成 MCP。
- 不说它能修改本工具项目源码。
- 不说它能绕过 audit/build。

当前主线见 [agent-workflow.md](agent-workflow.md) 和 [tool-calling-contract.md](tool-calling-contract.md)。
