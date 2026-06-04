# V1.5 CI / GitHub Actions

> 文档定位：这是 CI 专项材料，不是主学习入口。需要理解 GitHub Actions 和本地质量门禁关系时再读。

V1.5 adds a GitHub Actions workflow that runs the existing V1.4 `quality-gate` command on every push to `main`, every pull request, and manual workflow dispatch.

The workflow lives at:

```text
.github/workflows/quality-gate.yml
```

## What CI Runs

The default CI job runs on `windows-latest` with Python `3.11` and sets:

```text
PYTHONPATH=src
```

It executes:

```powershell
python -m agent.cli quality-gate --run-name ci-quality-gate --json
```

That means CI runs the fast default quality gate:

- environment doctor preflight without Java diagnostics
- Python compile checks
- `unittest discover`
- `print-schema --json`
- `test-examples --no-build --json`
- mock LLM eval smoke

## What CI Does Not Run By Default

CI does not pass `--build-smoke` by default.

That is intentional: Gradle and Minecraft/NeoForge build smoke can be slower and more sensitive to runner environment details. The stronger build smoke remains available locally:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli quality-gate --build-smoke --json
```

## Artifacts

The workflow uploads quality gate reports even if the gate fails:

```text
workspace/quality-gate-runs/ci-quality-gate/.agent/**
workspace/doctor-runs/ci-quality-gate-doctor/.agent/**
```

Important files include:

- `quality-gate-report.json`
- `quality-gate-report.md`
- `doctor-report.json`
- `doctor-report.md`
- `logs/*.stdout.log`
- `logs/*.stderr.log`

## Local CI Equivalent

Before pushing, run the same command locally:

```powershell
Set-Location L:\projects\MinecraftMods\idea
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli quality-gate --run-name ci-quality-gate-local --json
```

## 中文说明

V1.5 的目标是让项目更适合放到 GitHub 上展示：不只“本地能跑”，还要有一条清晰的 CI 验证链路。

新增的 workflow 文件是：

```text
.github/workflows/quality-gate.yml
```

它会在以下场景运行：

- push 到 `main`
- pull request
- 手动触发 `workflow_dispatch`

CI 默认执行：

```powershell
python -m agent.cli quality-gate --run-name ci-quality-gate --json
```

也就是说，它复用 V1.4 的质量门禁能力，并且从 V1.7 开始会先运行 doctor 环境诊断。CI 默认会自动运行 doctor、compile、unittest、schema、examples 和 mock eval smoke。

默认不跑 `--build-smoke`。这是为了让 GitHub Actions 更快、更稳定；NeoForge/Gradle build 可以作为本地更强验证：

```powershell
py -3.11 -m agent.cli quality-gate --build-smoke --json
```

CI 会上传 `.agent` 报告目录，方便失败时查看：

```text
workspace/quality-gate-runs/ci-quality-gate/.agent/**
workspace/doctor-runs/ci-quality-gate-doctor/.agent/**
```

这样 V1.5 之后，项目展示时可以讲清楚：

- 有 LLM / Agent 生成链路
- 有 deterministic generator
- 有 audit / eval / unittest
- 有一键 quality gate
- 有 GitHub Actions CI 把质量门禁自动化
