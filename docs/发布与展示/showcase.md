# Development E2E Showcase

当前推荐展示路径是“受控 NeoForge Coding Agent 的端到端开发闭环”，不是普通一次性 generator，也不是 RAG demo。

展示重点：

```text
Natural language
-> ModSpec / feature plan
-> deterministic generator
-> generated Java / JSON / resources
-> audit/build gate
-> tool-calling repair/refine evidence
-> reviewer / trace / benchmark report
```

## 展示顺序

1. 运行 `showcase`，证明 doctor、generate、modify、eval smoke 和 development e2e 都能落盘报告。
2. 单独运行 `eval --cases examples/agent_development_e2e.json`，展示自然语言如何进入 ModSpec，再由 generator 产出 workspace，并通过 audit gate 和 trace/report 验收。
3. 打开 eval report，重点看 `expected_feature_match_rate`、`expected_category_match_rate`、`audit_success_rate`、`repeat_modify_success_rate`。
4. 如需可靠性补充，再展示 3-case RAG ablation smoke、18-case repair suite 或 seeded holdout。
5. 明确边界：CLI showcase 默认只证明 workspace audit/build 层；人工 Minecraft runtime evidence 作为独立验证层记录，不能由 showcase 自动推导。

## 推荐命令

当前公开 audit smoke：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --run-name public-smoke-decomposed-e2e --json
```

最近一次本地公开 smoke `public-polish-decomposed-e2e-20260627` 结果：2/2 cases success，audit 2/2，expected feature/category match rate 均为 `1.0`，repeat modify 1/1，trace/prompt/agent artifacts 完整。该结果使用 mock provider 和 `--no-build`，只能作为离线 audit-level evidence。

当前公开 build smoke：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli showcase --run-name public-build-smoke --llm-provider mock --build --json
```

最近一次本地 build smoke `public-build-smoke-clean` 结果：showcase 5 passed / 0 failed / 1 skipped（quality gate 未请求），doctor 22 pass / 0 warning / 0 fail，development e2e 2/2 success，audit 2/2，Gradle build 2/2，生成 `progression_mod-0.1.0.jar` 和 `ruby_mod-0.1.0.jar`。该结果证明 generated workspace 的 Gradle build gate 通过，仍不等于 Minecraft runtime 自动验收。脱敏冻结报告见 [Portfolio Evidence](../../evidence/portfolio/README.md)。

真实 provider 证据建议作为单独一层展示，不和 mock / CI smoke 混写。下表是历史实验记录；对应 decomposed 原始 run 尚未进入公开 evidence 包，在补齐前应标为待复验，不作为公开主指标：

| Evidence | Result | 展示边界 |
|---|---:|---|
| Decomposed planner A/B | 5-case real-provider strict `5/5`，audit `5/5`，fallback `0`；相比 full-schema planner，provider-reported total tokens `254,310 -> 5,875`，约降 `97.7%`，平均延迟 `44.7s -> 25.1s` | full-schema batch 原始运行有 1 个空输出 case，单独重试后通过，因此说明成 `5/5*` 更准确 |
| Decomposed 13-case smoke | `12/13` strict real LLM success，audit `12/13`，fallback `0`，total tokens `22,904` | 唯一失败 `ruby_realm_world_structure` 是 dimension / biome / structure / loot 复合世界生成的 planner/schema 覆盖边界 |
| Representative build follow-up | 代表性 real-provider generated workspaces 有 Gradle build smoke 和 jar evidence | 只能证明 workspace 级 build gate，不证明 Minecraft runtime 自动验收 |

推荐讲法：mock 证明工程链路可复现；real provider 证明模型输出能进入 ModSpec、deterministic generator 和 audit gate；build follow-up 证明代表性 workspace 可编译；runtime 需要额外 manual runtime evidence。

Fast mock showcase:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli showcase --run-name codex-development-e2e-smoke --llm-provider mock --no-build --json
```

Development e2e eval:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --json
```

Decomposed planner smoke:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --json
```

Cross-feature modify stress:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --cases examples/decomposed_modify_cross_feature_stress.json --planner decomposed --llm-provider mock --audit --no-build --json
```

