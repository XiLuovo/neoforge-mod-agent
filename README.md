# NeoForge Mod Agent

NeoForge Mod Agent 是一个面向 Minecraft NeoForge 的受控 Coding Agent：自然语言先进入 `ModSpec-first` 规划，再由确定性 generator 生成 baseline workspace，随后通过真实 tool-calling repair/refine loop、RAG、结构化 patch、LLM reviewer、audit/build gate 和 trace-backed benchmark 验证结果。

当前主线（RC1 / Phase 0-4 已完成）：
```text
Natural language
-> planner / ModSpec
-> deterministic generator baseline
-> real tool-calling repair/refine loop
-> RAG / read files / structured patch / audit
-> LLM reviewer
-> audit/build gate
-> trace-backed benchmark
-> replayable evidence
```

RC1 之后，项目的重点不再是“一次性生成更多文件”，而是把生成、修复、审查、评测和证据链串成可复现的领域 agent 工作流。后续升级路线仍然可以使用 `Capability Harvest Loop`：当稳定 `generate` 覆盖不了需求时，先在隔离 workspace 中实验；通过 audit、build 和人工 runtime checklist 后，再把成功模式整理回稳定 `ModSpec`、DSL、generator、audit 和测试。

## Quick Start

PowerShell：
```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name demo-ruby-rc1 --no-build --json
py -3.11 -m agent.cli agent repair demo-ruby-rc1 --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
py -3.11 -m agent.cli audit demo-ruby-rc1 --json
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
py -3.11 -m unittest discover -s tests -v
```

兼容生成、Direct Code Lane 和 Free-Code Lab 仍可作为辅助能力讲解；RC1 推荐展示路径是 `agent develop`、`agent repair` 和 `agent bench`。

## Public Release Package

发布脚本默认不把整个 `workspace/` 打进公开包，只从固定 RC1 smoke 名称收集当前主线 evidence。打包前先生成 develop/repair 和 bench 示例产物：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name rc1-release-smoke --no-build --json
py -3.11 -m agent.cli agent repair rc1-release-smoke --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
py -3.11 -m agent.cli agent bench --run-name rc1-release-bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
.\scripts\create_public_release.ps1
```

如果默认示例名已经存在，优先换一个 workspace/run 名，并把它们传给 `-Rc1WorkspaceName` 和 `-Rc1BenchmarkRunName`；只有明确要重建旧目录时才给 CLI 加 `--overwrite`。缺失的示例产物会记录在 `release-manifest.md` 的 Missing Optional Evidence 中。

## Core Docs

先看这些当前主线文档：

1. [docs/总览/rc1-learning-guide.md](docs/总览/rc1-learning-guide.md)
2. [docs/总览/README.md](docs/总览/README.md)
3. [docs/Agent与能力/README.md](docs/Agent与能力/README.md)
4. [docs/验证与可靠性/README.md](docs/验证与可靠性/README.md)
5. [docs/规格与生成/README.md](docs/规格与生成/README.md)
6. [docs/发布与展示/agent-rc1-showcase.md](docs/发布与展示/agent-rc1-showcase.md)

历史报告、旧 test matrix 和旧 version history 已归档到 [docs/历史档案/README.md](docs/历史档案/README.md)。更多公开文档从 [docs/README.md](docs/README.md) 进入。

## Key Boundaries

- 这不是通用无限制 coding agent，而是 NeoForge 领域内的受控 Coding Agent。
- LLM 不直接无边界写完整项目；默认路径仍然是 `ModSpec-first`，最终文件由确定性 generator、受控结构化 patch 和 workspace 安全边界管理。
- generator、audit 和 build 仍然是确定性核心；LLM reviewer 负责审查覆盖、风险和建议，但不能替代 audit/build gate。
- Direct Code Lane 和 structured patch 是受控补丁通道，不是自由 diff 通道。
- `minecraft.neoforge` 仍然是当前唯一稳定 domain。
- `audit` / `build` 不能替代真实 Minecraft runtime 自动测试；进游戏验证仍然需要人工或未来额外 harness。
