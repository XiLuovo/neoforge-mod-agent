# Real LLM Semantic Coverage

Source run: `resume-ab-20260718-decomposed-5case-fix1`

## Metrics

- semantic success: `3/5`
- expected feature match: `5/5`
- expected category match: `9/13`
- ignored feature warning messages: `0`
- removed behavior warning messages: `0`
- semantic warning messages: `2`

## Cases

- `basic_ruby`: strict=true semantic=true
  - semantic warnings: 2 unique message(s)
- `ruby_charm_behavior`: strict=true semantic=true
- `speed_crystal_behavior`: strict=true semantic=true
- `ruby_apple_effect`: strict=true semantic=false
  - missing expected categories: food, behavior, food_effect
- `ruby_sword_ignite`: strict=true semantic=false
  - missing expected categories: sword_ignite

## Boundary

Semantic coverage compares expected features/categories with the generated ModSpec. It does not prove Gradle build or Minecraft runtime behavior.
