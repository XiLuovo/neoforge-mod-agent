# Real LLM Semantic Coverage

Source run: `resume-ab-20260718-decomposed-5case`

## Metrics

- semantic success: `2/5`
- expected feature match: `4/5`
- expected category match: `7/13`
- ignored feature warning messages: `2`
- removed behavior warning messages: `1`
- semantic warning messages: `3`

## Cases

- `basic_ruby`: strict=false semantic=false
  - missing expected features: ruby
  - missing expected categories: item
  - semantic warnings: 2 unique message(s)
- `ruby_charm_behavior`: strict=true semantic=true
- `speed_crystal_behavior`: strict=true semantic=true
- `ruby_apple_effect`: strict=true semantic=false
  - missing expected categories: food, behavior, food_effect
- `ruby_sword_ignite`: strict=true semantic=false
  - missing expected categories: behavior, sword_ignite
  - semantic warnings: 1 unique message(s)

## Boundary

Semantic coverage compares expected features/categories with the generated ModSpec. It does not prove Gradle build or Minecraft runtime behavior.