Build smoke when local Gradle/JDK environment is ready:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli showcase --run-name public-build-smoke --llm-provider mock --build --json
```

`--no-build` 适合快速本地演示。`--build` 更适合正式验收，但耗时更长，也仍然不等于 Minecraft 客户端/服务端进游戏验收。

## Evidence Snapshot 口径

可以引用的 evidence 类型包括：

- unit tests / compileall / diff check
- mock development e2e eval
- decomposed planner eval
- real provider eval，前提是实际使用 `openai-compatible` 且启用 `--require-llm` 或 `--require-real`
- strict build smoke，前提是报告中有 Gradle build log 和 `exit_code=0`
- cross-feature modify stress，前提是保留每步 `.agent/eval-modify-steps/<step>/` evidence
- benchmark report 和 evidence-chain report

表述必须和 evidence 匹配：

- mock provider 成功不能写成真实 provider 稳定通过。
- `--no-build` eval 不能写成 Gradle build 通过。
- Gradle build 通过不能写成 Minecraft runtime 自动验收。
- manual smoke 的 build follow-up 不能包装成 full eval build。

## 推荐检查的文件

```text
workspace/showcase-runs/<run-id>/.agent/showcase-report.json
workspace/eval-runs/<run-id>/.agent/eval-report.md
workspace/eval-runs/<run-id>/.agent/eval-report.json
workspace/<workspace>/.agent/agent-run.md
workspace/<workspace>/.agent/audit-report.md
workspace/<workspace>/.agent/logs/gradle-build.json
workspace/benchmark-runs/<run-id>/.agent/agent-benchmark-report.md
workspace/evidence-chain-runs/<run-id>/.agent/evidence-chain-report.md
```

## Runtime Manual Validation

如果展示需要覆盖 Minecraft 客户端或服务端内行为，先按 [../验证与可靠性/runtime-manual-validation.md](../验证与可靠性/runtime-manual-validation.md) 生成人工 runtime evidence。

推荐证据顺序：

1. 先展示 `.agent/modspec.json`、planner/modify evidence、audit report 和 build log。
2. 再展示 runtime evidence JSON 或 Markdown，说明人工实际检查了哪些游戏内行为。
3. 如果接入 `real-llm-stability --runtime-evidence`，再展示 `runtime_checked_count`、`runtime_success_count` 和 `runtime_unverified_count`。

这条路线的价值是把自动 gate 和人工 runtime 验证分开说清楚：build 证明 jar 可编译，runtime evidence 才能支撑“进游戏检查过”的结论。

当前首批人工 runtime evidence 位于 `evidence/runtime/`：3 个 case 已全部检查，其中 2 个 passed、1 个 failed。失败案例不是启动失败，而是 modify/worldgen workspace 中 `/place feature ruby_mod:ruby_ore` 命令失败；该案例的自然矿脉、内容注册和配方仍有截图证据。公开展示时应同时保留成功与失败结果，用来说明 runtime gate 补充了 audit/build 的覆盖边界。

## Repair / RAG 补充

RAG/repair benchmark 是可靠性补充，不是项目主线。

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench `
  --suite examples/agentic_rag_ablation.json `
  --llm-provider mock `
  --rag-ablation `
  --audit `
  --no-build `
  --json
```

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench `
  --suite examples/agent_benchmark_repair_18.json `
  --llm-provider mock `
  --rag-ablation `
  --audit `
  --no-build `
  --json
```

3-case smoke 用来确认 RAG on/off、trace 和 reviewer 没退化。18-case suite 用来覆盖 metadata、asset/resource、data/worldgen 和 generated-code audit 故障。Seeded holdout 用来防止只会固定题。

不要把 managed-file regeneration 的成功说成 RAG 核心能力。

## 项目讲解口径

一句话版本：

```text
这是一个受控领域 Coding Agent：LLM 负责把自然语言需求转成 ModSpec / patch / tool action，确定性 generator 负责产出 Java、JSON 和资源文件，audit/build/report 负责验收，repair benchmark 负责证明失败可诊断、可分类、可复现。
```

边界版本：

```text
当前证明的是 workspace 级 audit/build gate，不是自动进游戏 runtime 验收。RAG 是 planner/repair 的上下文和 citation evidence，不是项目主线。real provider 如果失败在连接、鉴权、SSL、限流或 HTTP 层，应归类为 provider_error，而不是 agent 能力失败。
```
