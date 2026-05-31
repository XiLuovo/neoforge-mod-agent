# V7.1 Recipe / Loot / Balance Planner

> 文档定位：这是 balance planner 专项材料，不是主学习入口。需要理解 progression / quest / balance 如何组织玩法时再读。

V7.1 的目标是把 V7 的玩法线再往前推一步：不只说明玩家从哪里走到哪里，还给这条路线补一层可审计的经济系统规划。

它仍然遵守项目边界：LLM / rules 只输出结构化 `ModSpec`，确定性生成器输出 Java、JSON、PNG 和 `.agent` 证据文件。V7.1 不生成任意 Java patch。

这句话描述的是 V7.1 balance planner 这个功能层的稳定路径边界，不否定 V8.4+ 的 `ModSpec-first hybrid` 架构。当前全局边界以 [project-limitations.md](project-limitations.md)、[direct-code-lane.md](direct-code-lane.md) 和 [agent-workflow.md](agent-workflow.md) 为准：当 `ModSpec` 表达不足时，Direct Code Lane 可以产出结构化补丁，并强制 review、snapshot、audit/build 和 rollback evidence。

## 能表达什么

`balance_plan` 会基于已有 `progression`、配方、机器、实体掉落和 loot pool 生成规划报告：

```text
配方缺口
物品稀有度
实体掉落概率
机器 max_progress / energy_per_tick / total_energy
chest loot 权重和概率
```

## ModSpec 写法

```json
{
  "type": "balance_plan",
  "id": "ruby_balance_plan",
  "title": "Ruby Economy Balance Plan",
  "target_progression": "ruby_progression",
  "profile": "standard",
  "summary": "Plan missing recipes, rarity, drop chances, machine timing, energy cost, and chest loot weights."
}
```

字段说明：

- `target_progression` 指向已有 `progression` id。
- `profile` 支持 `easy`、`standard`、`expert`，影响机器耗时和能量建议。
- 输出是报告和建议，不会直接 patch 任意 Java。

## 输出证据

生成时会写入：

```text
.agent/balance-report.json
.agent/balance-report.md
```

报告包含：

- `recipes`：已有配方的产物数量、复杂度和稀有度建议。
- `missing_recipes`：机器、装备等缺失配方的补全建议。
- `rarities`：基于玩法阶段和 feature 类型推断的稀有度。
- `machines`：机器耗时、能量/tick、总能耗建议。
- `entity_drops`：实体掉落概率建议。
- `loot_weights`：chest loot 权重和概率建议。
- `economy_summary`：来源、消耗点和瓶颈物品摘要。

## 快速验证

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m agent.cli generate-from-spec .\examples\balance_gameplay_loop.json --workspace-name demo-balance --overwrite --audit --no-build --json
```

关键产物：

```text
workspace/demo-balance/.agent/balance-report.json
workspace/demo-balance/.agent/balance-report.md
workspace/demo-balance/.agent/audit-report.json
workspace/demo-balance/.agent/generation-summary.json
```

## 边界

- V7.1 是经济规划报告，不是自动调参到完美平衡的游戏测试器。
- 它不会改写任意 Java，也不会生成复杂任务系统、市场系统或动态难度系统。
- 报告里的建议可作为后续自动应用 patch 的输入，但当前验收目标是可审计、可解释、可回放。
