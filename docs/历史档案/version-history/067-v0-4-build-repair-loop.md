## V0.4 Build Repair Loop

目标：让构建失败变得可诊断、可修复，而不是只看到一段 Gradle 报错。

完成内容：

- 增加 CLI 里的 Gradle build 执行能力。
- 将 build 日志记录到 `.agent/logs`。
- 分类常见构建错误，例如 missing symbol、bad import、constructor mismatch、resource JSON error 和 dependency issue。
- 生成 repair artifacts：
  - `.agent/debug-context.md`
  - `.agent/fix-request.md`
  - `.agent/suspected-errors.json`
- 增加 `repair` 命令和 build repair 集成。

价值：

- 为生成链路建立第一层可靠性闭环。
- 让失败信息可以交给人类开发者或后续 repair agent 使用。
