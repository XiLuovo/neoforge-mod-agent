# V5.4 World / Structure DSL

> 文档定位：这是 World / Structure DSL 专项材料，不是主学习入口。需要理解世界结构资源和 audit 覆盖时再读。

V5.4 把生成器从“内容和实体”继续推进到数据驱动的世界玩法包。边界仍然是：

```text
natural language / LLM / rules -> ModSpec -> deterministic generator -> JSON resources -> audit
```

LLM 只产出结构化 `ModSpec`，不会直接写 Java、NBT 或任意 datapack。

这句话描述的是 V5.4 World / Structure DSL 这个功能层的稳定路径边界，不否定 V8.4+ 的 Direct Code Lane。当前全局边界以 [project-limitations.md](project-limitations.md)、[direct-code-lane.md](direct-code-lane.md) 和 [agent-workflow.md](agent-workflow.md) 为准。

## Supported Types

- `dimension`: 生成 `data/<modid>/dimension_type/<id>.json` 和 `data/<modid>/dimension/<id>.json`。
- `biome`: 生成 `data/<modid>/worldgen/biome/<id>.json`。
- `world_feature`: 生成 `configured_feature`、`placed_feature` 和 NeoForge `biome_modifier`。当前支持 `feature_kind = "ore_vein"`。
- `structure`: 生成 jigsaw `structure`、`structure_set` 和 `template_pool/<id>/start_pool.json`。
- `loot_pool`: 生成 `data/<modid>/loot_table/chests/<id>.json`。

## Smoke Test

```powershell
py -3.11 -m agent.cli generate-from-spec .\examples\world_ruby_realm.json --workspace-name v54-world-smoke --overwrite --audit --no-build --json
```

Expected key outputs:

```text
src/main/resources/data/world_mod/dimension_type/ruby_realm.json
src/main/resources/data/world_mod/dimension/ruby_realm.json
src/main/resources/data/world_mod/worldgen/biome/ruby_fields.json
src/main/resources/data/world_mod/worldgen/configured_feature/ruby_vein.json
src/main/resources/data/world_mod/worldgen/placed_feature/ruby_vein.json
src/main/resources/data/world_mod/neoforge/biome_modifier/add_ruby_vein.json
src/main/resources/data/world_mod/worldgen/structure/ruby_shrine.json
src/main/resources/data/world_mod/worldgen/structure_set/ruby_shrine.json
src/main/resources/data/world_mod/worldgen/template_pool/ruby_shrine/start_pool.json
src/main/resources/data/world_mod/loot_table/chests/ruby_shrine_loot.json
```

## Current Boundary

This is a template-based DSL. It is useful for auditable world data scaffolding, but it does not yet author real NBT structures, custom terrain noise graphs, advanced placement processors, or cross-dimension gameplay systems.
