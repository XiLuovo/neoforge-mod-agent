## V1.9 Capability 能力矩阵

目标：导出一份结构化能力矩阵，作为当前项目能力的统一真相源。

完成内容：

- 新增 `capabilities.py`。
- 新增 CLI 命令：
  - `capabilities`
- 能力矩阵覆盖：
  - 项目元信息
  - 核心工作流
  - 生成内容类型
  - 行为模板
  - worldgen 支持
  - planner 与 LLM 边界
  - 可靠性和验证层
  - 当前限制
- 能力矩阵产物写入：
  - `workspace/capability-runs/<run-id>/.agent/capabilities.json`
  - `workspace/capability-runs/<run-id>/.agent/capabilities.md`
- 新增 `docs/总览/capabilities.md`。
- 新增 capability catalog 测试和 CLI 参数解析测试。
- 更新 README 和 test matrix。
- 更新 package metadata 到 `1.9.0`。

价值：

- 让 README、showcase、简历和面试讲解可以引用同一份结构化能力清单。
- 更容易把项目解释成一套完整系统，而不是一堆零散命令。
- 为后续自动化生成项目介绍、版本说明或展示页打基础。
