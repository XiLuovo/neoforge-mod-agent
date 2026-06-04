## V1.6 环境诊断 Doctor

目标：增加一个本地 preflight 诊断命令，让新环境、新 clone 或面试展示前更容易确认项目是否具备运行条件。

完成内容：

- 新增 `doctor.py`。
- 新增 CLI 命令：
  - `doctor`
- Doctor 会检查：
  - Python 版本
  - 项目目录结构
  - 兼容入口 `src/agent/cli.py`
  - NeoForge 模板目录
  - 模板里的 Gradle wrapper 文件
  - 模板 Java toolchain 版本
  - workspace 目录和父目录写入权限
  - `PYTHONPATH`
  - 关键文档
  - GitHub Actions workflow
  - `java -version`
- 增加 `--no-java`，可跳过 Java 检查。
- 增加 `--strict`，可把 warning 也视为失败。
- 写入 doctor artifacts：
  - `workspace/doctor-runs/<run-id>/.agent/doctor-report.json`
  - `workspace/doctor-runs/<run-id>/.agent/doctor-report.md`
- 新增 `docs/验证与可靠性/doctor.md`。
- 新增 doctor 单元测试和 CLI 参数解析测试。
- 更新 README 和 test matrix 中的 V1.6 命令。
- 更新 package metadata 到 `1.6.0`。

价值：

- 让别人拿到项目后，可以先运行 `doctor` 判断环境问题，而不是直接在 generate/build 里撞报错。
- 继续增强工程可靠性叙事：项目不仅有 Agent、eval、tests、quality gate、CI，还有本地环境诊断。
- Doctor 是只读诊断，不会生成 Mod，也不会改已有 workspace，适合安全地作为第一步检查。
