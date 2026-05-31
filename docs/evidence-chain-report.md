# Evidence Chain Report

> 文档定位：这是 evidence chain 报告专项材料，不是主学习入口。需要把生成、修复、评测和 replay 证据串起来时再读。

`evidence-chain-report` 把项目最核心的三层能力汇总成一份可审计证据链：

- Stable ModSpec Layer：结构化内容生成、eval 成功率、失败注入、repair 恢复率、生成文件数、已记录的 Minecraft runtime 验证矩阵。
- Behavior DSL Layer：item / block / machine / entity / quest / progression 共享 Event-Condition-Action 语义后的生成、audit、失败样例和修复后样例。
- Controlled Patch Agent Layer：受控 modify / patch-agent 的 patch plan、managed-file 边界、audit/build gate、rollback 建议和 repair-loop 恢复样例。

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

## Metrics

报告顶层会给出：

- `acceptance_success_rate`：三层 acceptance 样本通过率。
- `failure_samples_total`：被刻意构造并成功识别的失败样例数量。
- `recovery_rate`：失败后通过 repair / 修正规格 / 受控恢复流程重新通过的比例。
- `generated_files_total`：所有 acceptance / recovery 过程中生成的工程文件数量。
- `runtime_validation_pass_rate`：runtime 相关证据通过率。

每一层还会保留自己的：

- `acceptance_samples`
- `failure_samples`
- `recovery_samples`
- `runtime_validation`
- `artifacts`

## Runtime Boundary

这里的 runtime 验证分两类：

- Stable ModSpec 层会读取 `docs/test-matrix.md` 里已经记录过的 Minecraft 手工 runtime 验证矩阵，并把 runtime pass rate 聚合进报告。
- Behavior DSL 和 patch-agent 层默认使用生成后的 `.agent/behavior-report.json`、manual test checklist、audit gate、build gate、rollback / repair-loop report 作为本轮自动证据。

因此这份报告能证明“系统知道如何生成、检查、暴露失败、恢复并记录产物”，但它不替代完整的人工进服测试。真正要证明 Minecraft registry/runtime 行为时，仍然要对选定 workspace 执行 build 后的游戏内验证，并把结果补进 `docs/test-matrix.md`。
