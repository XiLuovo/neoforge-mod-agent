# Environment Doctor

`doctor` 是环境诊断工具。它不生成 Mod，不修改 workspace，也不调用真实 LLM；只检查当前 checkout 是否具备运行项目的基础条件。

## Command

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli doctor --no-java --json
```

如果要检查 Java：

```powershell
py -3.11 -m agent.cli doctor --json
```

## 检查内容

- Python 版本；
- 项目路径；
- `src` / `tests` / `examples` 是否可见；
- 可选 Java 诊断；
- OpenAI-compatible provider 配置是否存在；
- 不泄漏 API key，只记录是否配置。

## Outputs

```text
workspace/doctor-runs/<run-id>/.agent/doctor-report.json
workspace/doctor-runs/<run-id>/.agent/doctor-report.md
```

## RC1 边界

doctor 只能说明环境可运行，不能说明 agent 生成、修复或 benchmark 成功。RC1 展示时通常先跑 doctor，再跑 `agent develop`、`agent repair` 和 `agent bench`。
