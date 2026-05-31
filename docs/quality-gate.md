# V1.4 Quality Gate

> 文档定位：这是质量门禁专项材料，不是主学习入口。需要理解一键串联 compile、test、eval、failure lab 和 repair eval 时再读。

V1.4 新增了统一的 `quality-gate` 命令，用来组合开发中常用的快速可靠性检查。

它的目标是让提交前、演示前、继续加功能前，都能用一条命令确认项目没有明显回归：

```text
quality-gate
  -> environment doctor preflight
  -> Python compile check
  -> unittest regression suite
  -> ModSpec schema smoke
  -> example spec regression
  -> eval smoke benchmark
  -> golden snapshot tests
  -> optional Gradle build smoke
```

## 运行默认质量门

```powershell
Set-Location <repo-root>
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli quality-gate --json
```

默认质量门刻意保持轻量，除非显式传入参数，否则不会运行较慢的 Gradle build。

从 V2.9 开始，默认质量门会额外运行 deterministic golden tests。这些检查会生成一组标准 no-build workspace，并验证生成文件数量、预期路径、ModSpec feature id、关键 JSON 字段以及 audit 是否成功：

```powershell
py -3.11 -m agent.cli golden-test --json
```

Since V1.7, the default gate also runs an environment doctor preflight:

```powershell
py -3.11 -m agent.cli doctor --no-java --json
```

Java diagnostics are skipped inside the default quality gate to keep CI and lightweight local checks stable. Use `--doctor-java` when you want the gate to include `java -version` diagnostics.

## Stable Run Name

```powershell
py -3.11 -m agent.cli quality-gate --run-name v14-quality-gate-smoke --json
```

Reports are written to:

```text
workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.json
workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.md
workspace/quality-gate-runs/<run-id>/.agent/logs/
```

## Optional Build Smoke

Gradle build smoke is slower, so it is opt-in:

```powershell
py -3.11 -m agent.cli quality-gate --build-smoke --json
```

This generates a minimal ruby workspace with `--build --audit`.

## Skipping Checks

During development, individual checks can be skipped:

```powershell
py -3.11 -m agent.cli quality-gate --no-unittest --no-examples --json
```

Available skip flags:

- `--no-doctor`
- `--no-compile`
- `--no-unittest`
- `--no-schema`
- `--no-examples`
- `--no-eval`
- `--no-golden`

Doctor-specific flags:

- `--doctor-java`
- `--doctor-strict`

## JSON Output

The JSON output includes:

- `success`
- `run_id`
- `passed_count`
- `failed_count`
- `skipped_count`
- per-check command, status, return code, duration, stdout log path, and stderr log path
- report paths

## GitHub Actions

V1.5 wires this command into GitHub Actions:

```text
.github/workflows/quality-gate.yml
```

The CI workflow runs the default fast gate and uploads `.agent` reports. It does not enable `--build-smoke` by default.

Since V1.7, CI also uploads doctor artifacts from:

```text
workspace/doctor-runs/ci-quality-gate-doctor/.agent/**
```

See [ci.md](ci.md) for details.

## 中文说明

V1.4 的核心目标是把常用验证步骤整合成一个“一键质量门禁”。

以前我们有很多单独命令：

- `unittest`
- `print-schema`
- `test-examples`
- `eval`
- 可选 `generate --build --audit`

现在可以用一个命令串起来：

```powershell
py -3.11 -m agent.cli quality-gate --json
```

V1.7 开始，质量门禁默认会先跑一遍环境诊断：

```powershell
py -3.11 -m agent.cli doctor --no-java --json
```

默认跳过 Java 诊断，是为了让 CI 和快速本地检查更稳。如果希望质量门禁也检查 `java -version`，可以加：

```powershell
py -3.11 -m agent.cli quality-gate --doctor-java --json
```

这对项目展示很有用，因为它说明这个 Agent 项目不是“跑一次 demo”，而是有一套稳定的质量检查流程。默认不跑 Gradle build，是为了保证速度；如果要做更强验证，再加：

```powershell
py -3.11 -m agent.cli quality-gate --build-smoke --json
```

V1.5 已经把这个命令接入 GitHub Actions。CI 默认运行快速质量门禁，并上传 `.agent` 报告；默认不跑 `--build-smoke`，避免 CI 过慢。详细说明见 [ci.md](ci.md)。
