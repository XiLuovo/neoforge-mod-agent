# Real LLM Semantic Coverage

Source run: `resume-decomposed-13case-postfix-20260719`

## Metrics

- semantic success: `7/13`
- expected feature match: `15/33`
- expected category match: `22/37`
- ignored feature warning messages: `7`
- removed behavior warning messages: `1`
- semantic warning messages: `16`

## Cases

- `basic_ruby`: strict=true semantic=true
  - semantic warnings: 7 unique message(s)
- `ruby_charm_behavior`: strict=true semantic=true
- `speed_crystal_behavior`: strict=true semantic=true
- `ruby_apple_effect`: strict=true semantic=false
  - missing expected categories: food, behavior, food_effect
- `ruby_sword_ignite`: strict=true semantic=false
  - missing expected categories: behavior, sword_ignite
  - semantic warnings: 1 unique message(s)
- `ruby_pickaxe_tool`: strict=true semantic=true
- `ruby_tool_set`: strict=true semantic=true
- `ruby_armor_set`: strict=true semantic=false
  - missing expected features: ruby_helmet, ruby_chestplate, ruby_leggings, ruby_boots
  - missing expected categories: armor
  - semantic warnings: 1 unique message(s)
- `ruby_block_variants`: strict=true semantic=false
  - missing expected features: ruby_block, ruby_stairs, ruby_slab, ruby_wall, ruby_button, ruby_pressure_plate, ruby_fence, ruby_fence_gate, ruby_door, ruby_trapdoor
  - missing expected categories: block, recipe, block_variants, interactive_blocks
  - semantic warnings: 1 unique message(s)
- `ruby_ore_worldgen`: strict=true semantic=true
- `ruby_goblin_entity`: strict=true semantic=false
  - missing expected categories: entity
- `ruby_realm_world_structure`: strict=false semantic=false
  - missing expected features: ruby_realm, ruby_fields, ruby_vein, ruby_shrine
  - missing expected categories: dimension, biome, worldgen, structure
  - semantic warnings: 5 unique message(s)
- `progression_gameplay_loop`: strict=true semantic=true
  - semantic warnings: 1 unique message(s)

## Boundary

Semantic coverage compares expected features/categories with the generated ModSpec. It does not prove Gradle build or Minecraft runtime behavior.
