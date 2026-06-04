## V0.8 Ore Worldgen

Goal: make ore features naturally generate in the world.

Completed:

- Added `ore.worldgen` to `ModSpec`.
- Supported overworld underground ore generation.
- Added `worldgen_generator.py`.
- Generated worldgen files:
  - `data/<modid>/worldgen/configured_feature/<ore_id>.json`
  - `data/<modid>/worldgen/placed_feature/<ore_id>.json`
  - `data/<modid>/neoforge/biome_modifier/add_<ore_id>.json`
- Extended validator for worldgen constraints:
  - worldgen only on ore
  - only `minecraft:overworld`
  - valid Y range
  - positive vein size
  - positive veins per chunk
- Extended rules planner and mock LLM for worldgen prompts.
- Supported modify updates for existing ore worldgen.

Value:

- Completed the basic content loop for ores: item, block, drop, tags, loot, and natural generation.
- Added a realistic datapack-generation capability while keeping JSON deterministic.
