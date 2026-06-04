## 2026-05-13 Real LLM Natural Prompt Runtime Validation

本轮目标是验证真实 LLM 生成的 workspace 是否不只通过命令行检查，还能进入游戏完成基础人工测试。

| Case | Workspace | Result | Manual runtime checks |
| --- | --- | --- | --- |
| Machine | `workspace/real-llm-natural-machine-20260513` | 通过 | `real LLM` 返回成功；ModSpec 校验通过；audit 通过；build 通过；游戏内创建世界通过；创造物品栏中红宝石、红宝石矿石、红宝石压缩机图标正常；压缩机可放置、破坏、右键打开 GUI；工作台配方合成通过。 |
| Ruby Basic | `workspace/real-llm-natural-ruby-basic-20260513` | 通过 | `real LLM` 返回成功；ModSpec 校验通过；audit 通过；build 通过；进入世界时发现并修复 `worldgen/configured_feature` runtime JSON 问题；修复后游戏内验证通过。 |
| Progression | `workspace/real-llm-natural-progression-retry-20260513` | 通过 | `real LLM` 返回成功；ModSpec 校验通过；audit 通过；build 通过；修复 worldgen runtime schema、dimension type、biome carvers、advancement 背景资源后，游戏内创建世界、创造物品栏图标、方块放置/破坏、压缩机 GUI、工具/护甲和任务进度验证通过。 |

Runtime finding:

- `build` 通过不代表 Minecraft registry runtime 一定通过。
- 多个带矿石生成的 real LLM case 都暴露过同类问题：configured feature 的 `target` 不能是字符串，必须是 rule-test object。
- 修复后的合法形态为 `{"predicate_type": "minecraft:tag_match", "tag": "minecraft:stone_ore_replaceables"}`。
- Progression 额外暴露了 `dimension_type`、`worldgen/biome` 和根 advancement 背景资源的 runtime schema 风险。
- 源码层已补生成器、audit 和回归测试，避免后续新生成 workspace 再依赖手工 patch。
