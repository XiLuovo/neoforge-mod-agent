## V3.2 Web Demo Dashboard 交互化

目标：把 V2.5/V3.1 的 dashboard 从“静态报告页”升级成“可操作演示台”，方便实习简历、面试和现场 demo。

完成内容：

- 新增 `web_demo.py`。
- 新增 CLI 命令：
  - `web-demo`
- `web-demo` 使用 Python 标准库 HTTP server，不引入前端框架或第三方依赖。
- 页面支持输入 prompt。
- 页面支持选择 planner：
  - `rules`
  - `mock-llm`
  - `real-llm`
  - `auto-mock`
  - `auto-real`
- 后端复用 `AgentOrchestrator.run_generate`，仍然保持：
  - LLM 只输出 `ModSpec`
  - Java/JSON/PNG 由 deterministic generator 生成
  - audit/build/repair 继续兜底
- 页面展示：
  - `ModSpec`
  - generated files
  - audit result
  - build result
  - eval result
  - agent steps / decisions / prompt traces
- 新增 `web-demo --smoke --json`，用于不启动长驻服务的快速验证。
- capability matrix 新增 `interactive_web_demo`。
- package metadata 更新到 `3.2.0`。

价值：

- 面试时不再只能打开一堆 JSON 或静态 HTML，而是可以现场输入需求并展示完整 Agent 链路。
- 真实 LLM、mock LLM、rules planner 的差异可以在同一个页面里演示。
- 保持项目核心边界不变：自然语言 / LLM -> ModSpec -> deterministic generator -> audit/build/eval/repair。

本文记录项目从最早的红宝石物品 Demo，到当前 V3.1 RAG 知识库增强工作流的演进。
