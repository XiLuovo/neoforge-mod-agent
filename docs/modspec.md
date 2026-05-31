# ModSpec Reference

> 文档定位：这是 NeoForge ModSpec 参考文档，不建议从头背。学习规格层先看 [project-learning-plan-cn.md](project-learning-plan-cn.md) Day 2，需要字段细节时查本文。

`ModSpec` is the source of truth for generated NeoForge workspaces. It is also the current stable `DomainSpec` implementation for the `minecraft.neoforge` domain: natural language requests and optional LLM planning both resolve into this structure before deterministic generation begins.

## Top-Level Fields

- `raw_request`: original natural language request or descriptive source text
- `domain`: currently `minecraft.neoforge`
- `domain_spec_type`: currently `ModSpec`
- `mod_id`: lowercase registry-safe mod id, for example `ruby_mod`
- `mod_name` / `display_name`: human-readable mod name
- `package` / `package_name`: Java package, for example `com.generated.ruby_mod`
- `version`: mod version string
- `description`: mod description
- `authors`: list of author names
- `license_name`: license label written into the workspace
- `loader`: currently `neoforge`
- `neo_version`: currently `26.1`
- `java_version`: currently `25`
- `features`: normalized list of all typed features

The spec also keeps type-specific arrays:

- `items`
- `blocks`
- `machines`
- `entities`
- `dimensions`
- `biomes`
- `world_features`
- `structures`
- `loot_pools`
- `java_extensions`
- `ores`
- `foods`
- `swords`
- `tools`
- `armors`
- `recipes`
- `progressions`
- `balance_plans`
- `quests`

## Resource Location Rules

- Feature ids use `^[a-z][a-z0-9_]*$`
- References may be local ids like `ruby`
- References may also be resource locations like `ruby_mod:ruby` or `minecraft:speed`
- Recipes, drops, and effects should point to known generated ids or valid external ids

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

Optional behavior:

```json
{
  "type": "item",
  "id": "ruby_charm",
  "display_name_en_us": "Ruby Charm",
  "display_name_zh_cn": "红宝石护符",
  "behavior": {
    "type": "right_click_heal",
    "amount": 4,
    "cooldown_ticks": 400,
    "consume": false
  }
}
```

Or:

