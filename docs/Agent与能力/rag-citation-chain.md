# RAG Citation Chain

RC1 要求 RAG 不只是“参与过”，还要能追踪使用了哪些知识。

## Citation Flow

```text
retrieve_rag action
-> snippets / citations
-> observation
-> next tool action or reviewer prompt
-> .agent/rag-context.json
-> .agent/tool-call-trace.json
```

## 看什么

- query；
- matched knowledge ids；
- category / capability；
- score；
- snippet summary；
- 哪个 iteration 使用了这些 citation。

## Demo

运行 `agent develop` 或 `agent repair` 后，检查：

```text
workspace/<name>/.agent/rag-context.json
workspace/<name>/.agent/tool-call-trace.json
```

## 讲解方式

> Citation chain 的价值是把 LLM 的依据从“看起来合理”变成“可以回放到具体知识条目和具体 tool iteration”。
