# NeoForge Mod Agent

NeoForge Mod Agent 是一个面向 Minecraft NeoForge 的受控 LLM 代码生成项目：自然语言先进入 `ModSpec-first` 规划，再由确定性 generator、可审查补丁通道、audit/build/repair 和 replay 证据链生成并验证 Mod workspace。

当前主线（Phase 0-2.5）：
```text
Natural language
-> ModSpec-first routing
-> deterministic generation / optional Direct Code Lane
-> audit / build / real tool-calling repair/refine
-> replay / eval / harvest evidence
```

后续升级路线是 `Capability Harvest Loop`：当稳定 `generate` 覆盖不了需求时，先在 Free-Code Lab 的隔离 workspace 中实验；通过 audit、build 和人工 runtime checklist 后，再把成功模式整理回稳定 `ModSpec`、DSL、generator、audit 和测试。

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

先看这些当前主线文档：

1. [docs/总览/README.md](docs/总览/README.md)
2. [docs/Agent与能力/README.md](docs/Agent与能力/README.md)
3. [docs/验证与可靠性/README.md](docs/验证与可靠性/README.md)
4. [docs/规格与生成/README.md](docs/规格与生成/README.md)

历史报告、旧 test matrix 和旧 version history 已归档到 [docs/历史档案/README.md](docs/历史档案/README.md)。更多公开文档从 [docs/README.md](docs/README.md) 进入。

## Key Boundaries

- 默认路径仍然是 `ModSpec-first`。
- Direct Code Lane 仍然是受控补丁通道，不是无边界 coding agent。
- Free-Code Lab 是实验隔离区，不改原 workspace，也不自动回写 generator。
- `minecraft.neoforge` 仍然是当前唯一稳定 domain。
- `audit` / `build` 不能替代真实 Minecraft runtime 自动测试。
