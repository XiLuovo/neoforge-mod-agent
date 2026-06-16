# NeoForge Mod Agent

NeoForge Mod Agent 是一个面向 Minecraft NeoForge 的受控 Coding Agent：自然语言先进入 `ModSpec-first` 规划，再由确定性 generator 生成 Java/JSON/resource baseline，随后通过修改、audit/build gate、trace/report 和受控 repair/refine loop 验证结果。当前 RC3-candidate 的推荐展示主线是端到端开发闭环；RAG/repair benchmark 已阶段性冻结，作为可靠性和可解释性补充。

当前主线（RC3-candidate development e2e showcase）：
```text
Natural language
-> planner / feature plan / ModSpec
-> deterministic generator baseline
-> Java / JSON / resource artifacts
-> modify existing workspace
-> audit/build gate
-> trace-backed eval / showcase report
-> repair benchmark as reliability supplement
-> replayable evidence
```

RC1 之后，项目的重点不再是“一次性生成更多文件”，而是把生成、修改、审查、评测和证据链串成可复现的领域 agent 工作流。RC2 补强了 RAG 和 repair trace；RC3-candidate 把 provider error、repair logic failure、gate failure 和 managed-file regeneration 分开记录。现在推荐先展示 development e2e，再把 3-case RAG smoke、18-case repair suite 和 seeded holdout 作为可靠性证据补充。后续升级路线仍然可以使用 `Capability Harvest Loop`：当稳定 `generate` 覆盖不了需求时，先在隔离 workspace 中实验；通过 audit、build 和人工 runtime checklist 后，再把成功模式整理回稳定 `ModSpec`、DSL、generator、audit 和测试。

## Quick Start

PowerShell：
```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli showcase --run-name development-e2e-smoke --llm-provider mock --no-build --json
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --llm-provider mock --audit --no-build --json
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --json
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name demo-ruby-rc1 --no-build --json
py -3.11 -m agent.cli agent repair demo-ruby-rc1 --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
py -3.11 -m agent.cli audit demo-ruby-rc1 --json
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
py -3.11 -m agent.cli agent bench --suite examples/agentic_rag_ablation.json --llm-provider mock --rag-ablation --audit --json
py -3.11 -m agent.cli agent bench --suite examples/agent_benchmark_repair_18.json --llm-provider mock --rag-ablation --audit --no-build --json
py -3.11 -m agent.cli agent bench --repair-holdout --holdout-seed demo --holdout-limit 8 --llm-provider mock --rag-ablation --audit --no-build --json
py -3.11 -m unittest discover -s tests -v
```

`examples/agent_development_e2e.json` 是当前推荐的端到端开发 suite：从自然语言生成 ruby progression loop，覆盖 ore/worldgen、compressor machine、ruby tools、progression report；再从已有 ruby mod 追加 worldgen，并用 repeat modify 验证同一需求不会重复添加。`examples/agentic_rag_ablation.json` 是 3-case 快速 smoke；`examples/agent_benchmark_repair_18.json` 是固定完整 repair suite，覆盖 metadata、asset/resource、data/worldgen 和 generated-code audit 故障；`--repair-holdout` 会按 seed 生成不同 material/mod/resource 名的随机 holdout。当前推荐展示路径是 `showcase`、`eval --cases examples/agent_development_e2e.json`，repair/RAG benchmark 作为可靠性补充。

`--planner decomposed` 是 Decomposed Planner v1：先把自然语言拆成 `feature-plan.json`，再按 `item/ore/machine/tool/sword/recipe/progression` 生成小 JSON，组合回 `ModSpec` 后继续走 generator、audit/build 和 report。运行后可在 workspace 的 `.agent/decomposed-planner/` 查看 `feature-plan.json`、`feature-jsons.json`、`composed-modspec-raw.json` 和坏输出记录；它不是 RAG/Milvus 扩展，也不是让 LLM 接管完整 Java generator。

