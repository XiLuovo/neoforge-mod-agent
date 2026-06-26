# Tool-Calling Contract

> 这是 RC1 tool-calling loop 的契约说明。项目不是完整 MCP server，也不是通用无限制 coding agent；这里的 tool call 是内部受控 JSON action，由 runtime 执行并写入 `.agent/tool-call-trace.json`。

## Loop 输入

每轮 LLM 至少能看到：

- user goal
- intent contract / `ModSpec`
- 当前 mode：`develop` 或 `repair`
- audit/build observation
- reviewer observation
- RAG snippets / citations
- 已读文件摘要
- 上一轮 tool observation

## 允许工具

| Tool | 作用 | 写文件 |
| --- | --- | --- |
| `retrieve_rag` | 从本地 NeoForge RAG 取相关知识。 | 否 |
| `read_file` | 读取 generated workspace 内的指定文件。 | 否 |
| `search_files` | 在 generated workspace 内搜索文件名或文本。 | 否 |
| `apply_structured_patch` | 应用受控 patch plan。 | 是 |
| `run_audit` | 执行 deterministic audit 并返回 observation。 | 只写报告 |
| `run_build` | 执行 build gate 并返回 observation。 | 只写报告/构建输出 |
| `finish` | 结束 loop，给出 reason 和 summary。 | 否 |

## Patch 契约

`apply_structured_patch` 只接受结构化计划，不接受自由 diff。典型 action 包含：

```json
{
  "tool": "apply_structured_patch",
  "arguments": {
    "reason": "Fix invalid pack metadata.",
    "operations": [
      {
        "op": "replace_text",
        "path": "pack.mcmeta",
        "old": "old text",
        "new": "new text"
      }
    ]
  }
}
```

受控 patch 必须满足：

- path 解析后仍在 generated workspace 内；
- 不能写 `.git`、build output、Gradle wrapper binary、工作区外文件；
- patch 前写入 `.agent/structured-patch-snapshots/`；
- patch 后写入 `structured-patch-plan.json`、`structured-patch-diff.md`、`structured-patch-report.json`；
- rollback 信息写入 `structured-patch-rollback-report.json`。

## Trace 契约

`.agent/tool-call-trace.json` 必须来自真实 LLM action，而不是从 agent step 派生。每条 trace 至少应能说明：

- iteration
- source
- requested tool
- arguments summary
- execution status
- observation summary
- artifact paths

`agent-run.json` 的 payload 会链接 tool trace、reviewer report、audit/build 结果和 repair/patch evidence。

## Reviewer 关系

LLM reviewer 输出 `coverage_status`、`patch_risks`、`recommended_checks` 和 `decision`。当 reviewer 返回 `needs_repair` 时，它的 observation 会进入下一轮 tool-calling context。reviewer 不能替代 audit/build gate。

## 与 MCP / Function Calling 的关系

RC1 已经实现真实工具选择和 observation loop，但没有宣称实现 MCP server。更准确的表述是：项目具备可包装为 Function Calling 或 MCP tools 的内部 tool schema、trace 和安全边界。
