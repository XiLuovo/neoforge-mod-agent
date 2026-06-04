# Documentation Cleanup Todo

> 文档定位：这是文档历史债务和编码清洗待办，不是当前架构真相源。当前边界以 [project-limitations.md](../总览/project-limitations.md)、[direct-code-lane.md](../Agent与能力/direct-code-lane.md) 和 [agent-workflow.md](../Agent与能力/agent-workflow.md) 为准。

## Boundary Wording

- Keep historical version notes intact, but mark old statements such as "LLM only outputs ModSpec" or "LLM does not directly write Java" as historical boundary when they appear in V8.4-before context.
- Use the current boundary in current-facing docs: default to `ModSpec-first hybrid`; avoid naked LLM writes; allow structured Direct Code Patch only when `ModSpec` expression is insufficient.
- Mention the required evidence chain when Direct Code Lane is discussed: `review -> snapshot -> audit -> build -> rollback evidence`.

## Encoding Cleanup

- Run the focused mojibake scan from the implementation checklist before any cleanup. Keep the exact suspicious-character pattern in the checklist or shell history instead of duplicating it here, so this todo file does not match the scan by itself.

- If matches appear, inspect each file with UTF-8 decoding first and fix only confirmed mojibake.
- Keep encoding cleanup separate from architecture wording changes so review stays easy.

## Current Scan Result

- 2026-05-30: the planned mojibake scan returned no matches in `docs` or `README.md`.
