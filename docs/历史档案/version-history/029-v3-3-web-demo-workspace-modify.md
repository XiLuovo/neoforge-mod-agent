## V3.3 Web Demo Workspace 管理与 Modify 交互

目标：把 V3.2 的交互式 Web Demo 从“生成一个新项目”扩展为“管理并修改已有生成项目”，形成更完整的演示闭环。

完成内容：

- `web_demo.py` 新增 workspace 管理 API：
  - `GET /api/workspaces`
  - `GET /api/workspace?name=<workspace>`
- `web_demo.py` 新增 modify API：
  - `POST /api/modify`
- Web Demo 页面新增：
  - workspace 下拉选择
  - 刷新 workspace
  - 读取当前 workspace
  - modify request 输入框
  - modify 执行按钮
  - Workspace 结果页
  - Diff / Merge 结果页
- modify 后展示：
  - `added`
  - `updated`
  - `skipped`
  - `ModSpec diff`
  - audit/build 结果
  - agent trace
- `web-demo --smoke --json` 现在会验证：
  - generate
  - workspace list
  - workspace load
  - modify
  - audit
  - diff
- capability matrix 新增 `web_demo_modify`。
- package metadata 更新到 `3.3.0`。

价值：

- 项目演示从“自然语言生成新 Mod”升级为“自然语言持续维护已有 Mod”。
- 面试时可以现场演示：先生成 ruby，再对已有 workspace 增量添加 ruby_charm，并展示 merge/diff/trace。
- 继续保持核心边界：自然语言 / LLM -> ModSpec patch -> deterministic generator -> audit/build/repair。
