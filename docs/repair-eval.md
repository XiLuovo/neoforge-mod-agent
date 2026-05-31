# Repair Eval / 自修复能力量化报告

> 文档定位：这是 repair eval 专项材料，不是主学习入口。需要量化自修复成功率和失败类型时再读。

`repair-eval` 用来把自修复能力量化。它复用 Failure Lab 的故障注入样例，但输出更适合简历和面试讲述的指标报告。

## 运行命令

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli repair-eval --run-name v45-repair-eval --json
```

只评估单个故障：

```powershell
py -3.11 -m agent.cli repair-eval --case delete_texture --json
py -3.11 -m agent.cli repair-eval --case break_recipe_reference --json
```

## 统计指标

- `audit_detected_rate`：注入故障后 audit 是否发现预期问题。
- `repair_rag_relevant_rate`：Repair RAG 是否命中与故障类型相关的知识能力。
- `repair_loop_repaired_rate`：repair-loop 是否完成安全重生成。
- `audit_recovered_rate`：修复后 audit 是否恢复通过。
- `full_success_rate`：完整闭环成功率。
- `repair_rag_hits_count`：所有样例的 RAG 命中总数。

## 输出路径

```text
workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.json
workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.md
workspace/repair-eval-runs/<run-id>/runs/failure-lab-runs/failure-lab/.agent/failure-lab-report.json
```

每个 case 还会保留对应 workspace 下的：

```text
.agent/audit-report.json
.agent/repair-rag-context.json
.agent/repair-rag-context.md
.agent/repair-loop-report.json
.agent/repair-loop-report.md
```

## 面试叙事

可以这样讲：

```text
我不是只做了生成器 happy path。
我做了 Failure Lab 自动制造坏项目，
再用 Repair Eval 统计 audit 检出率、RAG 相关命中率、repair-loop 修复率和最终 audit 恢复率。
这样可以量化证明 Agent 的自修复链路是否真的有效。
```

## 边界

- 默认不依赖真实 LLM。
- 默认不跑 Gradle build；需要时可加 `--build`。
- Repair RAG 只提供证据，不直接改文件。
- repair-loop 只重生成 managed files。
