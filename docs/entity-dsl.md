# V5.3 Entity / Mob DSL

> 文档定位：这是 Entity / Mob DSL 专项材料，不是主学习入口。需要理解实体模板和 mob 生成能力时再读。

Entity / Mob DSL 是 V5.3 的核心：把生成器从物品、方块、机器继续推进到“能生成基础生物玩法”。它仍然不是任意 Java 代码生成，而是让 LLM 或 rules planner 输出结构化 `ModSpec`，再由 Python 确定性生成 NeoForge Java、数据包 JSON 和占位 PNG 资源。

这句话描述的是 V5.3 Entity / Mob DSL 这个功能层的稳定路径边界，不否定 V8.4+ 的 `ModSpec-first hybrid` 架构。当前全局边界以 [project-limitations.md](project-limitations.md)、[direct-code-lane.md](direct-code-lane.md) 和 [agent-workflow.md](agent-workflow.md) 为准。

## Scope

当前支持：

- 自定义实体注册：`EntityType`、尺寸、追踪范围、更新间隔、分类。
- 生物属性：生命值、移动速度、攻击力、护甲、跟随距离、击退抗性、经验值。
- 掉落：`data/<modid>/loot_table/entities/<id>.json`。
- 生成规则：NeoForge `add_spawns` biome modifier。
- 简单 AI goal：漂浮、近战、随机游走、看玩家、随机看向、受伤反击、锁定玩家。
- 攻击方式：当前稳定模板为 `melee` 和 `none`。
- 资源：实体语言 key、`textures/entity/<id>.png`、客户端 renderer 注册。

仍然不支持：

- Geckolib/复杂动画、复杂模型、Boss 阶段机制、远程弹幕、复杂驯服/交易系统、复杂寻路。
- 任意 Java 片段或自由发挥 AI 逻辑。

## ModSpec Example

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

完整示例见 [`examples/entity_ruby_goblin.json`](../examples/entity_ruby_goblin.json)。

## Generate

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli generate-from-spec .\examples\entity_ruby_goblin.json --workspace-name demo-entity --audit --no-build --json
```

生成后可重点查看：

- `src/main/java/com/generated/entity_mod/entity/RubyGoblinEntity.java`
- `src/main/java/com/generated/entity_mod/client/RubyGoblinRenderer.java`
- `src/main/java/com/generated/entity_mod/client/EntityModEntityClient.java`
- `src/main/resources/data/entity_mod/loot_table/entities/ruby_goblin.json`
- `src/main/resources/data/entity_mod/neoforge/biome_modifier/add_ruby_goblin.json`

游戏内基础验证可以用：

```text
/summon entity_mod:ruby_goblin
```
