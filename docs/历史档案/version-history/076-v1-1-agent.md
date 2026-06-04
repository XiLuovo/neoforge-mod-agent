## V1.1 轻量 Agent 编排

目标：在不破坏确定性生成的前提下，加入适合简历展示的多 Agent 工作流。

完成内容：

- 新增 `agent_models.py`。
- 新增 `agent_orchestrator.py`。
- 新增 CLI 命令组：
  - `agent generate`
  - `agent modify`
- 增加显式角色 trace：
  - `planner_agent`
  - `reviewer_agent`
  - `executor`
  - `auditor_agent`
  - `repair_agent`
- agent 默认使用 `llm + mock`，方便离线演示。
- 复用现有 OpenAI-compatible LLM client。
- 写入 agent artifacts：
  - `.agent/agent-run.json`
  - `.agent/agent-run.md`
  - 需要 repair analysis 时写入 `.agent/agent-repair-plan.json`
  - 需要 repair analysis 时写入 `.agent/agent-repair-plan.md`
- 增加 `docs/Agent与能力/agent-workflow.md`。
- 更新 README 和 test matrix 中的 V1.1 命令。
- 验证 agent generate 和 agent modify 均可通过 build 与 audit。

价值：

- 将项目升级成更清晰的 LLM-assisted Agent 系统。
- 展示多角色编排能力，同时不牺牲可靠性。
- 形成适合简历和面试讲解的亮点：
  - 结构化中间表示
  - 受约束的 LLM planning
  - 确定性执行
  - 项目结构审计
  - build 验证
  - repair-oriented failure analysis
