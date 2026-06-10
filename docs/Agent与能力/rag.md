# RAG

RC1 的 RAG 是本地 NeoForge 知识检索层。它服务 planner、develop/repair tool loop、reviewer 和 benchmark evidence，不是外部联网知识同步器。

## 在主线中的位置

```text
user goal / observation
-> retrieve_rag
-> snippets / citations
-> LLM tool action or reviewer decision
-> trace / rag-context evidence
```

## 用在哪里

- planner：辅助把自然语言目标收敛为 `ModSpec`。
- develop：baseline 之后根据 audit/build observation 补充上下文。
- repair：根据失败原因检索 NeoForge 规则和常见修复方向。
- reviewer：判断 unsupported request 和 recommended checks。
- benchmark：统计 `rag_hit_rate`。

## Evidence

常见输出：

```text
.agent/rag-context.json
.agent/repair-rag-context.json
.agent/prompt-trace.json
.agent/tool-call-trace.json
```

## 边界

- RAG 不替代 compiler、audit 或 reviewer。
- RAG 知识需要维护。
- RAG 命中只能说明“使用了哪些本地知识”，不能证明 Minecraft runtime 行为正确。

## 讲解方式

> RAG 不是为了装饰 prompt，而是为了让每次 planner、repair 和 reviewer 的依据能落到具体 citation，并写进 evidence。
