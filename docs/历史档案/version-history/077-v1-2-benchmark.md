## V1.2 评测与 Benchmark

目标：给 Agent 工作流增加可量化、可重复的评测层。

完成内容：

- 新增 `evaluator.py`。
- 新增 CLI 命令：
  - `eval`
- 增加默认离线 benchmark case，覆盖：
  - 基础红宝石生成
  - 行为型物品生成
  - 右键药水效果物品生成
  - 食物效果生成
  - 矿石自然生成
  - modify 给已有矿石添加 worldgen
- 复用 V1.1 的 `AgentOrchestrator`，没有另开一条生成路径。
- 增加 expected feature 检查，会读取最终 `.agent/modspec.json`，确认期望 feature 是否真的存在。
- 增加聚合指标：
  - 总体成功率
  - 期望 feature 命中率
  - planner 成功率
  - audit 成功率
  - 可选 build 成功率
  - generated files 数量统计
  - modify added / updated / skipped 统计
- 写入 eval artifacts：
  - `workspace/eval-runs/<run-id>/.agent/eval-cases.json`
  - `workspace/eval-runs/<run-id>/.agent/eval-report.json`
  - `workspace/eval-runs/<run-id>/.agent/eval-report.md`
- 新增 `docs/验证与可靠性/eval.md`。
- 更新 README 和 test matrix 中的 V1.2 命令。

价值：

- 让项目从“单次 smoke test 能跑通”升级到“可以批量评测 Agent 表现”。
- 后续更换 planner、LLM provider 或 generator 逻辑时，可以用同一套 benchmark 做对比。
- 对简历和面试叙事更有说服力：项目不只是接入 LLM 和多 Agent，还具备结构化评测指标。
