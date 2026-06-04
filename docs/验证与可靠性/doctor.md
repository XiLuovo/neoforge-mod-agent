# V1.6 Environment Doctor

> 文档定位：这是环境诊断专项材料，不是主学习入口。需要确认本机环境、Java、Gradle 和项目布局时再读。

V1.6 adds a deterministic environment diagnostic command:

```powershell
py -3.11 -m agent.cli doctor --json
```

The goal is to help a new user, reviewer, or CI maintainer quickly answer:

```text
Is this checkout ready to run the NeoForge Mod Agent?
```

## What Doctor Checks

The default doctor run checks:

- Python version is at least `3.11`
- project root exists
- `src/neoforge_agent` exists
- compatibility CLI `src/agent/cli.py` exists
- `pyproject.toml` exists
- `README.md` exists
- NeoForge template directory exists
- template `build.gradle` exists
- template `settings.gradle` exists
- template `gradlew.bat` exists
- template Gradle wrapper properties exist
- template `src/main` exists
- template Java toolchain version can be detected
- workspace root exists or can be created later
- workspace parent is writable
- local `PYTHONPATH` includes `src`
- docs and GitHub Actions workflow files exist
- OpenAI-compatible LLM provider configuration is complete enough for real LLM runs
- `java -version` can run

If `java -version` reports a version lower than the configured template target, doctor emits a warning rather than a hard failure. Gradle toolchains may still provide the required JDK during builds.

Since V3.6, doctor also checks real LLM configuration without calling the network. It reports `llm.openai_compatible` as `pass` when the required provider variables are available, or `warning` when real LLM runs are not configured yet. The check only records `api_key_present`; it does not write the actual API key.

Supported environment variables:

```powershell
$env:NEOFORGE_AGENT_LLM_BASE_URL = "https://api.openai.com/v1"
$env:NEOFORGE_AGENT_LLM_API_KEY = "<your-api-key>"
$env:NEOFORGE_AGENT_LLM_MODEL = "<your-model>"
$env:NEOFORGE_AGENT_LLM_TIMEOUT_SECONDS = "60"
$env:NEOFORGE_AGENT_LLM_MAX_RETRIES = "2"
```

`OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TIMEOUT_SECONDS`, and `OPENAI_MAX_RETRIES` are also accepted for compatibility.

## Reports

Doctor writes reports under:

```text
workspace/doctor-runs/<run-id>/.agent/doctor-report.json
workspace/doctor-runs/<run-id>/.agent/doctor-report.md
```

Use a stable run name when you want repeatable paths:

```powershell
py -3.11 -m agent.cli doctor --run-name local-doctor --json
```

## Options

Skip Java diagnostics:

```powershell
py -3.11 -m agent.cli doctor --no-java --json
```

Treat warnings as failure:

```powershell
py -3.11 -m agent.cli doctor --strict --json
```

## Recommended Usage

For local setup:

```powershell
Set-Location L:\projects\MinecraftMods\idea
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli doctor --json
```

Before demos, combine doctor with the quality gate:

```powershell
py -3.11 -m agent.cli doctor --json
py -3.11 -m agent.cli quality-gate --json
```

Since V1.7, the default quality gate already includes a doctor preflight with Java diagnostics disabled:

```powershell
py -3.11 -m agent.cli quality-gate --json
```

Use this when you want quality gate to include Java diagnostics too:

```powershell
py -3.11 -m agent.cli quality-gate --doctor-java --json
```

## 中文说明

V1.6 的 `doctor` 命令是一个本地环境诊断工具。它不生成 Mod，也不修改已有 workspace，只负责检查当前 checkout 是否具备运行项目的基础条件。

常用命令：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli doctor --json
```

它会检查：

- Python 版本
- 项目目录结构
- `src/neoforge_agent`
- `src/agent/cli.py`
- NeoForge 模板目录
- Gradle wrapper
- workspace 目录与写入权限
- `PYTHONPATH`
- README / docs / CI workflow
- `java -version`

报告会写入：

```text
workspace/doctor-runs/<run-id>/.agent/doctor-report.json
workspace/doctor-runs/<run-id>/.agent/doctor-report.md
```

如果只是想跳过 Java 检查：

```powershell
py -3.11 -m agent.cli doctor --no-java --json
```

如果希望 warning 也让命令失败：

```powershell
py -3.11 -m agent.cli doctor --strict --json
```

V1.7 开始，默认 `quality-gate` 已经会先运行一遍 doctor preflight，但会跳过 Java 检查：

```powershell
py -3.11 -m agent.cli quality-gate --json
```

如果希望质量门禁也检查 Java，可以运行：

```powershell
py -3.11 -m agent.cli quality-gate --doctor-java --json
```

这个命令适合放在 README 的“环境确认”步骤里，也适合在面试或项目展示时说明：项目不仅能生成 Mod，还有环境诊断、质量门禁、CI、测试和评测。
