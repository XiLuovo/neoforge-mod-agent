## V5.1 Behavior DSL

目标：先把“行为”做通用，让生成器从静态物品/方块推进到受控玩法模板。

完成内容：
- 新增 `BehaviorEventSpec`、`BehaviorActionSpec`、`BehaviorConditionSpec`，支持 `event -> condition -> action` 结构。
- 支持右键触发、攻击命中、背包 tick、方块交互、条件判断、消耗物品、给予效果、生成粒子和播放声音。
- `BehaviorGenerator` 确定性生成对应的 Item / Sword / Block Java 子类，保持 LLM 只输出 `ModSpec`。
- 新增 `docs/规格与生成/behavior-dsl.md` 和 `examples/behavior_dsl_battle_charm.json`。
- validator、audit 和回归测试覆盖行为 DSL。

边界：
- Behavior DSL 不是任意 Java 生成，只覆盖受控触发器、条件和动作集合。
- 机器方块右键已保留给 GUI 打开动作，复杂机器逻辑进入 V5.2 的机器 DSL。
