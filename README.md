# NeoForge Mod Agent

NeoForge Mod Agent 是一个面向 Minecraft NeoForge Mod 开发的受控 Coding Agent。它把自然语言需求转成 `ModSpec`，再由确定性生成器产出 Java、JSON、资源文件和 `.agent` 证据，而不是让 LLM 自由修改整个工程。

项目重点不是“聊天式生成代码”，而是一个可检查、可修复、可回放的领域工程闭环：

```text
Natural language
-> ModSpec planner
-> deterministic NeoForge generator
-> controlled tool-calling repair/refine loop
-> reviewer + audit/build gate
-> trace-backed benchmark and .agent evidence
```

## What It Does

- 从自然语言生成 NeoForge 26.1 mod workspace。
- 支持 item、block、ore/worldgen、recipe、machine、entity、progression、quest guide、resource/texture 等结构化能力。
- 用 `ModSpec` 和 DSL 限制 LLM 输出边界，Java / JSON / PNG 由生成器落地。
- 通过受控工具循环读取文件、检索本地 NeoForge 知识、应用结构化 patch、运行 audit/build。
- 为每次运行写出 `.agent/` 证据：planner trace、tool-call trace、RAG citation、reviewer report、audit report、patch report 和 rollback evidence。
- 用 benchmark / RAG ablation / repair suite 评估生成、修复和可靠性。

## Quick Start

PowerShell：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)

# Check local environment
py -3.11 -m agent.cli doctor --no-java --json

# Run the current offline development e2e smoke with mock LLM and no Gradle build
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --run-name public-smoke-decomposed-e2e --json

# Run the broader offline showcase flow
py -3.11 -m agent.cli showcase --run-name development-e2e-smoke --llm-provider mock --no-build --json

# Optional stricter smoke: run Gradle build for generated workspaces
py -3.11 -m agent.cli showcase --run-name public-build-smoke --llm-provider mock --build --json

# Run the test suite
py -3.11 -m unittest discover -s tests -v
```

`--no-build` 适合快速演示；需要 Gradle 编译证据时改用 `--build`。如果使用真实 LLM provider，请配置 `NEOFORGE_AGENT_LLM_*` 或 OpenAI-compatible 环境变量，并用 `--require-llm` / `--require-real` 区分真实 provider 成功和 fallback 成功。

## Example Workflows

```powershell
# Development e2e eval: generate + modify + audit + trace evidence
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --json

# Build smoke: generate/modify/e2e showcase with Gradle build enabled
py -3.11 -m agent.cli showcase --run-name public-build-smoke --llm-provider mock --build --json

