## V2.2 Eval Coverage Metrics

目标：把已有 benchmark 从“运行 prompt 并统计成功率”升级为更细的能力覆盖评测。

完成内容：

- 扩展 `EvalCase`，新增 `expected_categories` 和 `repeat_request`。
- 扩展 `EvalCaseResult`，记录期望能力分类命中 / 缺失、agent trace artifact 是否存在、repeat modify 幂等性结果。
- eval 现在会检查 `.agent/agent-run.json`、`.agent/agent-run.md`、`.agent/agent-decisions.md`、`.agent/prompt-trace.json` 是否真实生成。
- 新增聚合指标：`expected_category_match_rate`、`category_expectation_success_rate`、`agent_artifacts_complete_rate`、`repeat_modify_success_rate`。
- 默认 eval case 覆盖 basic ruby、right-click heal、right-click effect、food effect、sword ignite、ore worldgen、modify add behavior、modify add worldgen。
- `MockLLMClient` 支持 modify 场景下的 ruby charm behavior patch。
- `capabilities` 增加 `eval_coverage_metrics` 能力。
- package metadata 更新到 `2.2.0`。

价值：

- 评测报告不只说明“是否成功”，还能说明“覆盖了哪些能力”。
- 对简历和面试更友好：可以展示 feature expectation、capability coverage、agent trace、modify idempotency 四类工程指标。
- 后续更换 planner、LLM provider 或 generator 时，可以用同一套 benchmark 做稳定对比。
