# Trace-Backed Agent Benchmark

`agent bench` 用真实 agent 流程生成 benchmark evidence：develop / repair case 会经过 planner、ModSpec、deterministic generator、tool-calling loop、reviewer、audit/build gate 和 `.agent` trace。它不是静态拼报告。

## 证据口径

Benchmark 报告中的 `success_rate`、`audit_success_rate`、`repair_success_rate` 和 `build_success_rate` 都是 workspace 级证据。它们来自 planner/generator trace、reviewer 输出、structured patch 结果、audit 报告，以及可选的 Gradle build 结果。

Mock provider 成功只能说明离线可复现流程通过。真实 provider 成功必须以实际 provider run 和 `--require-real` / `--require-llm` evidence 为准。除非报告显式列出人工 Minecraft runtime evidence，否则 benchmark 不能写成客户端或服务端进游戏验收通过。

## Command

Fast local smoke:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

RAG ablation smoke:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench `
  --suite examples/agentic_rag_ablation.json `
  --llm-provider mock `
  --rag-ablation `
  --audit `
  --no-build `
  --json
```

18-case repair suite:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench `
  --suite examples/agent_benchmark_repair_18.json `
  --llm-provider mock `
  --rag-ablation `
  --audit `
  --no-build `
  --json
```

Real provider acceptance, only when provider config is ready:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench `
  --suite examples/agent_benchmark_repair_18.json `
  --llm-provider openai-compatible `
  --run-real `
  --require-real `
  --rag-ablation `
  --audit `
  --no-build `
  --json
```

## What It Runs

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

Repair cases should include failures that cannot be fixed by managed-file regeneration alone. This proves the structured patch loop actually participates in repair.

## Metrics

Key metrics:

- `success_rate`
- `audit_success_rate`
- `build_success_rate`
- `repair_success_rate`
- `audit_detection_rate`
- `expected_failure_detection_rate`
- `avg_tool_calls`
- `avg_iterations`
- `rag_hit_rate`
- `rag_citation_coverage_rate`
- `patch_accept_rate`
- `rollback_count`
- `failed_cases`
- `trace_paths`
- `evidence_scope`

Repair cases also record injected failure evidence:

- `breakage`
- `category`
- `injected_paths`
- `initial_audit_issue_ids`
- `detected_expected_failure`

## Outputs

```text
workspace/benchmark-runs/<run-id>/.agent/agent-benchmark-report.json
workspace/benchmark-runs/<run-id>/.agent/agent-benchmark-report.md
workspace/benchmark-runs/<run-id>/.agent/agent-benchmark-report.html
```

Each benchmark case keeps its own workspace `.agent` evidence, including agent run payload, tool-call trace, reviewer report, RAG decision trace, patch report, audit report, and rollback evidence when applicable.

## RAG Ablation

`--rag-ablation` expands each repair case into paired `rag_on` and `rag_off` runs. RAG-off still records skipped decisions, so the report can compare behavior and evidence. RAG-on is the primary path; RAG-off is a control group and may succeed or fail depending on the case.

Do not describe managed-file regeneration success as RAG success. RAG is context and citation evidence, not the main correctness gate.

## Holdout Suite

`--repair-holdout` generates deterministic randomized repair cases from the same breakage registry. It changes materials, mod ids, and resource names according to `--holdout-seed`, so it helps guard against overfitting to the fixed public suite.

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench `
  --repair-holdout `
  --holdout-seed demo `
  --holdout-limit 8 `
  --llm-provider mock `
  --rag-ablation `
  --audit `
  --no-build `
  --json
```

## Boundary

Benchmark does not bypass audit/build gates, and reviewer output cannot override failed deterministic checks. It measures the current controlled agent flow on a regression suite. It does not replace manual Minecraft runtime validation.

For in-game evidence, use [runtime-manual-validation.md](runtime-manual-validation.md) and record the result separately.
