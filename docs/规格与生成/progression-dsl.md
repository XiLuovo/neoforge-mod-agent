# Progression / Gameplay Loop DSL

> RC1 定位：Progression DSL 是玩法路线的报告和审计输入层。

## 作用

Progression 把零散 item、block、ore、machine、entity、structure 等 feature 组织成玩家可理解的路线。

## 示例

```json
{
  "type": "progression",
  "id": "ruby_progression",
  "title": "Ruby Progression",
  "entry_stage": "mine_ruby_ore",
  "end_stage": "craft_ruby_tool",
  "stages": [
    {
      "id": "mine_ruby_ore",
      "type": "ore",
      "title": "Mine Ruby Ore",
      "provides": ["raw_ruby"],
      "evidence": ["ruby_ore"]
    }
  ],
  "links": [
    {
      "from": "mine_ruby_ore",
      "to": "craft_ruby_tool",
      "trigger": "recipe",
      "requirement": "Use ruby in a crafting recipe"
    }
  ]
}
```

## Evidence

```text
.agent/progression-report.json
.agent/progression-report.md
```

## 边界

- 不生成复杂任务运行时。
- 不自动平衡游戏经济。
- 不替代 Minecraft runtime playtest。
