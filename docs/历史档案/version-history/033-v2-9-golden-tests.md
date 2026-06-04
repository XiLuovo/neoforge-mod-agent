## V2.9 自动验收增强 / Golden Tests

目标：把现有内容生成能力沉淀成可重复执行的 golden snapshot 验收，让项目可靠性从 build/audit/eval 继续升级到“金标生成快照”。

完成内容：

- 新增 `golden_tests.py`。
- 新增 CLI 命令：
  - `golden-test`
- 默认 golden case 覆盖：
  - basic ruby item
  - ruby block
  - ruby charm behavior
  - ruby food effect
  - ruby sword ignite
  - ruby ore worldgen
  - ruby tool set
  - ruby armor set
  - ruby block variants
- Golden checks 会验证：
  - generation success
  - audit success
  - expected feature ids
  - generated file count lower bound
  - expected generated paths
  - generation-summary 是否记录关键路径
  - item/block model、recipe、worldgen、pack.mcmeta、texture manifest 等关键 JSON 字段
- `quality-gate` 默认加入 `golden_tests`，并保留 `--no-golden` 快速跳过选项。
- `quality-gate --eval-limit` 默认从 2 提升到 10，用于覆盖 V2.6 tool/armor 与 V2.8 block variants。
- `eval` 指标增加 content category coverage 汇总。
- `dashboard` 新增 Content Coverage 区块和 metrics。
- capability matrix 新增：
  - `golden_tests`
  - `golden_snapshot_checks`
  - `content_coverage_dashboard`
- package metadata 更新到 `2.9.0`。

价值：

- 让项目更像成熟 Agent 工程，而不是只堆生成能力。
- 能快速回答“当前能力到底有没有被自动验收覆盖”。
- 让 quality gate、eval 和 dashboard 形成更完整的可靠性闭环。