```json
{
  "type": "item",
  "id": "speed_crystal",
  "display_name_en_us": "Speed Crystal",
  "display_name_zh_cn": "速度水晶",
  "behavior": {
    "type": "right_click_effect",
    "effect": "minecraft:speed",
    "duration_ticks": 200,
    "amplifier": 1,
    "cooldown_ticks": 200,
    "consume": false
  }
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

V2.8 开始，`block` 可以通过 `block_kind` 声明更多“可交互但不复杂”的方块变体：

- `cube`
- `stairs`
- `slab`
- `wall`
- `button`
- `pressure_plate`
- `fence`
- `fence_gate`
- `door`
- `trapdoor`

方块变体可以用 `base_block` 表达来源方块。生成器会确定性生成 Java 注册、blockstate、block model、item model、贴图、loot table、语言 key 和配方。

```json
{
  "type": "block",
  "id": "ruby_stairs",
  "display_name_en_us": "Ruby Stairs",
  "display_name_zh_cn": "红宝石楼梯",
  "strength": 5.0,
  "resistance": 6.0,
  "sound": "metal",
  "requires_correct_tool": true,
  "tool_tier": "iron",
  "block_kind": "stairs",
  "base_block": "ruby_block"
}
```

### Machine

V5.2 开始，`machine` 用于声明带 BlockEntity、容器、菜单和客户端 Screen 的机器方块。生成器会确定性生成：

- 机器 Block：右键打开菜单，服务端 ticker 驱动 BlockEntity。
- BlockEntity：保存 `SimpleContainer`、能量、进度，并通过 `ContainerData` 暴露同步字段。
- Menu / Screen：生成 `AbstractContainerMenu`、槽位布局、进度条、能量条和客户端 Screen 注册。
- 资源：blockstate、model、loot table、语言 key、mineable / tool tier 标签和机器贴图。

```json
{
  "type": "machine",
  "id": "ruby_compressor",
  "display_name_en_us": "Ruby Compressor",
  "display_name_zh_cn": "红宝石压缩机",
  "strength": 4.0,
  "resistance": 6.0,
  "sound": "metal",
  "requires_correct_tool": true,
  "tool_tier": "iron",
  "block_kind": "cube",
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

Supported `machine_kind` values:

- `furnace`
- `compressor`
- `upgrade_table`
- `magic_altar`
- `storage`

Machine GUI generation is template-based. It does not mean arbitrary GUI screens, custom energy networks, multi-block machines, or handwritten Java snippets are accepted in `ModSpec`.

### Entity / Mob

V5.3 开始，`entity` 用于声明基础自定义生物。生成器会确定性生成 `EntityType` 注册、实体 Java 类、属性注册、客户端 renderer 注册、实体贴图、语言 key、掉落表，以及可选的 NeoForge `add_spawns` biome modifier。

```json
{
  "type": "entity",
  "id": "ruby_goblin",
  "display_name_en_us": "Ruby Goblin",
  "display_name_zh_cn": "Ruby Goblin",
  "entity_kind": "monster",
  "category": "monster",
  "width": 0.6,
  "height": 1.35,
  "tracking_range": 10,
  "update_interval": 3,
  "xp_reward": 5,
  "attributes": {
    "max_health": 24,
    "movement_speed": 0.27,
    "attack_damage": 4,
    "armor": 2,
    "follow_range": 28,
    "knockback_resistance": 0
  },
  "drops": [
    { "item": "minecraft:emerald", "min_count": 1, "max_count": 2, "chance": 0.5 }
  ],
  "spawn": {
    "enabled": true,
    "biomes": "#minecraft:is_overworld",
    "weight": 80,
    "min_count": 1,
    "max_count": 3,
    "placement": "on_ground"
  },
  "goals": [
    { "type": "float", "priority": 0 },
    { "type": "melee_attack", "priority": 2, "speed": 1.1 },
    { "type": "target_player", "priority": 2 }
  ],
  "attack": { "type": "melee", "damage": 4, "speed": 1.1 }
}
```

Supported `entity_kind` values:

- `monster`
- `creature`
- `pet`
- `boss`
- `npc`
- `ambient`

Supported AI goal templates:

- `float`
- `melee_attack`
- `random_stroll`
- `look_at_player`
- `random_look_around`
- `hurt_by_target`
- `target_player`

Entity generation is template-based. It supports simple mobs, pets, bosses and NPC-style entities at the registration/attribute/loot/spawn/simple-AI level, but not complex animation, boss phases, remote projectiles, trading, taming, or arbitrary Java AI logic.

### World / Structure

V5.4 开始，世界玩法通过五类数据驱动 feature 表达：

- `dimension`: fixed-biome noise dimension 和 dimension type。
- `biome`: climate、precipitation、颜色效果和 feature slot scaffold。
- `world_feature`: 当前支持 `ore_vein`，生成 configured / placed feature 和 biome modifier。
- `structure`: 当前支持 jigsaw structure metadata、structure set 和 empty start template pool。
- `loot_pool`: 当前支持 chest loot table 的 rolls、weighted entries、count 和 chance。

完整示例见 [`examples/world_ruby_realm.json`](../examples/world_ruby_realm.json) 和 [`docs/world-structure-dsl.md`](world-structure-dsl.md)。

### Controlled Java Extension

V6.1 uses `java_extension` for narrow, additive Java helper classes. This is still a structured `ModSpec` feature, not raw Java source. The generator writes managed classes only under `<package>.extension` and writes `.agent/java-extension-report.*`, `.agent/java-extension-diff.md`, and `.agent/java-extension-rollback-report.*` for audit evidence.

```json
{
  "type": "java_extension",
  "id": "safe_info_extension",
  "display_name_en_us": "Safe Info Extension",
  "class_name": "SafeInfoExtension",
  "purpose": "Expose a tiny compile-time helper without editing existing generated sources.",
  "explanation": "The deterministic generator renders this as an additive managed class under the extension package.",
  "allowed_imports": [
    "net.minecraft.network.chat.Component"
  ],
  "methods": [
    {
      "name": "describe",
      "return_type": "String",
      "return_value": "Controlled Java extension generated from ModSpec.",
      "explanation": "Returns a short audit-friendly description."
    }
  ]
}
```

Rules:

- `class_name` must be PascalCase.
- method names must be lowerCamelCase.
- `return_type` is currently limited to `String`.
- `allowed_imports` may only contain the V6 allowlist: `BlockPos`, `Component`, or `ResourceLocation`.
- text fields and generated source are checked for file, network, process, reflection, thread, classloader, native, package/import injection, and other forbidden tokens.
- generated output is additive only; existing Java sources and Gradle files are not patched.
- formal acceptance requires audit plus Gradle build gate; build status is recorded in `.agent/java-extension-report.json`.

Full example: [`examples/controlled_java_extension.json`](../examples/controlled_java_extension.json). More detail: [`docs/controlled-java-extension.md`](controlled-java-extension.md).

### Progression / Gameplay Loop

V7 uses `progression` for an auditable gameplay route. It does not generate free-form Java. Instead, it links existing ModSpec content into stages such as ore, material, machine, equipment, entity, structure, loot pool, and dimension.

```json
{
  "type": "progression",
  "id": "ruby_progression",
  "title": "Ruby Progression Loop",
  "entry_stage": "mine_ruby_ore",
  "end_stage": "enter_ruby_realm",
  "stages": [
    {
      "id": "mine_ruby_ore",
      "type": "ore",
      "title": "Mine Ruby Ore",
      "provides": ["raw_ruby"],
      "evidence": ["ruby_ore"]
    },
    {
      "id": "refine_raw_ruby",
      "type": "material",
      "title": "Refine Raw Ruby",
      "requires": ["raw_ruby"],
      "provides": ["ruby"],
      "evidence": ["recipe:raw_ruby_to_ruby"]
    }
  ],
  "links": [
    {
      "from": "mine_ruby_ore",
      "to": "refine_raw_ruby",
      "trigger": "ore_drop",
      "requirement": "Collect raw_ruby"
    }
  ]
}
```

Rules:

- stage ids must be snake_case.
- supported stage types include `ore`, `material`, `recipe`, `machine`, `equipment`, `item`, `block`, `entity`, `structure`, `loot_pool`, `dimension`, `biome`, `world_feature`, and `milestone`.
- `requires`, `provides`, `unlocks`, and `evidence` should reference generated ids, namespaced resource locations, or `recipe:<id>`.
- generation writes `.agent/progression-report.json` and `.agent/progression-report.md` with route coverage, missing references, and entry-to-end reachability.

Full example: [`examples/progression_gameplay_loop.json`](../examples/progression_gameplay_loop.json). More detail: [`docs/progression-dsl.md`](progression-dsl.md).

### Recipe / Loot / Balance Planner

V7.1 uses `balance_plan` for a report-only economy planning layer. It analyzes existing recipes, machines, entity drops, loot pools, and a target progression, then writes machine-readable balance recommendations.

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

Rules:

- `target_progression` must reference an existing `progression` id when provided.
- `profile` must be `easy`, `standard`, or `expert`.
- generation writes `.agent/balance-report.json` and `.agent/balance-report.md`.
- the report includes recipe recommendations, missing recipe suggestions, rarity assignments, machine timing / energy guidance, entity drop rules, loot weight rules, and an economy summary.

Full example: [`examples/balance_gameplay_loop.json`](../examples/balance_gameplay_loop.json). More detail: [`docs/balance-planner.md`](balance-planner.md).

### Quest / Advancement / Guide

V7.2 uses `quest` for player-facing goals. A quest can target an existing `progression`, or it can declare explicit tasks. The generator writes advancement JSON, a Markdown guidebook, and Patchouli-style book/category/entry JSON.

```json
{
  "type": "quest",
  "id": "ruby_questline",
  "title": "Ruby Questline",
  "summary": "Visible goals for the ruby progression.",
  "target_progression": "ruby_progression",
  "guidebook_id": "ruby_guidebook",
  "category": "ruby_progression",
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

Rules:

- `target_progression` must reference an existing `progression` id when provided.
- a quest must declare explicit `tasks` or target a progression that can be converted into tasks.
- supported task types are `obtain_item`, `craft_item`, `mine_block`, `use_machine`, `kill_entity`, `enter_dimension`, `visit_structure`, and `milestone`.
- task `parent` values must reference another task in the same quest.
- generation writes `.agent/quest-report.json`, `.agent/quest-report.md`, `.agent/guidebook.md`, `data/<modid>/advancement/<quest>/<task>.json`, and Patchouli-style guidebook JSON.

Full example: [`examples/quest_guide_gameplay_loop.json`](../examples/quest_guide_gameplay_loop.json). More detail: [`docs/quest-guide-dsl.md`](quest-guide-dsl.md).

### Ore

```json
{
  "type": "ore",
  "id": "ruby_ore",
  "display_name_en_us": "Ruby Ore",
  "display_name_zh_cn": "红宝石矿石",
  "strength": 3.0,
  "resistance": 3.0,
  "sound": "stone",
  "requires_correct_tool": true,
  "tool_tier": "iron",
  "drop": "ruby_mod:ruby",
  "min_drop": 1,
  "max_drop": 1,
  "affected_by_fortune": false,
  "silk_touch_drops_self": false
}
```

Ore can include worldgen:

```json
{
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

Current worldgen scope is limited to overworld underground ore generation.

### Food

```json
{
  "type": "food",
  "id": "ruby_apple",
  "display_name_en_us": "Ruby Apple",
  "display_name_zh_cn": "红宝石苹果",
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

### Sword

```json
{
  "type": "sword",
  "id": "ruby_sword",
  "display_name_en_us": "Ruby Sword",
  "display_name_zh_cn": "红宝石剑",
  "attack_damage_bonus": 4,
  "attack_speed": -2.4,
  "tool_material": "ruby",
  "on_hit": {
    "type": "ignite",
    "seconds": 5
  }
}
```

### Tool

```json
{
  "type": "tool",
  "id": "ruby_pickaxe",
  "display_name_en_us": "Ruby Pickaxe",
  "display_name_zh_cn": "红宝石镐",
  "tool_type": "pickaxe",
  "tool_material": "ruby",
  "attack_damage_bonus": 1.0,
  "attack_speed": -2.8
}
```

Supported `tool_type` values:

- `pickaxe`
- `axe`
- `shovel`
- `hoe`

Supported `tool_material` values include vanilla baselines such as `wood`, `stone`, `iron`, `diamond`, `gold`, `netherite`, plus `ruby` for generated ruby equipment. In V2.7, `ruby` is preserved in ModSpec and mapped to a safe `IRON` Java baseline during deterministic generation.

### Armor

```json
{
  "type": "armor",
  "id": "ruby_helmet",
  "display_name_en_us": "Ruby Helmet",
  "display_name_zh_cn": "红宝石头盔",
  "armor_type": "helmet",
  "armor_material": "ruby"
}
```

Supported `armor_type` values:

- `helmet`
- `chestplate`
- `leggings`
- `boots`

Supported `armor_material` values include vanilla baselines such as `leather`, `chainmail`, `iron`, `diamond`, `gold`, `netherite`, plus `ruby` for generated ruby equipment. In V2.7, `ruby` is preserved in ModSpec and mapped to a safe `IRON` Java baseline during deterministic generation.

### Recipe

Shaped:

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

Shapeless:

```json
{
  "type": "recipe",
  "id": "ruby_from_ruby_block",
  "recipe_type": "shapeless",
  "ingredients": ["ruby_mod:ruby_block"],
  "result": "ruby_mod:ruby",
  "count": 9,
  "category": "misc"
}
```

## Supported Behaviors

### `item.behavior`

- `right_click_heal`
  - `amount > 0`
  - `cooldown_ticks >= 0`
  - `consume` must be boolean
- `right_click_effect`
  - `effect` must be a resource location such as `minecraft:speed`
  - `duration_ticks > 0`
  - `amplifier >= 0`
  - `cooldown_ticks >= 0`
  - `consume` must be boolean

### `food.effects[]`

- `effect` resource location
- `duration_ticks > 0`
- `amplifier >= 0`
- `probability` in `[0, 1]`

### `sword.on_hit`

- currently only `ignite`
- `seconds > 0`

## Validator Rules

The validator currently checks the following kinds of constraints:

- ids and package names are well-formed
- referenced recipe ids and ore drops resolve correctly
- behavior types are supported
- behavior fields use the expected types and ranges
- entity attributes, drops, spawn rules, simple AI goals, and melee/none attack templates use supported ranges
- food effects use legal ranges
- sword `on_hit` currently only supports `ignite`
- tool types are limited to `pickaxe`, `axe`, `shovel`, and `hoe`
- armor types are limited to `helmet`, `chestplate`, `leggings`, and `boots`
- `ruby` is accepted as a tool/armor material for ruby equipment sets
- legacy ore worldgen only appears on `ore`
- V5.4 world features use `world_feature` and currently support `feature_kind = "ore_vein"`
- dimensions, biomes, structures and loot pools use supported template fields only
- V6.1 `java_extension` must stay additive under the `extension` package, use allowlisted imports, String-returning methods, safe text fields, generated diff/rollback/report artifacts, and Gradle build gate evidence for formal acceptance
- V7 `progression` stages and links must be structurally valid; missing evidence references are reported as warnings and in `.agent/progression-report.json`
- V7.1 `balance_plan` must use a supported profile and must target an existing progression when `target_progression` is set
- V7.2 `quest` must use supported task types, valid parent links, and an existing `target_progression` when one is declared
- `min_y < max_y`
- `vein_size > 0`
- `veins_per_chunk > 0`

## Modify Merge Rules

`modify` reads the existing `.agent/modspec.json`, plans a patch, merges it into the saved spec, and re-generates only managed files.

Possible merge outcomes:

- `added`: feature did not exist and was added
- `updated`: feature id existed and its content changed
- `skipped`: feature already matched the requested patch

Important behavior:

- user-authored unmanaged files are preserved
- generated files listed in `generation-summary.json` are re-written
- repeated identical modify requests should become `skipped`
- nested fields like `behavior`, `effects`, and `worldgen` are merged through feature replacement by id

## Example: Basic Ruby

```json
{
  "mod_id": "ruby_mod",
  "mod_name": "Ruby Mod",
  "package": "com.generated.ruby_mod",
  "features": [
    {
      "type": "item",
      "id": "ruby",
      "display_name_en_us": "Ruby",
      "display_name_zh_cn": "红宝石"
    }
  ]
}
```

## Example: Behavior Item

```json
{
  "mod_id": "ruby_mod",
  "mod_name": "Ruby Mod",
  "package": "com.generated.ruby_mod",
  "features": [
    {
      "type": "item",
      "id": "ruby_charm",
      "display_name_en_us": "Ruby Charm",
      "display_name_zh_cn": "红宝石护符",
      "behavior": {
        "type": "right_click_heal",
        "amount": 4,
        "cooldown_ticks": 400,
        "consume": false
      }
    }
  ]
}
```

## Example: Food Effect

```json
{
  "mod_id": "ruby_mod",
  "mod_name": "Ruby Mod",
  "package": "com.generated.ruby_mod",
  "features": [
    {
      "type": "food",
      "id": "ruby_apple",
      "display_name_en_us": "Ruby Apple",
      "display_name_zh_cn": "红宝石苹果",
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
  ]
}
```

## Example: Sword Ignite

```json
{
  "mod_id": "ruby_mod",
  "mod_name": "Ruby Mod",
  "package": "com.generated.ruby_mod",
  "features": [
    {
      "type": "sword",
      "id": "ruby_sword",
      "display_name_en_us": "Ruby Sword",
      "display_name_zh_cn": "红宝石剑",
      "attack_damage_bonus": 4,
      "attack_speed": -2.4,
      "tool_material": "ruby",
      "on_hit": {
        "type": "ignite",
        "seconds": 5
      }
    }
  ]
}
```

## Example: Ore Worldgen

```json
{
  "mod_id": "ruby_mod",
  "mod_name": "Ruby Mod",
  "package": "com.generated.ruby_mod",
  "features": [
    {
      "type": "item",
      "id": "ruby",
      "display_name_en_us": "Ruby",
      "display_name_zh_cn": "红宝石"
    },
    {
      "type": "ore",
      "id": "ruby_ore",
      "display_name_en_us": "Ruby Ore",
      "display_name_zh_cn": "红宝石矿石",
      "drop": "ruby_mod:ruby",
      "min_drop": 1,
      "max_drop": 1,
      "affected_by_fortune": false,
      "silk_touch_drops_self": false,
      "worldgen": {
        "enabled": true,
        "dimension": "minecraft:overworld",
        "min_y": -64,
        "max_y": 32,
        "vein_size": 6,
        "veins_per_chunk": 4
      }
    }
  ]
}
```

## Example: Tool And Armor

```json
{
  "mod_id": "ruby_mod",
  "mod_name": "Ruby Mod",
  "package": "com.generated.ruby_mod",
  "features": [
    {
      "type": "tool",
      "id": "ruby_pickaxe",
      "display_name_en_us": "Ruby Pickaxe",
      "display_name_zh_cn": "红宝石镐",
      "tool_type": "pickaxe",
      "tool_material": "ruby",
      "attack_damage_bonus": 1.0,
      "attack_speed": -2.8
    },
    {
      "type": "armor",
      "id": "ruby_helmet",
      "display_name_en_us": "Ruby Helmet",
      "display_name_zh_cn": "红宝石头盔",
      "armor_type": "helmet",
      "armor_material": "ruby"
    }
  ]
}
```

## Example: V2.7 Equipment Set With Recipes

The rules planner and mock LLM can produce this shape from requests such as `红宝石工具套装` or `ruby tool set`.

```json
{
  "mod_id": "ruby_mod",
  "mod_name": "Ruby Mod",
  "package": "com.generated.ruby_mod",
  "features": [
    {
      "type": "item",
      "id": "ruby",
      "display_name_en_us": "Ruby",
      "display_name_zh_cn": "红宝石"
    },
    {
      "type": "sword",
      "id": "ruby_sword",
      "display_name_en_us": "Ruby Sword",
      "display_name_zh_cn": "红宝石剑",
      "tool_material": "ruby",
      "attack_damage_bonus": 4,
      "attack_speed": -2.4
    },
    {
      "type": "tool",
      "id": "ruby_pickaxe",
      "display_name_en_us": "Ruby Pickaxe",
      "display_name_zh_cn": "红宝石镐",
      "tool_type": "pickaxe",
      "tool_material": "ruby",
      "attack_damage_bonus": 1.0,
      "attack_speed": -2.8
    },
    {
      "type": "recipe",
      "id": "ruby_pickaxe",
      "recipe_type": "shaped",
      "pattern": ["RRR", " S ", " S "],
      "keys": {
        "R": "ruby_mod:ruby",
        "S": "minecraft:stick"
      },
      "result": "ruby_mod:ruby_pickaxe",
      "count": 1,
      "category": "equipment",
      "group": "ruby_equipment"
    }
  ]
}
```

## Example: V2.8 Block Variants

rules planner 和 mock LLM 可以从 `红宝石方块变体` 或 `ruby block variants` 生成完整建筑方块套装。在这条普通 ModSpec 路径中，LLM 输出会收束为 ModSpec，具体 Java/JSON/PNG 由确定性 generator 产出；如果未来需求超出 ModSpec 表达能力，则应走 Direct Code Lane 或 Free-Code Lab，而不是改写这个规格示例。

```json
{
  "mod_id": "ruby_mod",
  "mod_name": "Ruby Mod",
  "package": "com.generated.ruby_mod",
  "features": [
    {
      "type": "block",
      "id": "ruby_block",
      "display_name_en_us": "Block of Ruby",
      "display_name_zh_cn": "红宝石方块",
      "block_kind": "cube"
    },
    {
      "type": "block",
      "id": "ruby_stairs",
      "display_name_en_us": "Ruby Stairs",
      "display_name_zh_cn": "红宝石楼梯",
      "block_kind": "stairs",
      "base_block": "ruby_block"
    },
    {
      "type": "block",
      "id": "ruby_door",
      "display_name_en_us": "Ruby Door",
      "display_name_zh_cn": "红宝石门",
      "block_kind": "door",
      "base_block": "ruby_block"
    },
    {
      "type": "recipe",
      "id": "ruby_stairs",
      "recipe_type": "shaped",
      "pattern": ["R  ", "RR ", "RRR"],
      "keys": {
        "R": "ruby_mod:ruby_block"
      },
      "result": "ruby_mod:ruby_stairs",
      "count": 4,
      "category": "building",
      "group": "ruby_block_variants"
    }
  ]
}
```
