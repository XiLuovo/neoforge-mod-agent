## V1.8 Showcase 展示报告

目标：增加一个适合 GitHub、简历和面试展示的一键 demo flow，把当前 Agent 系统能力汇总成一份报告。

完成内容：

- 新增 `showcase.py`。
- 新增 CLI 命令：
  - `showcase`
- 默认 showcase 会运行：
  - 环境诊断 doctor，不检查 Java
  - mock LLM 多角色 `agent generate`
  - mock LLM 多角色 `agent modify`
  - 离线 eval smoke benchmark
  - 可选 quality gate，传入 `--quality-gate` 时执行
- 展示用 workspace 隔离在：
  - `workspace/showcase-runs/<run-id>/workspaces/`
- 展示报告写入：
  - `workspace/showcase-runs/<run-id>/.agent/showcase-report.json`
  - `workspace/showcase-runs/<run-id>/.agent/showcase-report.md`
- 增加参数：
  - `--run-name`
  - `--planner`
  - `--llm-provider`
  - `--eval-limit`
  - `--build`
  - `--quality-gate`
- 新增 `docs/发布与展示/showcase.md`。
- 新增 showcase runner 测试和 CLI 参数解析测试。
- 更新 README 和 test matrix。
- 更新 package metadata 到 `1.8.0`。

价值：

- 形成一份适合放到 GitHub、简历或面试演示里的项目展示报告。
- 展示项目已经不是单点 demo，而是一套完整 Agent 系统：doctor、LLM planner、多 Agent 编排、modify、audit、eval 和可选 quality gate。
- 默认不跑 Gradle build，保证 showcase 足够快；需要强验证时可以显式加 `--build`。
