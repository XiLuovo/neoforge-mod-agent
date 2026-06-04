## Current Architecture Summary

The project now supports:

- `generate`: natural language or spec to new workspace
- `modify`: natural language patch to existing workspace
- `audit`: deterministic workspace consistency check
- `build`: Gradle verification
- `repair`: build failure artifact generation
- `agent generate`: multi-role orchestration for new workspace generation
- `agent modify`: multi-role orchestration for existing workspace modification
- `eval`: benchmark evaluation for agent workflows
- `unittest`: fast automated regression checks
- `quality-gate`: one-command reliability gate
- GitHub Actions CI: automated quality gate for pushes and pull requests
- `doctor`: local environment diagnostics
- integrated doctor preflight inside `quality-gate`
- `showcase`: one-command portfolio demo report
- `capabilities`: structured capability matrix export

The main design principle is:

```text
LLM / natural language -> ModSpec -> deterministic Java/JSON generation -> audit/build/repair
```

This keeps LLM output constrained and makes generated projects easier to test, reproduce, and debug.

---

# 版本说明

本文档记录项目从最早的红宝石物品 Demo 到当前 V1.9 能力矩阵工作流的演进过程。
