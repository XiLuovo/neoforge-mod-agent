# 术语表

| 术语 | 说明 |
| --- | --- |
| RC1 | 基础 agent 闭环阶段：Phase 0-4 已完成，具备真实 tool-calling develop/repair、LLM reviewer 和 trace-backed bench。 |
| RC2 | Agentic RAG 阶段：补强 RAG policy、query rewrite、多跳检索、citation trace、reviewer evidence sufficiency 和 RAG ablation。 |
| NeoForge Mod Agent | 面向 Minecraft NeoForge 的受控 Coding Agent。 |
| ModSpec-first | 先把自然语言目标收敛为结构化规格，再由确定性 generator 落地。 |
| deterministic generator | Python 生成器，负责可复现地产出 Java、JSON、PNG 和资源文件。 |
| tool-calling loop | LLM 在 planner 之外按 schema 选择工具，系统执行后把 observation 放回下一轮。 |
| structured patch | 受控补丁计划，只允许限定 operation 和 workspace 内路径。 |
| snapshot | patch 前保存的文件快照。 |
| rollback evidence | 描述如何恢复 patch 的报告和快照路径。 |
| RAG | 本地 NeoForge 知识检索层，为 planner、repair/refine 和 reviewer 提供上下文。RC2 中它还记录检索决策和 citation 使用情况。 |
| LLM reviewer | 输出结构化审查 JSON 的 reviewer，审查覆盖和风险，但不替代 audit/build。 |
| audit/build gate | deterministic 最终验收门禁。 |
| trace-backed benchmark | 从真实 agent trace、reviewer report 和 audit/build result 计算指标的 benchmark。 |
| replayable evidence | `.agent/` 中可复盘的 planner、tool call、reviewer、audit/build、patch 和 rollback 证据。 |
| Direct Code Lane | 辅助/兼容的受控 workspace patch 通道，不是当前推荐主线。 |
