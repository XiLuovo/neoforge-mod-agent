# V1.2 Evaluation And Benchmark

> 文档定位：这是 eval / benchmark 专项材料，不是主学习入口。需要理解评测 case、指标和报告时再读。

## V3.9 Real LLM Eval Report

V3.9 新增 `llm-eval-report`，把真实 LLM 的效果纳入可重复评测。它不是替代 `eval` 或 `eval-compare`，而是把它们串成一个更适合真实模型对比的工作流：

```text
mock baseline eval
  -> candidate eval
  -> eval-compare
  -> llm-eval-report
```

离线 smoke：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli llm-eval-report --candidate-provider mock --limit 2 --run-name v39-llm-eval-mock --json
```

真实 LLM 对比：

```powershell
$env:NEOFORGE_AGENT_LLM_BASE_URL = "https://api.openai.com/v1"
$env:NEOFORGE_AGENT_LLM_API_KEY = "<your-api-key>"
$env:NEOFORGE_AGENT_LLM_MODEL = "<your-model>"
py -3.11 -m agent.cli llm-eval-report --candidate-provider openai-compatible --limit 3 --run-name v39-real-llm-eval --json
```

输出：

```text
workspace/llm-eval-runs/<run-id>/.agent/llm-eval-report.json
workspace/llm-eval-runs/<run-id>/.agent/llm-eval-report.md
```

如果真实 provider 未配置，默认会安全跳过 candidate eval 并记录 provider preflight；如果希望 CI 或手动评测强制要求真实模型，使用 `--require-real`。

## V2.3 Eval Compare

V2.3 adds a deterministic `eval-compare` command. It compares two eval reports and fails when monitored benchmark rates or case outcomes regress.

Typical workflow:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --run-name v23-baseline --json
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --run-name v23-candidate --json
py -3.11 -m agent.cli eval-compare v23-baseline v23-candidate --run-name v23-compare --json
```

You can pass either eval run names or direct report paths:

```powershell
py -3.11 -m agent.cli eval-compare workspace\eval-runs\v23-baseline\.agent\eval-report.json workspace\eval-runs\v23-candidate\.agent\eval-report.json --json
```

The comparison report is written to:

```text
workspace/eval-comparisons/<run-id>/.agent/eval-compare-report.json
workspace/eval-comparisons/<run-id>/.agent/eval-compare-report.md
```

Monitored rates include `success_rate`, feature/category expectation rates, planner/audit/build rates, agent trace artifact rates, and repeat modify success rate.

中文说明：V2.3 的重点是“防退步”。V2.2 让单次 eval 更丰富，V2.3 则可以比较 baseline 和 candidate。如果 candidate 的成功率、能力覆盖率、trace 完整率或 modify 幂等性低于 baseline，命令会返回失败，方便在后续升级前做回归门禁。

V1.2 adds a deterministic evaluation runner for the Agent workflow. The goal is to move beyond single smoke tests and make the project measurable: given a fixed suite of prompts, the system can report planning success, audit success, build success, and whether the expected features appeared in the final `ModSpec`.

## Why This Exists

The project already has `generate`, `modify`, `audit`, `build`, `repair`, and V1.1 agent orchestration. The next reliability layer is benchmark evaluation:

```text
eval cases
  -> agent generate / agent modify
  -> expected feature checks
  -> audit/build metrics
  -> eval-report.json / eval-report.md
```

This keeps the same safety principle:

```text
LLM / rules -> ModSpec -> deterministic Java/JSON generation -> audit/build/repair
```

The evaluator does not let the LLM write Java, Gradle, or resource JSON.

## Quick Start

All commands assume:

```powershell
Set-Location L:\projects\MinecraftMods\idea
$env:PYTHONPATH = (Resolve-Path .\src)
```

Run the default offline benchmark suite:

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --json
```

Run a smaller smoke subset:

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --limit 2 --run-name v12-smoke --json
```

