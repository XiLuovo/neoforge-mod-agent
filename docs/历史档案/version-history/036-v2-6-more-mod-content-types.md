## V2.6 More Mod Content Types

目标：在不引入复杂 GUI、BlockEntity 或实体系统的前提下，扩展更常见、可演示的 Mod 内容类型。

完成内容：

- 新增 `tool` ModSpec 类型。
- 支持工具类型：
  - `pickaxe`
  - `axe`
  - `shovel`
  - `hoe`
- 新增 `armor` ModSpec 类型。
- 支持护甲类型：
  - `helmet`
  - `chestplate`
  - `leggings`
  - `boots`
- 扩展 schema、validator、rules planner、LLM planner、MockLLMClient、modify merge、Java generator、asset generator、auditor、capability matrix 和 eval coverage。
- 工具生成使用确定性 Java 注册：
  - `properties.pickaxe(...)`
  - `properties.axe(...)`
  - `properties.shovel(...)`
  - `properties.hoe(...)`
- 护甲生成使用确定性 Java 注册：
  - `properties.humanoidArmor(..., ArmorType.HELMET)`
  - `ArmorType.CHESTPLATE`
  - `ArmorType.LEGGINGS`
  - `ArmorType.BOOTS`
- 程序化材质支持工具和护甲图标。
- audit 检查工具/护甲模型、贴图、语言 key、Java 注册、工具方法和护甲 `ArmorType`。
- package metadata 更新到 `2.6.0`。

价值：

- 内容生成能力从基础物品/方块/矿石/食物/剑扩展到更完整的装备层。
- 保持核心边界：自然语言或 LLM 只产出 ModSpec，Java/JSON/PNG 仍由确定性 generator 生成。
- 为后续 V2.7+ 做更复杂装备套装、材料系统、配方自动生成和实战演示打基础。
