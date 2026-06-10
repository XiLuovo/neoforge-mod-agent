# Quest / Advancement / Guide DSL

> RC1 定位：Quest DSL 把 progression 转成玩家可见目标、advancement JSON 和 guidebook 文档。

## 示例

```json
{
  "type": "quest",
  "id": "ruby_questline",
  "title": "Ruby Questline",
  "summary": "Visible goals for the ruby progression.",
  "target_progression": "ruby_progression",
  "guidebook_id": "ruby_guidebook",
  "tasks": [
    {
      "id": "mine_ruby_ore",
      "title": "Mine Ruby Ore",
      "task_type": "mine_block",
      "target": "ruby_ore",
      "icon": "ruby_ore",
      "guide_text": "Start underground and mine ruby ore.",
      "reward_xp": 25
    }
  ]
}
```

## 生成内容

- advancement JSON；
- Markdown guidebook；
- Patchouli-style book/category/entry JSON；
- quest report。

## 边界

- 不实现完整任务运行时。
- 不保证游戏内 UX 已经足够好。
- 需要 runtime playtest 或未来 harness 验证。
