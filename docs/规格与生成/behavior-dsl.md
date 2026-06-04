# V5.1 Behavior DSL

> 文档定位：这是 Behavior DSL 专项材料，不是主学习入口。需要理解事件-条件-动作如何进入 ModSpec 和 generator 时再读。

Behavior DSL 是 V5.1 的第一步：把“玩法行为”从少量硬编码模板升级成可组合的 `event -> condition -> action` 结构，同时继续保持 NeoForge 26.1 Java 代码由 Python 确定性生成。

这句话描述的是 V5.1 Behavior DSL 这个功能层的稳定路径边界：行为逻辑先收束为 DSL，再由 generator 落地。它不否定 V8.4+ 的 Direct Code Lane；当前全局边界以 [project-limitations.md](../总览/project-limitations.md)、[direct-code-lane.md](../Agent与能力/direct-code-lane.md) 和 [agent-workflow.md](../Agent与能力/agent-workflow.md) 为准。

## 结构

```json
{
  "behavior": {
    "type": "event_action",
    "events": [
      {
        "trigger": "right_click",
        "conditions": [{ "type": "not_sneaking" }],
        "cooldown_ticks": 100,
        "actions": [
          { "type": "heal", "target": "self", "amount": 4 },
          {
            "type": "apply_effect",
            "target": "self",
            "effect": "minecraft:regeneration",
            "duration_ticks": 100,
            "amplifier": 0
          },
          { "type": "spawn_particles", "particle": "minecraft:heart", "count": 10 },
          { "type": "play_sound", "sound": "minecraft:entity.experience_orb.pickup" }
        ]
      }
    ]
  }
}
```

## 当前支持

Behavior DSL 现在是一层共享语义层，不再只绑定物品和方块：

- Hosts: `item`, `block`, `sword`, `ore`, `machine`, `entity`, `progression`, `quest`
- Compiled runtime: `item`, `block`, `sword`, `ore`
- Report-only semantics: `machine`, `entity`, `progression`, `quest`

也就是说，简单物品/方块行为仍然会生成受控 Java hook；机器、实体、进度和任务线的行为先进入 `.agent/behavior-report.json` / `.agent/behavior-report.md`，用于审计、展示和后续 runtime 扩展规划。

支持的触发器：

- Item / block: `right_click`, `hit_entity`, `inventory_tick`, `block_use`, `block_tick`
- Machine: `server_tick`, `machine_tick`, `machine_complete`, `energy_low`, `inventory_changed`
- Entity: `spawn`, `entity_tick`, `hurt`, `attack`, `death`, `target_acquired`
- Quest / progression: `quest_start`, `task_complete`, `quest_complete`, `guide_open`, `stage_enter`, `stage_complete`, `link_unlock`, `loop_complete`

支持的组合能力：

- trigger modes: `any`, `all`, `sequence`
- state: `state_equals`, `state_not_equals`, `state_above`, `state_below`, `set_state`, `increment_state`, `clear_state`
- resource: `resource_at_least`, `resource_below`, `consume_resource`, `restore_resource`, `transfer_resource`
- cooldown / combo: `cooldown_ready`, `combo_ready`, `cooldown_ticks`, `window_ticks`
- chain: `chain_event`, `chain_trigger`, `delay_ticks`, `chain_window_ticks`

基础动作仍包括 `heal`, `apply_effect`, `ignite`, `consume_item`, `cooldown`, `spawn_particles`, `play_sound`。

## 示例

```powershell
py -3.11 -m agent.cli generate-from-spec .\examples\behavior_dsl_battle_charm.json --workspace-name behavior-dsl-demo --overwrite --no-build --audit --json
```

这个示例会生成：

- `BattleCharmItem.java`: 右键回血、给再生、播放音效、生成粒子，并在背包 tick 中按条件显示粒子
- `RubyPedestalBlock.java`: 空手右键方块时给玩家再生效果、生成粒子、播放音效
- `.agent/behavior-report.json`: 记录 host 覆盖、compiled/report-only 分类、combo/state/resource/chain 统计

机器、实体、进度和任务线示例也会进入同一个 behavior report：

```powershell
py -3.11 -m agent.cli generate-from-spec .\examples\machine_ruby_compressor.json --workspace-name behavior-machine-demo --overwrite --no-build --audit --json
py -3.11 -m agent.cli generate-from-spec .\examples\progression_gameplay_loop.json --workspace-name behavior-progression-demo --overwrite --no-build --audit --json
py -3.11 -m agent.cli generate-from-spec .\examples\quest_guide_gameplay_loop.json --workspace-name behavior-quest-demo --overwrite --no-build --audit --json
```

## 边界

Behavior DSL 仍然不是任意 Java 生成。LLM 只应该输出 `ModSpec.behavior.events`，真正的 Java、资源、报告和检查清单由确定性生成器产出。这样它比纯 `ModSpec` 字段更接近玩法设计，又保留 audit、repair-loop、eval 和 dashboard 所需要的可复现边界。

这是 Behavior DSL 功能层自己的稳定路径边界。当前全局架构已经是 `ModSpec-first hybrid`：当 `ModSpec` / DSL 表达不足时，应走 Direct Code Lane 或 Free-Code Lab，并保留结构化补丁、review、snapshot、audit/build 和 rollback evidence。
