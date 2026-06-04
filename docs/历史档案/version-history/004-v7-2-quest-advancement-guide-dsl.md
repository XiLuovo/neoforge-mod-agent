## V7.2 Quest / Advancement / Guide DSL

目标：把 V7 玩法线变成玩家能看见的目标，生成任务链、advancement、引导文本和 Patchouli-style guidebook 结构，让演示时不再需要用户猜玩法路线。

完成内容：

- package metadata 更新到 `7.2.0`。
- `ModSpec` 新增 `quest` / `quests`，支持 `target_progression`、`guidebook_id`、`category` 和结构化 `tasks`。
- 新增 `QuestGuideGenerator`，输出 `.agent/quest-report.json`、`.agent/quest-report.md`、`.agent/guidebook.md`。
- 生成 `data/<modid>/advancement/<quest>/<task>.json`，覆盖 obtain、craft、mine、machine、kill、dimension、structure 和 milestone 任务类型。
- 生成 Patchouli-style `book.json`、category JSON 和 entry JSON，作为 guidebook 数据结构证据。
- validator 检查 quest id、task id、task type、parent 链、目标 progression 引用和任务目标引用。
- audit / generation-summary / manual checklist / capabilities / rules planner / mock LLM 均接入 V7.2。
- 新增示例 `examples/quest_guide_gameplay_loop.json` 和文档 `docs/规格与生成/quest-guide-dsl.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_quest_guide_dsl tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\quest_guide_gameplay_loop.json --workspace-name v72-quest-smoke --overwrite --audit --no-build --json
```

边界：

- V7.2 是数据驱动任务 / 成就 / 指南结构，不是完整自定义任务运行时。
- Patchouli-style JSON 会被生成，但不会自动添加 Patchouli Gradle 依赖。
- 复杂剧情触发、跨维度脚本和任意 Java 逻辑仍属于后续受控扩展。
