# V1.8 Showcase Reports

> 文档定位：这是 showcase 报告专项材料，不是主学习入口。需要理解一键展示报告时再读。

V1.8 adds a portfolio-friendly showcase command:

```powershell
py -3.11 -m agent.cli showcase --json
```

The command runs a curated offline demo flow and writes a consolidated report. It is designed for GitHub READMEs, internship demos, and interview walkthroughs.

## What Showcase Runs

The default showcase flow runs:

- environment doctor preflight without Java diagnostics
- mock LLM multi-role `agent generate`
- mock LLM multi-role `agent modify`
- offline eval smoke benchmark
- optional quality gate when `--quality-gate` is passed

Default showcase runs do not call Gradle build, so they stay fast and deterministic.

## Artifacts

Reports are written under:

```text
workspace/showcase-runs/<run-id>/.agent/showcase-report.json
workspace/showcase-runs/<run-id>/.agent/showcase-report.md
```

Generated demo workspaces are isolated under:

```text
workspace/showcase-runs/<run-id>/workspaces/
```

## Recommended Commands

Fast offline showcase:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli showcase --run-name v18-showcase-smoke --json
```

Include the default fast quality gate:

```powershell
py -3.11 -m agent.cli showcase --run-name v18-showcase-full --quality-gate --json
```

Attempt Gradle build for the agent generate/modify showcase cases:

```powershell
py -3.11 -m agent.cli showcase --run-name v18-showcase-build --build --json
```

## 中文说明

V1.8 的 `showcase` 命令是为了“项目展示”服务的。它不是新增游戏玩法，而是把当前已经完成的能力串成一条可复现 demo：

- 环境诊断 doctor
- mock LLM 多 Agent 生成
- mock LLM 多 Agent 修改已有项目
- eval smoke 评测
- 可选 quality-gate

常用命令：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli showcase --run-name v18-showcase-smoke --json
```

报告位置：

```text
workspace/showcase-runs/<run-id>/.agent/showcase-report.json
workspace/showcase-runs/<run-id>/.agent/showcase-report.md
```

展示用 workspace 会隔离在：

```text
workspace/showcase-runs/<run-id>/workspaces/
```

这条命令很适合用于简历项目说明：它能证明项目不是单点 demo，而是已经具备 Agent 编排、结构化审计、评测和质量门禁这一整套工程链路。
