## V2.8 More Block Content

目标：进入“可交互但不复杂”的方块扩展，让普通 block 可以声明常见建筑/红石方块变体，同时继续强化 deterministic generator。

完成内容：

- `BlockSpec` 新增 `block_kind` 与 `base_block`。
- 支持的 `block_kind`：
  - `cube`
  - `stairs`
  - `slab`
  - `wall`
  - `button`
  - `pressure_plate`
  - `fence`
  - `fence_gate`
  - `door`
  - `trapdoor`
- rules planner 支持：
  - `红宝石方块变体`
  - `红宝石建筑方块套装`
  - `ruby block variants`
  - `ruby building block set`
  - 单独的 `红宝石楼梯 / ruby stairs`、`红宝石门 / ruby door` 等表达。
- 生成器会为方块变体确定性生成：
  - vanilla block subclass Java 注册
  - blockstate JSON
  - block model JSON
  - item model JSON
  - loot table
  - shaped/shapeless recipe
  - language key
  - 16x16 PNG texture
- `door` 使用 `DoubleHighBlockItem`，避免门被当成普通 `BlockItem`。
- schema、validator、LLM planner、MockLLMClient、auditor、capability matrix、RAG knowledge 和 eval coverage 均已更新。
- `generate --build --audit "Create a ruby mod with ruby block variants."` 已验证通过。
- package metadata 更新到 `2.8.0`。

价值：

- 让方块内容从“只有 cube”扩展到更接近真实建筑玩法的常见方块链。
- 这类能力主要靠 JSON、注册、模型、loot 和 recipe，风险低但展示效果明显。
- 后续可以继续升级到自定义方块行为、方块实体或更复杂建筑/装饰系统。
