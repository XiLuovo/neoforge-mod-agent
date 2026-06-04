## V2.3 Eval Compare

目标：让 V2.2 的 benchmark 指标可以做两次运行之间的回归对比。

完成内容：

- 新增 `eval_compare.py`。
- 新增 CLI 命令：
  - `eval-compare <baseline> <candidate>`
- baseline 和 candidate 支持：
  - eval report JSON 路径
  - eval run 目录
  - eval run 名称
- 对比并监控这些 rate 指标：
  - `success_rate`
  - `expected_feature_match_rate`
  - `expected_category_match_rate`
  - `planning_success_rate`
  - `audit_success_rate`
  - `build_success_rate`
  - `agent_artifacts_complete_rate`
  - `prompt_trace_present_rate`
  - `repeat_modify_success_rate`
- 对比每个 eval case 是否从 pass 退步为 fail。
- 生成对比报告：
  - `workspace/eval-comparisons/<run-id>/.agent/eval-compare-report.json`
  - `workspace/eval-comparisons/<run-id>/.agent/eval-compare-report.md`
- `capabilities` 增加 `eval_compare` 能力。
- package metadata 更新到 `2.3.0`。

价值：

- V2.2 解决“单次评测有没有覆盖足够信息”，V2.3 解决“这次升级有没有比上次退步”。
- 适合后续作为 release 前的 benchmark regression gate。
- 对简历叙事更完整：项目不仅有 Agent、eval 和 quality gate，还有跨版本评测对比能力。
