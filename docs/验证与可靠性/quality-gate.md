# Quality Gate

`quality-gate` 是本地快速可靠性检查入口。RC1 的最终 agent 成功仍由具体 workspace 的 audit/build gate 决定；`quality-gate` 用于提交前确认项目测试和基础工具没有回退。

## Command

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli quality-gate --json
```

默认 gate 保持轻量，适合本地和 CI：

```text
doctor preflight
-> Python compile check
-> unittest regression suite
-> schema smoke
-> example spec regression
-> eval smoke
-> golden snapshots
```

## Optional Build Smoke

Gradle build 比较慢，需要显式开启：

```powershell
py -3.11 -m agent.cli quality-gate --build-smoke --json
```

## Skip Flags

开发中可以跳过单项检查：

```powershell
py -3.11 -m agent.cli quality-gate --no-unittest --no-examples --json
```

常用 flag：

- `--no-doctor`
- `--no-compile`
- `--no-unittest`
- `--no-schema`
- `--no-examples`
- `--no-eval`
- `--no-golden`
- `--doctor-java`
- `--doctor-strict`

## Outputs

```text
workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.json
workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.md
workspace/quality-gate-runs/<run-id>/.agent/logs/
```

## RC1 边界

`quality-gate` 不是 `agent bench` 的替代品。它不一定运行真实 tool-calling develop/repair case；需要评测真实 agent 行为时，使用：

```powershell
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```
