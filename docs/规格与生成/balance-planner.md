# Recipe / Loot / Balance Planner

> RC1 定位：Balance Planner 是报告型输入层，用于审查配方、掉落、机器成本和 progression 的经济关系。

## 示例

```json
{
  "type": "balance_plan",
  "id": "ruby_balance_plan",
  "title": "Ruby Economy Balance Plan",
  "target_progression": "ruby_progression",
  "profile": "standard",
  "summary": "Check recipes, drop rates, loot weights and machine timing."
}
```

## 输出

```text
.agent/balance-report.json
.agent/balance-report.md
```

## 检查内容

- missing recipe suggestions；
- rarity assignments；
- machine timing / energy guidance；
- entity drop guidance；
- loot weight guidance；
- progression coverage。

## 边界

- 它是 planner/report，不是自动游戏平衡器。
- 不替代 runtime playtest。
- reviewer 可以引用这些报告提出 recommended checks。
