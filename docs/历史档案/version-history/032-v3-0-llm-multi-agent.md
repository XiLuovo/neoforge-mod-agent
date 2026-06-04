## V3.0 真实 LLM / Multi-Agent 强化版

目标：把已有 `agent generate/modify` 能力升级成更适合简历展示的多角色 Agent 闭环，同时继续坚持 LLM 不直接写 Java/JSON/PNG，只输出 `ModSpec` 或 repair plan。

完成内容：

- 标准化多角色链路：`planner_agent`、`reviewer_agent`、`executor_agent`、`auditor_agent`、`repair_agent`。
- `reviewer_agent` 增加结构化 `review_checks`，记录 ModSpec schema 边界、feature presence、validator error/warning 和内容覆盖提示。
- `repair_agent` 增加 deterministic `repair_plan`，把 build/audit 失败映射成可读的下一步修复动作。
- 新增 agent trace summary artifact：`.agent/agent-trace-summary.json` 和 `.agent/agent-trace-summary.md`。
- dashboard 新增 `Multi-Agent Trace` 区块，展示每个 agent role 的输入、输出、决策理由和 prompt trace 数量。
- capability matrix 新增 `multi_agent_trace`、`multi_agent_dashboard`、`repair_plan`。
- eval 指标把 agent trace summary 纳入 artifact 完整性检查。
- package metadata 更新到 `3.0.0`。

价值：

- 面试时可以讲清楚“多 Agent 如何分工”，而不是只说调用了 LLM。
- dashboard 可以直接展示每个 agent 的输入、输出和决策理由。
- 真实 LLM 接入仍然被 ModSpec 边界约束，不破坏确定性生成和 audit/build/repair 兜底。
