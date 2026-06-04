## V2.5 Web Demo Dashboard

目标：把现有 CLI / agent / eval / RAG / capability 报告汇总成一个可直接打开的本地 Web 展示页，方便简历项目和面试演示。

完成内容：

- 新增 `dashboard.py`。
- 新增 CLI 命令：
  - `dashboard`
- 默认输出：
  - `workspace/dashboard-runs/<run-id>/index.html`
  - `workspace/dashboard-runs/<run-id>/.agent/dashboard-data.json`
  - `workspace/dashboard-runs/<run-id>/.agent/dashboard-report.md`
- Dashboard 默认汇总：
  - capability matrix
  - V2.4 RAG knowledge query
  - showcase 多 Agent 演示
  - eval smoke 摘要
  - 原始 artifact 链接
- 新增 `--no-showcase`，可快速生成 capabilities + RAG 页面。
- capability matrix 增加：
  - `web_dashboard`
- package metadata 更新到 `2.5.0`。

价值：

- 让项目从“能跑的 CLI 工具”更像“能展示的 Agent 产品”。
- 面试时可以直接打开 HTML 讲完整链路。
- 继续保持离线、无前端依赖、无服务启动的轻量形态。
