# Agent Run Replay

Replay 用于把 `.agent` evidence 还原成可讲解的执行过程。

## RC1 应回放什么

- planner / `ModSpec`；
- generated baseline；
- tool-calling iterations；
- RAG hits；
- file reads / searches；
- structured patch；
- audit/build observations；
- reviewer decision；
- final gate result。

## 核心文件

```text
.agent/agent-run.json
.agent/prompt-trace.json
.agent/tool-call-trace.json
.agent/rag-context.json
.agent/reviewer-report.json
.agent/audit-report.json
.agent/structured-patch-report.json
.agent/structured-patch-rollback-report.json
```

## 讲解方式

> Replay 的价值是证明 agent 不是一次性生成：每次工具选择、observation、reviewer 判断和 gate 结果都有 evidence，可以定位失败，也可以复盘为什么接受或拒绝一次修复。
