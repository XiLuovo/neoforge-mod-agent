## V3.7 Repair Agent 增强

目标：让 repair agent 不再只是“失败后写一份修复建议”，而是在明确安全边界内自动执行确定性修复。

完成内容：

- `AgentOrchestrator` 接入 `AutoRepairRunner`。
- `agent generate` / `agent modify` 在 audit 或 build 失败时，会自动执行一次 safe repair loop。
- 修复动作仍然只有安全动作：
  - 从 `.agent/modspec.json` 读取真相源
  - 重生成受控 Java / JSON / PNG / lang / model / worldgen / pack metadata
  - 重新运行本次请求过的 audit/build 检查
- `repair_agent` payload 新增：
  - `repair_executed`
  - `repair_success`
  - `repair_loop`
  - `repair_loop_report_json_path`
  - `repair_loop_report_md_path`
- `.agent/agent-repair-plan.md` 会展示 repair-loop 执行摘要。
- 如果安全修复成功，agent run 最终可以恢复为 `success=true`。
- capability matrix 新增：
  - `repair_agent_execute`
  - `safe_repair_execution`
- package metadata 更新到 `3.7.0`。

价值：

- audit/build 发现受控生成文件缺失或损坏时，Agent 可以自己恢复，不需要用户手动再跑 `repair-loop`。
- 仍然不让 LLM 直接改源码，风险低，适合简历中讲“可验证、可恢复的 Agent 工程闭环”。
- 修复全过程有 `.agent` artifacts，可用于复盘和 Web/Dashboard 展示。
