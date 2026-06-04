## V2.3 Programmatic Texture Generation

目标：把生成材质纳入正式、可审计、可修复的确定性生成链路，减少游戏内黑紫缺失材质。

完成内容：

- 为 `item`、`food`、`sword`、`block`、`ore` 生成确定性的 `16x16 RGBA PNG` 材质。
- 行为物品会根据行为类型选择不同模板：
  - `right_click_heal` 使用 `heal_badge`
  - `right_click_effect` 使用 `effect_crystal`
- 普通 item 使用 `gem` 模板。
- food 使用 `apple` 模板。
- sword 使用 `sword` 模板。
- block 使用 `solid_block` 模板。
- ore 使用 `ore_block` 模板。
- 新增 `.agent/texture-manifest.json`，记录每个生成材质的 feature 类型、id、路径、模板、尺寸和颜色格式。
- `generation-summary.json` 会记录 `.agent/texture-manifest.json` 和生成的 PNG 文件。
- `audit` 新增材质检查：
  - manifest 是否存在
  - manifest JSON 是否可解析
  - manifest 中的 texture 文件是否存在
  - feature 对应的 PNG 是否存在
  - PNG 是否为 `16x16 RGBA`
- `repair-loop` 可以恢复缺失的受控材质文件。
- `capabilities` 增加：
  - `procedural_textures`
  - `texture_audit`

价值：

- 程序化材质不是最终美术，但能让生成项目更适合打开游戏演示。
- 黑紫块问题从“人工进游戏才发现”前移到 `audit` 阶段。
- 后续接入 LLM / 多 Agent 材质创作时，可以把 `.agent/texture-manifest.json` 作为稳定接口。
