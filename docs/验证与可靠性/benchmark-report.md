# Trace-Backed Agent Benchmark

> 当前 benchmark 的主线是 `agent bench`。旧静态聚合报告可作为兼容工具，但当前质量指标以真实 agent trace 为准；RC2 增加 RAG on/off ablation，并把 repair benchmark 扩展为 18 个 audit 层真实故障类型。

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
- `audit_detection_rate`
- `expected_failure_detection_rate`
- `avg_tool_calls`
- `avg_iterations`
- `rag_hit_rate`
- `patch_accept_rate`
- `rollback_count`
- `cases_by_category`
- `failed_cases`
- `trace_paths`

这些指标来自 `.agent/tool-call-trace.json`、`reviewer-report.json`、`agent-run.json`、audit/build result 和 rollback evidence。

Repair case 还会记录注入和初始检测证据：

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

每个 benchmark case 也会保留自己的 workspace evidence，便于回放失败原因和 patch 过程。

## RAG Ablation Suites

`--rag-ablation` expands each repair case into paired `rag_on` and `rag_off` runs. RAG-off still records skipped decisions, so the report can compare both behavior and evidence. RAG-on 是主验收路径；RAG-off 是对照组，成功率可以在 0 到 1 之间，不作为硬失败条件。

### 3-Case Smoke

`examples/agentic_rag_ablation.json` 保留为快速 smoke suite，覆盖 `neoforge.mods.toml`、`pack.mcmeta` 和 recipe/resource-path repair。它适合本地频繁回归，确认 trace、reviewer、RAG decision 和 citation coverage 没退化。

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

### 18-Case Repair Suite

`examples/agent_benchmark_repair_18.json` 是严肃评测用的完整 repair suite，覆盖 18 个 audit 层故障：

- metadata：missing/corrupt `neoforge.mods.toml`、`pack.mcmeta`
- asset/resource：item definition/model/texture、blockstate、loot table、lang entry
- data/worldgen：recipe JSON/reference、ore configured feature/rule test/biome modifier
- generated code/domain artifacts：behavior item Java、machine block entity Java、entity spawn modifier

Mock full run:

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

Real provider full acceptance, when `NEOFORGE_AGENT_LLM_API_KEY` or `OPENAI_API_KEY` and a model are configured:

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

Full ablation produces 36 repair runs. It is slower and may incur provider cost; use the 3-case smoke for fast checks and the 18-case suite for acceptance evidence.

### Seeded Repair Holdout

`--repair-holdout` generates a deterministic randomized repair suite from the same breakage registry. It keeps the same failure types, but changes material/mod/resource names such as `sapphire_holdout`, `cobalt_block`, or `amber_ore` according to `--holdout-seed`. This is not a replacement for the fixed 18-case regression suite; it is a lightweight guard against tuning only for the public fixed cases.

Mock holdout run:

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

The same seed produces the same case list, which makes failures reproducible. Different seeds select different breakage/material combinations. `--holdout-limit 8 --rag-ablation` produces 16 paired repair runs; increase the limit when you need broader evidence and can afford the time/provider cost.

Key metrics:

- `audit_detection_rate`
- `expected_failure_detection_rate`
- `cases_by_category`
- `repair_holdout`
- `holdout_seed`
- `holdout_limit`
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
- `rag_on_expected_detection_rate`
- `rag_citation_coverage_rate`

Each RAG-on repair should leave `tool-call-trace.json`, `reviewer-report.json`, and `rag-decision-trace.json` under the repaired workspace `.agent` directory.

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
193 tests OK
compileall passed
diff --check passed with only LF/CRLF warnings on Windows
```

Real-provider smoke also passed with the configured OpenAI-compatible provider:

```text
provider = openai-compatible
model = deepseek-v4-flash
parsed_json = {"ok": true, "purpose": "rc2 real provider smoke"}
```

The latest complete 3-case real-provider ablation report is:

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

Real-provider caution: the configured provider can be slow on paired ablation runs, especially the 18-case suite. Use mock ablation for repeatable RAG-on/RAG-off regression checks; use real full acceptance when you need current provider evidence.

## Boundary

benchmark 不绕过 audit/build gate，也不让 reviewer 覆盖失败结果。它衡量的是当前受控 agent 流程在小型回归集上的行为，不等于完整 Minecraft runtime 验收。