Run eval with Gradle builds enabled:

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --build --json
```

Build-enabled eval is slower, but it produces a stronger signal.

## Default Cases

The built-in suite covers:

- basic ruby item generation
- ruby charm behavior item
- speed crystal right-click effect
- ruby apple food effect
- ruby ore worldgen
- modify an existing ruby ore workspace to add worldgen

The default provider is intended to be `mock` for repeatable offline testing.

## Custom Cases

You can provide a JSON file with either a top-level array or an object containing `cases`.

```json
{
  "cases": [
    {
      "id": "custom_ruby_charm",
      "mode": "generate",
      "request": "Create a ruby mod with a ruby charm item.",
      "expected_features": ["ruby_charm"]
    },
    {
      "id": "custom_modify_worldgen",
      "mode": "modify",
      "setup_request": "Create a ruby mod with ruby and ruby ore.",
      "request": "Make ruby ore generate underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk.",
      "expected_features": ["ruby_ore"]
    }
  ]
}
```

Run custom cases:

```powershell
py -3.11 -m agent.cli eval --cases examples\my_eval_cases.json --planner llm --llm-provider mock --no-build --json
```

## Case Fields

- `id`: stable case identifier used in workspace names and reports.
- `mode`: `generate` or `modify`.
- `request`: natural language request.
- `setup_request`: required only for `modify`; creates the base workspace before modification.
- `expected_features`: feature ids that must appear in the final `.agent/modspec.json`.

## Output Artifacts

Each run creates:

```text
workspace/eval-runs/<run-id>/.agent/eval-cases.json
workspace/eval-runs/<run-id>/.agent/eval-report.json
workspace/eval-runs/<run-id>/.agent/eval-report.md
```

Generated case workspaces are placed under:

```text
workspace/eval-runs/<run-id>/<case-number>-<case-id>
```

Modify cases create a setup workspace first:

```text
workspace/eval-runs/<run-id>/<case-number>-<case-id>-base
```

## Metrics

`eval-report.json` includes:

- `total_cases`
- `success_count`
- `success_rate`
- `feature_expectation_success_rate`
- `expected_feature_match_rate`
- `planning_success_rate`
- `audit_success_rate`
- `build_success_rate`
- `generated_files_total`
- `average_generated_files`
- `modify_added_total`
- `modify_updated_total`
- `modify_skipped_total`

## 中文说明

V1.2 的核心目标是让项目具备“可评测性”。以前我们能证明某一个命令可以跑通；现在可以批量跑一组固定 prompt，并输出结构化指标。

这对简历项目很重要，因为它展示的不只是“我调用了 LLM”，而是：

- 我设计了受约束的 LLM Agent 工作流。
- 我用 `ModSpec` 作为中间表示，避免让模型直接写代码。
- 我有确定性的 generator、audit、build、repair。
- 我还能用 benchmark 量化系统表现。

推荐演示命令：

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --limit 2 --run-name v12-demo --json
```

如果要展示更强可靠性，可以开启 build：

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --build --run-name v12-build-demo --json
```

## V2.2 评测覆盖率增强

V2.2 在原有 eval 基础上增加了更适合长期回归和简历展示的覆盖指标：

- `expected_categories`：每个 case 可以声明期望覆盖的能力分类，例如 `item`、`food`、`sword`、`behavior`、`worldgen`、`right_click_heal`、`right_click_effect`、`food_effect`、`sword_ignite`、`modify`。
- `repeat_request`：modify case 可以要求重复执行同一条修改请求，用来检查增量修改是否幂等。
- agent trace artifact 检查：确认 `.agent/agent-run.json`、`.agent/agent-run.md`、`.agent/agent-decisions.md`、`.agent/prompt-trace.json` 是否真实存在。

新增聚合指标包括：

- `expected_category_match_rate`
- `category_expectation_success_rate`
- `agent_artifacts_complete_rate`
- `agent_trace_present_rate`
- `agent_decisions_present_rate`
- `prompt_trace_present_rate`
- `repeat_modify_success_rate`

推荐离线评测命令：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --run-name v22-eval --json
```

自定义 case 示例：

```json
{
  "id": "modify_add_behavior",
  "mode": "modify",
  "setup_request": "Create a ruby mod with ruby.",
  "request": "Add a ruby charm item that heals 4 health on right click with 20 seconds cooldown.",
  "expected_features": ["ruby_charm"],
  "expected_categories": ["item", "behavior", "right_click_heal", "modify"],
  "repeat_request": true
}
```