Post-merge evidence snapshot：Decomposed Planner v1 已补 real-provider hardening，能把 real provider 拆碎的 progression fragments 稳定合并回 `ruby_progression`，并清理空/非法 behavior schema drift。当前可引用证据包括 real provider decomposed eval `postmerge-real-decomposed-fragment-fix2`（2/2 cases success，audit 2/2，expected feature/category match rate 均为 `1.0`，但使用 `--no-build`）、strict real provider build smoke `real-decomposed-build-smoke`（`openai-compatible` + decomposed + `--require-llm` + `--build`，audit 246 checks passed，Gradle build `exit_code=0`，生成 `ruby_progression-0.1.0.jar`）、mock decomposed build smoke `main-postmerge-build-smoke`（audit 280 checks passed，Gradle build `exit_code=0`，生成 jar）和 full unittest `213 tests OK`。这些证据证明 workspace 级 planning/audit/build gate，不等于 Minecraft runtime 自动验收。

## Public Release Package

发布脚本默认不把整个 `workspace/` 打进公开包，只从固定 showcase、develop/repair/bench 名称收集可展示 evidence。打包前先生成 development e2e、develop/repair 和 bench 示例产物；RAG ablation evidence 可作为额外展示材料单独保留：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli showcase --run-name release-development-e2e --llm-provider mock --no-build --json
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --llm-provider mock --audit --no-build --json
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name rc1-release-smoke --no-build --json
py -3.11 -m agent.cli agent repair rc1-release-smoke --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
py -3.11 -m agent.cli agent bench --run-name rc1-release-bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
py -3.11 -m agent.cli agent bench --run-name rc2-rag-ablation --suite examples/agentic_rag_ablation.json --llm-provider mock --rag-ablation --audit --json
py -3.11 -m agent.cli agent bench --run-name repair-18-mock --suite examples/agent_benchmark_repair_18.json --llm-provider mock --rag-ablation --audit --no-build --json
py -3.11 -m agent.cli agent bench --run-name repair-holdout-demo --repair-holdout --holdout-seed release-demo --holdout-limit 8 --llm-provider mock --rag-ablation --audit --no-build --json
.\scripts\create_public_release.ps1
```

如果默认示例名已经存在，优先换一个 workspace/run 名，并把它们传给 `-Rc1WorkspaceName` 和 `-Rc1BenchmarkRunName`；只有明确要重建旧目录时才给 CLI 加 `--overwrite`。完整 18-case evidence 是可选的严肃评测材料，不是打包脚本的默认必需输入；缺失的示例产物会记录在 `release-manifest.md` 的 Missing Optional Evidence 中。

## Core Docs

先看这些当前主线文档：

1. [docs/总览/rc1-learning-guide.md](docs/总览/rc1-learning-guide.md)
2. [docs/总览/README.md](docs/总览/README.md)
3. [docs/Agent与能力/README.md](docs/Agent与能力/README.md)
4. [docs/Agent与能力/rag.md](docs/Agent与能力/rag.md)
5. [docs/验证与可靠性/benchmark-report.md](docs/验证与可靠性/benchmark-report.md)
6. [docs/验证与可靠性/README.md](docs/验证与可靠性/README.md)
7. [docs/规格与生成/README.md](docs/规格与生成/README.md)
8. [docs/发布与展示/showcase.md](docs/发布与展示/showcase.md)

历史报告、旧 test matrix 和旧 version history 已归档到 [docs/历史档案/README.md](docs/历史档案/README.md)。更多公开文档从 [docs/README.md](docs/README.md) 进入。

## Key Boundaries

- 这不是通用无限制 coding agent，而是 NeoForge 领域内的受控 Coding Agent。
- LLM 不直接无边界写完整项目；默认路径仍然是 `ModSpec-first`，最终文件由确定性 generator、受控结构化 patch 和 workspace 安全边界管理。
- generator、audit 和 build 仍然是确定性核心；LLM reviewer 负责审查覆盖、风险和建议，但不能替代 audit/build gate。
- RAG citation 是 planner/repair 的领域上下文和可回放证据，不是项目主线，也不是正确性的最终证明；最终仍要看 audit/build 和必要的 runtime 验证。
- Direct Code Lane 和 structured patch 是受控补丁通道，不是自由 diff 通道。
- `minecraft.neoforge` 仍然是当前唯一稳定 domain。
- 当前状态是 RC3-candidate，不是正式 RC3 通过；real provider 不通时不能把 provider failure 说成 agent repair failure。
- `audit` / `build` 不能替代真实 Minecraft runtime 自动测试；进游戏验证仍然需要人工或未来额外 harness。
