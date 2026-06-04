## V2.8 Block Variants Smoke

```powershell
py -3.11 -m agent.cli generate --build --audit "Create a ruby mod with ruby block variants." --workspace-name v28-block-variants --overwrite --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby block variants." --planner llm --llm-provider mock --workspace-name v28-llm-block-variants --overwrite --no-build --audit --json
py -3.11 -m agent.cli generate --build --audit "Create a ruby mod with ruby block." --workspace-name v28-modify-block-base --overwrite --json
py -3.11 -m agent.cli modify workspace\v28-modify-block-base "添加红宝石方块变体。" --build --audit --json
py -3.11 -m agent.cli modify workspace\v28-modify-block-base "添加红宝石方块变体。" --build --audit --json
```

Expected:

- rules planner creates `ruby_block`, `ruby_stairs`, `ruby_slab`, `ruby_wall`, `ruby_button`, `ruby_pressure_plate`, `ruby_fence`, `ruby_fence_gate`, `ruby_door`, and `ruby_trapdoor`
- generated ModSpec records `block_kind` and `base_block`
- Java registration uses vanilla subclasses such as `StairBlock`, `SlabBlock`, `ButtonBlock`, `DoorBlock`, and `TrapDoorBlock`
- recipes, loot tables, blockstates, block models, item models, textures, and lang keys are generated
- audit succeeds and checks class usage, assets, textures, recipes, and registration
- repeated modify skips existing block variants and recipes
- Gradle build succeeds for the full rules planner block variant project
