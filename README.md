# NeoForge Mod Agent

NeoForge Mod Agent 是一个面向 Minecraft NeoForge 的受控 LLM 代码生成项目：自然语言先进入 `ModSpec-first` 规划，再由确定性 generator、可审查补丁通道、audit/build/repair 和 replay 证据链生成并验证 Mod workspace。

当前主线：

```text
Natural language
-> ModSpec-first routing
-> deterministic generation / optional Direct Code Lane
-> audit / build / repair
-> replay / eval / harvest evidence
```

后续升级路线是 `Capability Harvest Loop`：稳定 `generate` 覆盖不了的需求，先在 Free-Code Lab 的隔离 workspace 中实验；通过 audit、build 和人工 runtime checklist 后，再把成功模式整理回稳定 `ModSpec`、DSL、generator、audit 和测试。

## Quick Start

PowerShell：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name demo-ruby --overwrite --no-build --json
py -3.11 -m agent.cli audit demo-ruby --json
py -3.11 -m unittest discover -s tests -v
```

Free-Code Lab 实验入口：

```powershell
py -3.11 -m agent.cli agent lab-generate "<request>" --from-workspace <workspace> --run-name <name> --build --json
py -3.11 -m agent.cli harvest-report --run-name <name> --json
```

## Core Docs

如果目标是先学懂项目，按这个顺序读：

1. [docs/README.md](docs/README.md)：文档分层入口。
2. [docs/project-limitations.md](docs/project-limitations.md)：当前边界、不足和后续方向。
3. [docs/architecture.md](docs/architecture.md) / [docs/agent-workflow.md](docs/agent-workflow.md)：架构和 agent workflow 真相源。
4. [docs/direct-code-lane.md](docs/direct-code-lane.md) / [docs/capability-harvest-loop.md](docs/capability-harvest-loop.md)：Direct Code Lane 和 Free-Code Lab 机制真相源。

更多公开文档从 [docs/README.md](docs/README.md) 进入。

## Key Boundaries

- 默认路径仍是 `ModSpec-first`：LLM 产出结构化意图，最终 Java / JSON / PNG / resources 主要由 deterministic generator 生成。
- Direct Code Lane 不是无边界 coding agent；它只接受结构化 `write_file` / `replace_text` workspace 补丁，并经过 review、snapshot、audit、Gradle build 和 rollback evidence。
- Free-Code Lab 是实验隔离区，不修改原 workspace，也不自动修改本工具源码；成功样本必须人工整理后才能固化进 generator。
- `minecraft.neoforge` 是当前唯一稳定 domain；`spring.api`、`unity.component` 仍是 planned 扩展方向。
- `mock` provider 用于离线稳定学习和回归；真实 LLM 能力需要单独用 real provider 和 `--require-llm` 验证。
- `audit` / `build` 不能替代 Minecraft runtime 自动化测试。

## Current Status

- 本地回归基线：`py -3.11 -m unittest discover -s tests -v` 通过 163 个 unittest case。
- 当前重点不是继续堆普通玩法功能，而是把 Free-Code Lab 的成功实验沉淀成可复现 generator 能力。
- 学习优先级高于展示优先级：先能讲清数据流、模块职责、证据文件和失败排查路径。
