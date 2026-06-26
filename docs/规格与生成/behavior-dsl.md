# Behavior DSL

> RC1 定位：Behavior DSL 是 `ModSpec-first` 输入层的一部分。它描述玩法行为，由 deterministic generator 或报告层落地，不是自由 Java 生成。

## 作用

Behavior DSL 把行为写成：

```text
event -> conditions -> actions
```

这样 planner 或 LLM 可以表达“右键回血”“命中点燃”“方块交互触发效果”等需求，同时仍然保留结构化验证和可回放 evidence。

## 示例

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
          }
        ]
      }
    ]
  }
}
```

## 当前支持

- compiled hosts：`item`、`block`、`sword`、`ore`。
- report-only hosts：`machine`、`entity`、`progression`、`quest`。
- common actions：`heal`、`apply_effect`、`ignite`、`consume_item`、`cooldown`、`spawn_particles`、`play_sound`。
- common conditions：state、resource、cooldown、combo 和 sequence 相关条件。

## Evidence

```text
.agent/behavior-report.json
.agent/behavior-report.md
.agent/audit-report.json
```

## 边界

- 不接受任意 Java source。
- 不替代 tool-calling repair/refine loop。
- 超出 DSL 的需求应在 RC1 中通过 structured patch tool 或后续规格扩展处理。
