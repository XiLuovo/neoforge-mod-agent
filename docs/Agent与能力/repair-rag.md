# Repair RAG

Repair RAG 是 RAG 在修复链路里的用法。RC1 中，它既可以作为 deterministic repair context，也可以由真实 tool-calling loop 通过 `retrieve_rag` 主动调用。

## 输入

- audit errors；
- build errors；
- reviewer observation；
- changed files summary；
- current user goal；
- ModSpec / intent contract。

## 输出

检索结果会写入：

```text
.agent/repair-rag-context.json
.agent/rag-context.json
.agent/tool-call-trace.json
```

## 在 Tool Loop 中

典型顺序：

```text
retrieve_rag
-> read_file
-> apply_structured_patch
-> run_audit
-> finish
```

RAG 只提供证据和方向；是否 patch、patch 哪里、是否继续 audit/build，都由 tool action 和 deterministic gate 决定。

## 边界

- 不联网。
- 不替代文件读取。
- 不直接修改 workspace。
- 不把 reviewer approve 当成功。
