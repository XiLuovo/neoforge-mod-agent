## V2.7 Equipment Sets And Recipes

目标：把 V2.6 的工具/护甲单件生成补成更完整的装备链，让一句话就能生成可合成、可审计、可构建的红宝石工具套装和护甲套装。

完成内容：

- rules planner 支持：
  - `红宝石工具套装`
  - `一套红宝石工具`
  - `ruby tool set`
  - `ruby tools`
  - `红宝石护甲套装`
  - `一套红宝石护甲`
  - `ruby armor set`
  - `ruby armor`
- 红宝石工具套装会生成：
  - `ruby`
  - `ruby_sword`
  - `ruby_pickaxe`
  - `ruby_axe`
  - `ruby_shovel`
  - `ruby_hoe`
- 红宝石护甲套装会生成：
  - `ruby`
  - `ruby_helmet`
  - `ruby_chestplate`
  - `ruby_leggings`
  - `ruby_boots`
- 自动生成每件装备对应的 shaped crafting recipe：
  - 工具/剑使用 `ruby_mod:ruby` + `minecraft:stick`
  - 护甲使用 `ruby_mod:ruby`
- `tool_material` 和 `armor_material` 支持 `ruby`。
- Java generator 将 `ruby` 材料映射到安全的 vanilla `IRON` 基线，保持 build 稳定。
- schema、validator、LLM planner、MockLLMClient、capability matrix 和测试覆盖同步更新。
- audit 继续覆盖装备模型、贴图、语言 key、注册代码和 recipe 引用。
- package metadata 更新到 `2.7.0`。

价值：

- V2.6 的工具/护甲不再只是“能注册”，而是形成完整可玩的装备链。
- 仍然保持核心边界：自然语言或 LLM 只产出 ModSpec，Java/JSON/PNG 仍由确定性 generator 生成。
- 为后续真正自定义材料属性、套装效果和更复杂配方系统打基础。
