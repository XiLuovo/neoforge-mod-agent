# Development E2E Showcase

当前推荐展示路径是“受控 NeoForge Coding Agent 的端到端开发闭环”，不是继续加厚 RAG/Milvus，也不是把 deterministic repair 包装成核心卖点。

## 展示顺序

1. 用 `showcase` 跑一键离线演示，先证明 doctor、generate、modify、eval smoke 和 development e2e 都能落盘报告。
2. 单独跑 `eval --cases examples/agent_development_e2e.json`，展示自然语言需求如何进入 `ModSpec`，再由 generator 产出 Java/JSON/resource，并通过 audit gate 和 trace/report 验收。
3. 打开 development e2e eval report，重点看 `expected_feature_match_rate`、`expected_category_match_rate`、`audit_success_rate` 和 `repeat_modify_success_rate`。
4. 如需可靠性补充，再展示 3-case RAG ablation smoke、18-case repair suite 或 seeded holdout。
5. 明确边界：本轮证明 audit/build 层，不声称 Minecraft runtime 自动验收。

## 推荐命令

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli showcase --run-name codex-development-e2e-smoke --llm-provider mock --no-build --json
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --llm-provider mock --audit --no-build --json
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --json
py -3.11 -m agent.cli showcase --run-name codex-development-e2e-build --llm-provider mock --build --json
```

`--no-build` 适合快速面试演示；`--build` 更适合本地正式验收，耗时会更长。

## Post-Merge Evidence Snapshot

合并 Decomposed Planner v1 和 real-provider hardening 后，当前可引用的证据链是：

- unit tests：`py -3.11 -m unittest discover -s tests -v` 通过，`213 tests OK`。
- real provider decomposed eval：`postmerge-real-decomposed-fragment-fix2`，2/2 cases success，audit 2/2 success，expected feature/category match rate 均为 `1.0`。
- real provider eval 边界：该 run 使用 `--no-build`，证明的是 real provider planning + audit + trace，不是 Gradle build。
- strict real provider build smoke：`real-decomposed-build-smoke` 使用 `openai-compatible` provider + decomposed planner + `--require-llm` + `--build`，planner 生成 15 个 features，audit `246` checks passed，Gradle `exit_code=0`，生成 `ruby_progression-0.1.0.jar`。
- real provider build 边界：该 run 证明真实 provider 能通过 workspace 级 planning、audit 和 Gradle build；仍然不是 Minecraft 客户端/服务端进游戏自动验收。
- build smoke：`main-postmerge-build-smoke` 使用 mock provider + decomposed planner + `--build`，audit `280` checks passed，Gradle `exit_code=0`，生成 `progression_mod-0.1.0.jar`。
- runtime 边界：这些证据仍然不是 Minecraft 客户端/服务端进游戏自动验收。

推荐展示时先打开：

- `workspace/eval-runs/postmerge-real-decomposed-fragment-fix2/.agent/eval-report.md`
- `workspace/real-decomposed-build-smoke/.agent/agent-run.md`
- `workspace/real-decomposed-build-smoke/.agent/logs/gradle-build.json`
- `workspace/real-decomposed-build-smoke/.agent/audit-report.md`
- `workspace/main-postmerge-build-smoke/.agent/agent-run.md`
- `workspace/main-postmerge-build-smoke/.agent/logs/gradle-build.json`
- `workspace/main-postmerge-build-smoke/.agent/audit-report.md`

讲法要保持证据匹配：real provider eval 证明真实 provider 能走通 decomposed planner、audit 和 trace；strict real provider build smoke 进一步证明单 case 真实 provider workspace 可编译；mock build smoke 是离线可复现补充。

## Development E2E Suite

`examples/agent_development_e2e.json` 当前包含两类 case：

- `develop_progression_loop`：从自然语言生成 ruby progression gameplay loop，覆盖 ore/worldgen、compressor machine、ruby tools、recipes 和 progression report。
- `modify_add_worldgen_repeat`：从已有 ruby mod 出发追加 ruby ore worldgen，并通过 repeat modify 验证同一需求重复执行不会重复添加。

报告中应该重点展示：

- `eval_report_json` / `eval_report_md`
- expected feature/category match rate
- audit attempted/success
- build attempted/success
- repeat modify success
- agent trace、prompt trace、audit report

## Repair/RAG 补充

RAG/repair benchmark 到 RC3-candidate 已阶段性冻结。它们仍然有价值，但展示口径应是可靠性补充：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench `
  --suite examples/agentic_rag_ablation.json `
  --llm-provider mock `
  --rag-ablation `
  --audit `
  --json

py -3.11 -m agent.cli agent bench `
  --suite examples/agent_benchmark_repair_18.json `
  --llm-provider mock `
  --rag-ablation `
  --audit `
  --no-build `
  --json

py -3.11 -m agent.cli agent bench `
  --repair-holdout `
  --holdout-seed demo `
  --holdout-limit 8 `
  --llm-provider mock `
  --rag-ablation `
  --audit `
  --no-build `
  --json
```

讲法要克制：3-case smoke 用来确认 RAG on/off、trace 和 reviewer 没退化；18-case suite 用来覆盖 metadata、asset/resource、data/worldgen 和 generated-code audit 故障；seeded holdout 用来防止只会固定题。不要把 managed-file regeneration 的成功说成 RAG 核心能力。

## 面试讲法

一句话版本：

```text
这是一个受控领域 coding agent：LLM 负责把自然语言需求转成 ModSpec / patch / tool action，确定性 generator 负责产出 Java、JSON 和资源文件，audit/build/report 负责验收，repair benchmark 负责证明失败可诊断、可分类、可复现。
```

边界版本：

```text
当前证明的是 workspace 级 audit/build gate，不是自动进游戏 runtime 验收；RAG 是 planner/repair 的上下文和 citation 证据，不是项目主线；real provider 如果失败在连接或 SSL 层，应该归类为 provider_error，而不是 agent 能力失败。
```
