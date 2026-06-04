## V7 Progression / Gameplay Loop DSL

目标：让生成器不只生成一堆 feature，而是能表达一条玩家可游玩的成长路线：矿物 -> 材料 -> 机器加工 -> 装备 / 道具 -> 实体掉落 -> 结构战利品 -> 维度推进。

完成内容：

- package metadata 更新到 `7.0.0`。
- `ModSpec` 新增 `progression` / `progressions`，覆盖 stage、link、entry/end stage、requires/provides/unlocks/evidence。
- 新增 `ProgressionGenerator`，输出 `.agent/progression-report.json` 和 `.agent/progression-report.md`。
- validator 检查 progression id、stage type、link 引用、入口到终点可达性、循环提示，以及 evidence / requires / provides / unlocks 是否能解析到已有 ModSpec 对象或外部资源。
- audit / generation-summary / manual checklist / capabilities / rules planner / mock LLM 均接入 V7。
- 新增示例 `examples/progression_gameplay_loop.json` 和文档 `docs/规格与生成/progression-dsl.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_progression_dsl tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\progression_gameplay_loop.json --workspace-name v70-progression-smoke --overwrite --audit --no-build --json
```

边界：

- V7 是玩法线 DSL 和证据报告，不是任意任务系统、成就树、剧情脚本或 Java patch。
- stage evidence 必须尽量引用现有 ModSpec feature；未知引用会进入 warning 和 report 的 missing references。
- 实际机器配方、维度门逻辑、复杂剧情推进仍属于后续扩展。
