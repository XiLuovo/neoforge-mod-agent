# Entity DSL

> RC1 定位：Entity DSL 是 `ModSpec` 的实体输入层，用于生成基础自定义实体模板，不是复杂 AI 或动画系统。

## 示例

```json
{
  "type": "entity",
  "id": "ruby_guard",
  "display_name_en_us": "Ruby Guard",
  "entity_kind": "npc",
  "category": "creature",
  "width": 0.6,
  "height": 1.8,
  "attributes": {
    "max_health": 24,
    "movement_speed": 0.25,
    "attack_damage": 3
  },
  "spawn": {
    "enabled": true,
    "biomes": "#minecraft:is_overworld",
    "weight": 40,
    "min_count": 1,
    "max_count": 2
  }
}
```

## 生成内容

- `EntityType` 注册；
- entity Java class；
- attribute registration；
- client renderer registration；
- texture placeholder；
- loot table；
- optional biome modifier。

## 支持范围

- simple creature / npc / ambient / monster template；
- basic melee or none attack；
- simple spawn rules；
- basic loot entries。

## 边界

- 不支持复杂动画、交易系统、复杂 AI、阶段式 boss、远程弹射物或任意 Java。
- 复杂实体需求应作为 unsupported/risky request 进入 reviewer 或后续规格扩展。
