# CI / GitHub Actions

CI 的职责是防止基础回归，不是替代本地 RC1 smoke 或 Minecraft runtime 验收。

## 当前策略

默认 CI 应覆盖：

```text
doctor
-> compile
-> unittest
-> schema/examples
-> lightweight eval/golden checks
-> doc link guard
```

对于 RC1 相关改动，本地仍建议额外跑：

```powershell
python -m unittest tests.test_doc_links
python -m unittest discover tests
py -3.11 -m compileall src
```

## Evidence

CI 可以上传 `.agent` 报告，例如：

```text
workspace/quality-gate-runs/<run-id>/.agent/
workspace/doctor-runs/<run-id>/.agent/
```

## RC1 边界

- CI 默认不一定运行 Gradle build smoke。
- CI 不做 Minecraft runtime 自动化验收。
- 如果要验证真实 agent 行为，使用 `agent bench` 生成 trace-backed benchmark evidence。
