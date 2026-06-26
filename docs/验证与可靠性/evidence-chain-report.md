# Evidence Chain Report

`evidence-chain-report` 把项目的关键证据层汇总成一份可审计报告。它用于展示“系统如何生成、检查、暴露失败、恢复并记录证据”，不是 Minecraft runtime 自动验收。

## Command

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli evidence-chain-report --run-name local-evidence-chain --eval-limit 1 --repair-limit 1 --json
```

输出位置：

```text
workspace/evidence-chain-runs/<run-id>/.agent/evidence-chain-report.json
workspace/evidence-chain-runs/<run-id>/.agent/evidence-chain-report.md
```

## Layers

报告聚合三层 evidence：

- **Stable ModSpec Layer**：结构化内容生成、eval success rate、失败注入、repair recovery、生成文件数，以及已显式记录的 manual runtime matrix entries。
- **Behavior DSL Layer**：item / block / machine / entity / quest / progression 共用 Event-Condition-Action 语义后的生成、audit、失败样本和恢复样本。
- **Controlled Patch Agent Layer**：受控 modify / patch-agent 的 patch plan、managed-file boundary、audit/build gate、rollback evidence 和 repair-loop recovery。

## Metrics

顶层 metrics 包括：

- `acceptance_success_rate`
- `failure_samples_total`
- `recovery_rate`
- `generated_files_total`
- `runtime_validation_total`
- `runtime_validation_pass_rate`
- `evidence_scope`

每层还保留：

- `acceptance_samples`
- `failure_samples`
- `recovery_samples`
- `runtime_validation`
- `artifacts`
- `notes`

`runtime_validation` 是历史字段名。阅读时应理解为“本层 evidence details”，不自动等价于 Minecraft runtime 验收。

## Evidence Boundary

Evidence-chain success 聚合的是 workspace 级 audit/build gate、生成报告、repair evidence，以及已文档化的 manual runtime matrix entries。它不声称 Minecraft 客户端或服务端 runtime 通过，除非具体样本显式包含 manual runtime evidence。

具体边界：

- Stable layer 可以引用 manual Minecraft runtime matrix，但只统计已记录的 case。
- Behavior layer 的 manual test checklist 是待验收清单，不是已完成进游戏测试的证明。
- Patch-agent layer 的 build/audit/rollback/repair-loop evidence 证明 workspace gate 和恢复流程，不证明游戏内行为。

如果展示需要“进游戏检查过”的结论，应先按 [runtime-manual-validation.md](runtime-manual-validation.md) 记录人工 runtime evidence，再在报告或展示材料中引用。

## When To Use

适合用于：

- 展示项目不是只跑成功样例，也保留失败样本和恢复样本。
- 复盘 ModSpec、Behavior DSL、Patch Agent 三层能力的证据覆盖。
- 准备公开 demo 或说明材料时检查 evidence 是否和表述匹配。

不适合用于：

- 宣称所有 generated mod 都已经在 Minecraft 客户端/服务端验收。
- 替代 Gradle build、workspace audit、unit tests 或 manual runtime checklist。
- 包装没有跑过的 real provider 或 runtime evidence。
