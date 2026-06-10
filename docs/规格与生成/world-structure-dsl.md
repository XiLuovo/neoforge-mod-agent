# World / Structure DSL

> RC1 定位：World / Structure DSL 是数据驱动世界内容的输入层。

## Feature Families

- `dimension`
- `biome`
- `world_feature`
- `structure`
- `loot_pool`

## 示例

```json
{
  "type": "world_feature",
  "id": "ruby_ore_vein",
  "feature_kind": "ore_vein",
  "target_block": "minecraft:stone",
  "ore_block": "ruby_ore",
  "min_y": -64,
  "max_y": 32,
  "vein_size": 6,
  "veins_per_chunk": 4
}
```

## 生成内容

- configured feature；
- placed feature；
- biome modifier；
- loot table；
- structure metadata where supported；
- `.agent` reports。

## 边界

- 当前世界生成仍是模板化数据包生成。
- 不证明游戏内分布平衡或结构体验。
- Minecraft runtime 验收仍需人工或未来 harness。
