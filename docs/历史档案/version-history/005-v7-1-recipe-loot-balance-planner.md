## V7.1 Recipe / Loot / Balance Planner

目标：让系统不只生成内容和玩法线，还能把配方、掉落、稀有度、机器耗时、能量消耗和战利品权重组织成一份可审计经济规划。

完成内容：

- package metadata 更新到 `7.1.0`。
- `ModSpec` 新增 `balance_plan` / `balance_plans`，可指向已有 `progression`。
- 新增 `BalancePlanGenerator`，输出 `.agent/balance-report.json` 和 `.agent/balance-report.md`。
- 报告覆盖已有配方建议、缺失配方建议、稀有度分配、机器 `max_progress` / `energy_per_tick` / `total_energy`、实体掉落概率、loot 权重和 economy summary。
- validator 检查 balance plan id、profile、目标 progression 引用，以及是否有可分析的经济对象。
- audit / generation-summary / capabilities / rules planner / mock LLM 均接入 V7.1。
- 新增示例 `examples/balance_gameplay_loop.json` 和文档 `docs/规格与生成/balance-planner.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_balance_planner tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\balance_gameplay_loop.json --workspace-name v71-balance-smoke --overwrite --audit --no-build --json
```

边界：

- V7.1 是 report-only 经济规划层，不直接改写任意 Java 或复杂玩法逻辑。
- 平衡建议可解释、可审计、可回放，但不能替代游戏内人工经济测试。
- 后续可以在受控 patch / apply 模式里把建议安全落回 `ModSpec`。
