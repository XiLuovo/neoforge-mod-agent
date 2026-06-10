# ModSpec Reference

> RC1 定位：`ModSpec` 是 `minecraft.neoforge` domain 的稳定规格输入层。它描述要生成的 Mod 内容；真正的 Java、JSON、PNG、resources 和 `.agent` evidence 由 deterministic generator 或受控 structured patch executor 产出。

## 在 RC1 主线中的位置

```text
Natural language
-> planner / intent contract
-> ModSpec
-> deterministic generator baseline
-> real tool-calling repair/refine loop
-> reviewer
-> audit/build gate
```

`ModSpec` 不是完整 agent loop 的全部，但它是 baseline generation 的真相源。

## Top-Level Fields

- `raw_request`: 原始用户目标。
- `domain`: 当前为 `minecraft.neoforge`。
- `domain_spec_type`: 当前为 `ModSpec`。
- `mod_id`: registry-safe id，例如 `ruby_mod`。
- `mod_name` / `display_name`: 人类可读名称。
- `package` / `package_name`: Java package，例如 `com.generated.ruby_mod`。
- `version`: Mod 版本。
- `description`: 描述。
- `authors`: 作者列表。
- `license_name`: license label。
- `loader`: 当前为 `neoforge`。
- `neo_version`: 当前目标 NeoForge 版本。
- `java_version`: 当前目标 Java 版本。
- `features`: 所有 typed feature 的规范化列表。

常见 type-specific arrays：

```text
items, blocks, machines, entities, dimensions, biomes,
world_features, structures, loot_pools, java_extensions,
ores, foods, swords, tools, armors, recipes,
progressions, balance_plans, quests
```

## Resource Rules

- feature id 使用 snake_case。
- local reference 可以写 `ruby`。
- namespaced reference 可以写 `ruby_mod:ruby` 或 `minecraft:speed`。
- recipe、drop、effect、progression evidence 应指向已生成 id 或有效外部 id。

## Feature Types

### Item

```json
{
  "type": "item",
  "id": "ruby",
  "display_name_en_us": "Ruby",
  "display_name_zh_cn": "红宝石"
}
```

### Block

```json
{
  "type": "block",
  "id": "ruby_block",
  "display_name_en_us": "Block of Ruby",
  "display_name_zh_cn": "红宝石块",
  "strength": 5.0,
  "resistance": 6.0,
  "sound": "metal",
  "requires_correct_tool": true,
  "tool_tier": "iron",
  "block_kind": "cube"
}
```

Supported `block_kind` includes `cube`, `stairs`, `slab`, `wall`, `button`, `pressure_plate`, `fence`, `fence_gate`, `door`, and `trapdoor`.

### Machine

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

Machine generation is template-based. It can generate BlockEntity/Menu/Screen scaffolding, but not arbitrary GUI logic or custom energy networks.

### Entity

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
  }
}
```

Entity generation is template-based. It supports registration, attributes, simple spawn/loot data and simple behavior templates; complex animation or advanced AI remains out of scope.

### Ore

```json
{
  "type": "ore",
  "id": "ruby_ore",
  "display_name_en_us": "Ruby Ore",
  "drop": "ruby_mod:ruby",
  "min_drop": 1,
  "max_drop": 1,
  "worldgen": {
    "enabled": true,
    "dimension": "minecraft:overworld",
    "min_y": -64,
    "max_y": 32,
    "vein_size": 6,
    "veins_per_chunk": 4
  }
}
```

### Food

```json
{
  "type": "food",
  "id": "ruby_apple",
  "display_name_en_us": "Ruby Apple",
  "nutrition": 6,
  "saturation": 0.8,
  "effects": [
    {
      "effect": "minecraft:regeneration",
      "duration_ticks": 100,
      "amplifier": 1,
      "probability": 1.0
    }
  ]
}
```

### Sword / Tool / Armor

```json
{
  "type": "sword",
  "id": "ruby_sword",
  "display_name_en_us": "Ruby Sword",
  "tool_material": "ruby",
  "attack_damage_bonus": 4,
  "attack_speed": -2.4,
  "on_hit": {
    "type": "ignite",
    "seconds": 5
  }
}
```

```json
{
  "type": "tool",
  "id": "ruby_pickaxe",
  "display_name_en_us": "Ruby Pickaxe",
  "tool_type": "pickaxe",
  "tool_material": "ruby"
}
```

```json
{
  "type": "armor",
  "id": "ruby_helmet",
  "display_name_en_us": "Ruby Helmet",
  "armor_type": "helmet",
  "armor_material": "ruby"
}
```

### Recipe

```json
{
  "type": "recipe",
  "id": "ruby_block",
  "recipe_type": "shaped",
  "pattern": ["RRR", "RRR", "RRR"],
  "keys": {
    "R": "ruby_mod:ruby"
  },
  "result": "ruby_mod:ruby_block",
  "count": 1,
  "category": "misc"
}
```

### Behavior

Behavior DSL can be embedded in supported hosts:

```json
{
  "behavior": {
    "type": "event_action",
    "events": [
      {
        "trigger": "right_click",
        "cooldown_ticks": 100,
        "actions": [
          { "type": "heal", "target": "self", "amount": 4 }
        ]
      }
    ]
  }
}
```

See [behavior-dsl.md](behavior-dsl.md).

### World / Structure

World content uses data-driven features such as:

- `dimension`
- `biome`
- `world_feature`
- `structure`
- `loot_pool`

See [world-structure-dsl.md](world-structure-dsl.md).

### Controlled Java Extension

`java_extension` is a narrow additive helper-class spec. It is not raw Java source.

```json
{
  "type": "java_extension",
  "id": "safe_info_extension",
  "class_name": "SafeInfoExtension",
  "allowed_imports": [
    "net.minecraft.network.chat.Component"
  ],
  "methods": [
    {
      "name": "describe",
      "return_type": "String",
      "return_value": "Controlled Java extension generated from ModSpec."
    }
  ]
}
```

See [controlled-java-extension.md](controlled-java-extension.md).

### Progression / Balance / Quest

These are report and guidance layers:

- `progression`: gameplay route and dependencies.
- `balance_plan`: recipe, loot, drop and machine-cost guidance.
- `quest`: advancement and guidebook data.

See [progression-dsl.md](progression-dsl.md), [balance-planner.md](balance-planner.md), and [quest-guide-dsl.md](quest-guide-dsl.md).

## Validator Rules

The validator checks:

- id and package shape；
- supported feature types；
- resource reference shape；
- recipe and drop references；
- behavior type and field ranges；
- food effect ranges；
- tool and armor type ranges；
- ore worldgen ranges；
- template-only world/entity/machine constraints；
- controlled Java extension allowlist；
- progression/balance/quest structural references。

## Evidence

Generated workspaces typically include:

```text
.agent/modspec.json
.agent/generation-summary.json
.agent/audit-report.json
.agent/prompt-trace.json
.agent/agent-run.json
```

RC1 repair/refine may add:

```text
.agent/tool-call-trace.json
.agent/reviewer-report.json
.agent/structured-patch-report.json
.agent/structured-patch-rollback-report.json
```

## Boundary

- `ModSpec` is not a free Java DSL.
- Unsupported requests should be surfaced to reviewer or handled by controlled structured patch in the tool loop.
- Passing `ModSpec` validation does not prove Minecraft runtime behavior.
- Final success still depends on audit/build gate.
