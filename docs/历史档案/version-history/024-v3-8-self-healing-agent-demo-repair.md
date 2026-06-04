## V3.8 Self-Healing Agent Demo / Repair 可视化

目标：把 V3.7 的 repair agent 安全自动修复能力从“隐藏在 JSON 里”推进到“Web Demo 和 Dashboard 中可讲、可看、可追踪”。

完成内容：

- `web_demo.py` 的 generate / modify payload 新增 `repair` 和 `self_healing` 摘要。
- `GET /api/workspace` 现在会读取：
  - `.agent/agent-repair-plan.json`
  - `.agent/repair-loop-report.json`
  - 并返回 `repair_plan`、`repair_loop`、`self_healing`
- Web Demo 页面新增 `Self-Healing` 标签页，展示：
  - `Repair Agent`
  - `Repair Loop`
  - `repair_needed`
  - `repair_executed`
  - `repair_success`
  - root causes
  - repair attempts
  - repair artifact 路径
- `dashboard.py` 新增 `Self-Healing Repair` 区块，汇总 repair runs、needed、executed、success 和 attempts。
- Dashboard artifact 链接新增 agent repair plan 和 repair loop report。
- Capability Matrix 新增：
  - `web_demo_self_healing`
  - `dashboard_repair_summary`
  - `self_healing_demo`
- package metadata 更新到 `3.8.0`。

价值：

- 面试演示时可以直接讲清楚“Agent 如何发现生成项目损坏，并在安全边界内恢复受控文件”。
- repair 不再只是命令行或 JSON artifact，而是进入可视化演示链路。
- 仍然保持核心原则：LLM 不直接写 Java / JSON / PNG，只输出 `ModSpec` 或 repair plan；修复动作由 deterministic repair loop 执行。
