# Machine DSL

> RC1 定位：Machine DSL 是 deterministic generator 的输入规格，用于生成受控机器方块模板。

## 作用

Machine DSL 描述带 BlockEntity、Menu、Screen、进度和能量字段的机器方块。它让常见机器玩法进入 `ModSpec`，避免 LLM 手写 Java。

## 示例

```json
{
  "type": "machine",
  "id": "ruby_compressor",
  "display_name_en_us": "Ruby Compressor",
  "machine_kind": "compressor",
  "inventory_slots": 2,
  "input_slots": 1,
  "output_slots": 1,
  "energy_capacity": 10000,
  "energy_per_tick": 20,
  "max_progress": 100,
  "menu_title": "Ruby Compressor"
}
```

## 生成内容

- machine block；
- block entity；
- menu / container；
- client screen；
- blockstate / model / loot table；
- language keys；
- `.agent` generation summary 和 audit report。

## 边界

- 只支持模板化机器。
- 不支持任意 GUI、复杂能量网络、多方块结构或手写 Java。
- 复杂行为应先进入 structured spec 或由 RC1 tool loop 通过受控 patch 修复已有 workspace。
