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

## RC2 RAG Ablation

RC2 adds an agent benchmark mode for measuring whether Agentic RAG actually changes repair outcomes.

Fast mock run:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench `
  --suite examples/agentic_rag_ablation.json `
  --llm-provider mock `
  --rag-ablation `
  --audit `
  --json
```

Real provider acceptance, when `NEOFORGE_AGENT_LLM_API_KEY` or `OPENAI_API_KEY` and a model are configured:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench `
  --suite examples/agentic_rag_ablation.json `
  --llm-provider openai-compatible `
  --run-real `
  --require-real `
  --rag-ablation `
  --audit `
  --json
```

`--rag-ablation` expands each repair case into paired `rag_on` and `rag_off` runs. RAG-off still records skipped decisions, so the report can compare both behavior and evidence.

Key metrics:

- `rag_on_success_rate`
- `rag_off_success_rate`
- `rag_on_audit_success_rate`
- `rag_off_audit_success_rate`
- `rag_on_avg_iterations`
- `rag_off_avg_iterations`
- `rag_on_avg_tool_calls`
- `rag_off_avg_tool_calls`
- `rag_success_delta`
- `rag_iteration_delta`
- `rag_tool_call_delta`
- `rag_citation_coverage_rate`

The default RC2 suite covers `neoforge.mods.toml`, `pack.mcmeta`, and recipe/resource-path repair cases. Each RAG-on repair should leave `tool-call-trace.json`, `reviewer-report.json`, and `rag-decision-trace.json` under the repaired workspace `.agent` directory.

### RC2 Acceptance Snapshot

Local validation completed for the RC2 branch:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
py -3.11 -m unittest discover tests
py -3.11 -m compileall src
git diff --check
```

Observed result:

```text
187 tests OK
compileall passed
diff --check passed with only LF/CRLF warnings on Windows
```

Real-provider smoke also passed with the configured OpenAI-compatible provider:

```text
provider = openai-compatible
model = deepseek-v4-flash
parsed_json = {"ok": true, "purpose": "rc2 real provider smoke"}
```

The latest complete real-provider ablation report is:

```text
workspace/benchmark-runs/rc2-real-ablation-accepted/.agent/agent-benchmark-report.json
```

Key metrics from that report:

```text
cases_total = 6
success_count = 6
success_rate = 1.0
audit_success_rate = 1.0
repair_success_rate = 1.0
rag_on_success_rate = 1.0
rag_off_success_rate = 1.0
rag_success_delta = 0.0
rag_citation_coverage_rate = 0.5833
failed_cases_count = 0
```

Real-provider caution: the configured provider can be slow on full paired ablation runs. If a full real run stalls, use the complete `rc2-real-ablation-accepted` evidence for release notes, then run a short real-provider smoke to confirm current credentials and endpoint health. Use mock ablation for repeatable RAG-on/RAG-off regression checks.

## Boundary

benchmark 不绕过 audit/build gate，也不让 reviewer 覆盖失败结果。它衡量的是当前受控 agent 流程在小型回归集上的行为，不等于完整 Minecraft runtime 验收。
