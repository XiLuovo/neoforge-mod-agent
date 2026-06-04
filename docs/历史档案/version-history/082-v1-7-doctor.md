## V1.7 Doctor 集成质量门禁

目标：让环境诊断不只作为单独命令存在，而是进入默认可靠性链路，成为 `quality-gate` 的第一步。

完成内容：

- 将 doctor 集成进 `quality-gate`，新增默认检查：
  - `doctor_environment`
- 默认质量门禁现在会运行：
  - `doctor --no-java --json`
  - Python `compileall`
  - `unittest discover`
  - `print-schema --json`
  - `test-examples --no-build --json`
  - mock LLM eval smoke
  - 可选 build smoke
- 增加 quality gate 参数：
  - `--no-doctor`
  - `--doctor-java`
  - `--doctor-strict`
- 更新 GitHub Actions artifact 上传路径，额外上传：
  - `workspace/quality-gate-runs/ci-quality-gate/.agent/**`
  - `workspace/doctor-runs/ci-quality-gate-doctor/.agent/**`
- 更新 CI workflow 测试，确认 CI 没有禁用 doctor。
- 更新 quality gate 测试，覆盖 doctor pass / skip 行为。
- 更新 README、CI 文档、doctor 文档、quality gate 文档和测试矩阵。
- 更新 package metadata 到 `1.7.0`。

价值：

- 让本地和 CI 的可靠性检查更完整：如果是环境问题，会先在 doctor 阶段暴露出来。
- 默认质量门禁跳过 Java 诊断，保持 CI 快速稳定。
- 需要强验证时，仍可使用 `quality-gate --doctor-java --build-smoke`。
