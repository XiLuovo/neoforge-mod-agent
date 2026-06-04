## V5.3 Entity / Mob DSL

目标：把生成器从静态内容、行为模板、机器 GUI 推进到基础生物玩法，让它能生成怪物、宠物、Boss、NPC 这类实体骨架，同时继续保持 `ModSpec -> deterministic generator -> audit` 的边界。

完成内容：
- package metadata 更新到 `5.3.0`。
- `ModSpec` 新增 `entity` / `entities`，覆盖 `entity_kind`、实体分类、尺寸、追踪范围、经验、属性、掉落、生成规则、AI goals 和攻击方式。
- 新增 `EntityGenerator`，确定性生成 `EntityType` 注册、实体 Java 类、属性注册、客户端 renderer 注册类。
- 资源生成接入实体贴图、语言 key、实体 loot table 和 NeoForge `add_spawns` biome modifier。
- validator、audit、manual checklist、capability matrix、knowledge base、golden tests 和回归测试覆盖实体链路。
- 新增示例 `examples/entity_ruby_goblin.json` 和文档 `docs/规格与生成/entity-dsl.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest tests.test_generation_audit tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\entity_ruby_goblin.json --workspace-name v53-entity-smoke --audit --no-build --json
```

边界：
- 当前是模板化实体系统，不是任意 Java / 任意 AI / 任意动画生成。
- 稳定攻击模板为 `melee` 和 `none`；远程弹幕、复杂驯服、交易、Boss 阶段和模型动画属于后续路线。
