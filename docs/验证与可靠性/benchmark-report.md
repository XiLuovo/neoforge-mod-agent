# Trace-Backed Agent Benchmark

> RC1 benchmark 的主线是 `agent bench`。旧静态聚合报告可作为兼容工具，但当前质量指标以真实 agent trace 为准。

## Command

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

## What It Runs

`agent bench` 会直接运行真实链路：

```text
develop / repair case
-> planner / ModSpec
-> deterministic generator baseline
-> tool-calling loop
-> RAG / read files / structured patch / audit
-> LLM reviewer
-> audit/build gate
-> trace-backed metrics
```

benchmark case 必须能覆盖仅靠 managed-file regeneration 修不好的失败样例，证明 structured patch loop 确实参与修复。

## Metrics

- `success_rate`
- `build_success_rate`
- `audit_success_rate`
- `repair_success_rate`
- `avg_tool_calls`
- `avg_iterations`
- `rag_hit_rate`
- `patch_accept_rate`
- `rollback_count`
- `failed_cases`
- `trace_paths`

这些指标来自 `.agent/tool-call-trace.json`、`reviewer-report.json`、`agent-run.json`、audit/build result 和 rollback evidence。

## Outputs

```text
workspace/agent-benchmark-runs/<run-id>/.agent/agent-benchmark-report.json
workspace/agent-benchmark-runs/<run-id>/.agent/agent-benchmark-report.md
workspace/agent-benchmark-runs/<run-id>/.agent/agent-benchmark-report.html
```

每个 benchmark case 也会保留自己的 workspace evidence，便于回放失败原因和 patch 过程。

## Boundary

benchmark 不绕过 audit/build gate，也不让 reviewer 覆盖失败结果。它衡量的是当前受控 agent 流程在小型回归集上的行为，不等于完整 Minecraft runtime 验收。
