## V2.0 Agent Workflow Trace

目标：把已有 `agent generate` / `agent modify` 从轻量步骤编排升级为可追踪的多角色 Agent 工作流。

完成内容：

- 新增 `AgentDecision` 和 `AgentPromptTrace` 数据结构。
- `agent-run.json` 现在包含：
  - `steps`
  - `decisions`
  - `prompt_traces`
- 每次 workspace agent run 额外写入：
  - `.agent/agent-decisions.md`
  - `.agent/prompt-trace.json`
- `llm_planner` 的 artifacts 现在记录 system prompt，并写入：
  - `.agent/planner-system-prompt.txt`
- `agent generate` 记录 planner / reviewer / executor / auditor / repair 的决策。
- `agent modify` 记录 context_loader / planner / reviewer / executor / auditor / repair 的决策。
- 修复 mock LLM modify 被 existing ModSpec 污染的问题：modify 模式优先只根据 Change Request 生成 patch。
- `capabilities` 增加：
  - `agent_prompt_trace`
  - `agent_decision_log`
- package metadata 更新到 `2.0.0`。
- 新增 `docs/Agent与能力/agent-workflow.md`。

价值：

- 面试叙事更清晰：项目现在不是单纯的生成器，而是可追踪的多角色 LLM 开发 Agent。
- 调试更容易：可以从 `prompt-trace.json` 看到 planner 输入、LLM 原始 JSON、normalized ModSpec 和 warnings。
- 复盘更容易：可以从 `agent-decisions.md` 看到每个角色的决策理由。