# Agent benchmark with RAG on/off ablation
py -3.11 -m agent.cli agent bench --suite examples/agentic_rag_ablation.json --llm-provider mock --rag-ablation --audit --no-build --json
```

Generated workspaces and reports are written under `workspace/`. Key run evidence lives in `.agent/` folders.

当前公开 smoke 基线：`public-polish-decomposed-e2e-20260627` 完成 2/2 cases，audit 2/2，expected feature/category match rate 均为 `1.0`，repeat modify 1/1。当前 build smoke `public-build-smoke-clean` 记录为 5 passed / 0 failed / 1 skipped（quality gate 未请求），doctor 22 pass / 0 warning，development e2e build 2/2，并生成 `progression_mod-0.1.0.jar` 和 `ruby_mod-0.1.0.jar`。这些结果使用 mock provider；build smoke 证明 Gradle 编译层通过，但仍不是 Minecraft runtime 自动验收。脱敏冻结报告、来源 run 和 SHA-256 见 [Portfolio Evidence](evidence/portfolio/README.md)。

## Real Provider Evidence

公开 smoke 默认使用 mock provider，是为了让 CI 和本地演示稳定复现；真实 provider 路径单独统计，避免把 fallback、provider 错误、schema 错误、audit/build 和 runtime 证据混在一起。

下列 decomposed planner 数据来自历史本地实验记录；对应原始 run 当前尚未进入公开 evidence 包，因此只能作为待复验结果，不能作为仓库内可独立复现的主指标。公开包中的 `real-provider-13case-historical` 是另一轮 non-decomposed run，不能替代下表证据。

| Evidence | Recorded result | Boundary |
| --- | --- | --- |
| Decomposed planner A/B | 5 real-provider generate cases 中，decomposed planner `5/5` strict success、audit `5/5`、fallback `0`；相比 full-schema planner，provider-reported total tokens 从 `254,310` 降到 `5,875`，约降 `97.7%`，平均延迟 `44.7s -> 25.1s` | Full-schema batch 曾有 1 个空输出 case，单独重试后通过，因此按 `5/5*` 记录稳定性边界 |
| Decomposed 13-case smoke | `12/13` strict real LLM success，audit `12/13`，fallback `0`，total tokens `22,904` | 唯一失败是 `ruby_realm_world_structure`，暴露 dimension / biome / structure / loot 复合世界生成的 planner/schema 覆盖边界 |
| Build follow-up | 代表性 real-provider generated workspaces 补充 Gradle build smoke，保留 jar 和 build evidence | 这证明 workspace 级 build gate，不等于 Minecraft 客户端/服务端 runtime 验收 |

更多统计口径见 [Real LLM Evidence Summary](docs/Agent与能力/real-llm-evidence-summary.md)。没有显式 manual runtime evidence 的 case 一律不能写成 Minecraft runtime 通过。

当前包版本是 `8.5.0`；文档中的 RC1/RC2/RC3 表示作品集能力阶段，不是独立的 Python package version。

## Evidence And Safety

| Area | How this project handles it |
| --- | --- |
| LLM planning | LLM output is constrained to `ModSpec`, structured patch intent, or tool actions. |
| Code generation | Java, JSON, resources, recipes, loot tables, tags, and textures are generated deterministically. |
| Repair/refine | The agent uses controlled tools such as RAG retrieval, file read/search, structured patch, audit, and build. |
| Review | LLM reviewer checks coverage, risk, and evidence sufficiency, but cannot override audit/build gates. |
| Evidence | `.agent/` stores run traces, prompt traces, tool-call traces, reviewer reports, audit/build reports, patch reports, and rollback evidence. |
| Benchmarks | `agent bench` records real agent traces and can compare RAG on/off behavior. |

Important boundary: audit/build proves workspace-level correctness. It is not the same as Minecraft client/server runtime validation unless explicit manual runtime evidence is attached.

## Repository Layout

```text
src/neoforge_agent/      Agent runtime, planner, generator, auditor, repair, benchmark
src/agent/               CLI compatibility entrypoint
examples/                ModSpec examples, eval suites, repair/RAG benchmark cases
templates/neoforge-26.1/ NeoForge workspace template
tests/                   Unit and regression tests
docs/                    Architecture, agent workflow, generation specs, validation, showcase docs
workspace/               Local generated workspaces and evidence, not long-term source assets
```

## Documentation

- [Architecture](docs/总览/architecture.md)
- [Agent Workflow](docs/Agent与能力/agent-workflow.md)
- [Tool Calling Contract](docs/Agent与能力/tool-calling-contract.md)
- [ModSpec](docs/规格与生成/modspec.md)
- [Validation And Reliability](docs/验证与可靠性/README.md)
- [Real LLM Evidence Summary](docs/Agent与能力/real-llm-evidence-summary.md)
- [Showcase Guide](docs/发布与展示/showcase.md)
- [Screenshots And Visual Evidence](docs/发布与展示/screenshots.md)
- [Public Release Checklist](docs/发布与展示/public-release-checklist.md)

## Project Boundaries

- This is a `minecraft.neoforge` controlled Coding Agent, not a generic unrestricted coding agent.
- RAG is context and citation evidence for planning/repair/review; it is not the main product.
- Direct Code Lane is experimental opt-in and must not bypass ModSpec, structured patch, audit/build, or evidence gates.
- Claims in README, reports, or demos must match the evidence actually generated.
