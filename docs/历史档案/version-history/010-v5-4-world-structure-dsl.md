## V5.4 World / Structure DSL

目标：把生成器从“内容、机器、生物”继续推进到数据驱动的世界玩法包，支持维度、群系、地物、矿脉规则、结构和战利品池。

完成内容：
- package metadata 更新到 `5.4.0`。
- `ModSpec` 新增 `dimension`、`biome`、`world_feature`、`structure`、`loot_pool` 五类 feature。
- `WorldgenGenerator` 新增 dimension type、dimension、biome、configured / placed feature、NeoForge biome modifier、jigsaw structure、structure set、template pool 和 chest loot table 生成。
- validator / auditor / rules planner / mock LLM / modify merge / checklist / capability matrix 均接入 V5.4 字段。
- 新增示例：`examples/world_ruby_realm.json`。

验证入口：

```powershell
py -3.11 -m agent.cli generate-from-spec .\examples\world_ruby_realm.json --workspace-name v54-world-smoke --audit --no-build --json
```

边界：
- 这是模板化 World / Structure DSL，不是任意 datapack / NBT / Java 生成器。
- 当前结构生成以 jigsaw 元数据、structure set 和 empty template pool 为主；真实结构 NBT 拼装、复杂地形噪声、多维度玩法逻辑仍在范围外。
