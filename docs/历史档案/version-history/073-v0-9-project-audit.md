## V0.9 结构化验收 / Project Audit

目标：检查 Gradle build 无法覆盖的生成结构一致性问题。

完成内容：

- 新增 `auditor.py`。
- 新增 `audit` CLI 命令。
- 读取 `.agent/modspec.json` 和 `.agent/generation-summary.json`。
- 检查基础项目文件。
- 检查 `generation-summary.json` 中记录的生成文件是否真实存在。
- 检查 item、block、ore、food、sword、recipe、behavior 和 worldgen 输出。
- 写入 audit artifacts：
  - `.agent/audit-report.json`
  - `.agent/audit-report.md`
- 增加负向测试：删除生成的 model 文件后 audit 能失败并报告错误。

价值：

- 增加确定性的项目结构审计能力。
- 覆盖 Gradle build 不一定能发现的问题，例如缺 model、缺 lang key、缺 worldgen 文件、generated file 记录过期等。
