## V0.8 矿石自然生成 / Worldgen

目标：让 ore feature 能自然生成在世界里。

完成内容：

- 在 `ModSpec` 中加入 `ore.worldgen`。
- 支持主世界地下矿石生成。
- 新增 `worldgen_generator.py`。
- 生成 worldgen 文件：
  - `data/<modid>/worldgen/configured_feature/<ore_id>.json`
  - `data/<modid>/worldgen/placed_feature/<ore_id>.json`
  - `data/<modid>/neoforge/biome_modifier/add_<ore_id>.json`
- 扩展 validator 校验 worldgen 约束：
  - worldgen 只能挂在 ore 上
  - 只支持 `minecraft:overworld`
  - Y 范围合法
  - vein size 必须为正
  - veins per chunk 必须为正
- 扩展 rules planner 和 mock LLM 的 worldgen prompt。
- 支持 modify 给已有 ore 新增或更新 worldgen。

价值：

- 补齐 ore 的基本闭环：item、block、drop、tag、loot、自然生成。
- 加入真实 datapack JSON 生成能力，同时仍保持确定性。
