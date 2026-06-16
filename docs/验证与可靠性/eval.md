# Eval 与 Development E2E

旧 eval 命令仍有价值：它们提供固定 prompt、固定期望和基础回归指标。RC3-candidate 之后，公开展示时应把 development e2e suite 放在前面，把 repair/RAG benchmark 解释为可靠性补充。

## 当前关系

```text
natural language request
-> ModSpec-first planning / decomposed feature planning
-> deterministic generator
-> Java / JSON / resource artifacts
-> audit/build gate
-> trace-backed eval report
-> repair benchmark as reliability supplement
```

## 推荐主命令

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --llm-provider mock --audit --no-build --json
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --json
py -3.11 -m agent.cli showcase --run-name codex-development-e2e-smoke --llm-provider mock --no-build --json
```

`--planner decomposed` 会额外落盘 `.agent/decomposed-planner/feature-plan.json`、`feature-jsons.json`、`composed-modspec-raw.json` 和 `bad-raw-outputs.json`，用于展示 natural language -> feature plan -> small JSON -> ModSpec -> audit/report 的可调试链路。

更严格的本地验收：

```powershell
py -3.11 -m agent.cli showcase --run-name codex-development-e2e-build --llm-provider mock --build --json
```

## 当前已验证证据

当前 post-merge 证据分成两层，展示时不要混在一起说：

| 证据 | 命令/Run | 已证明 | 未证明 |
|---|---|---|---|
| real provider decomposed eval | `postmerge-real-decomposed-fragment-fix2` | real provider planning 成功，2/2 cases success，audit 2/2，expected feature/category match rate = `1.0`，trace artifacts 完整 | 未跑 Gradle build，因为使用 `--no-build` |
| build smoke | `main-postmerge-build-smoke` | mock provider + decomposed planner 生成工程后，audit `280` checks passed，Gradle build `exit_code=0`，jar 已生成 | 未证明 real provider 同一 run 的 build，也未证明 Minecraft runtime |
| unit tests | `py -3.11 -m unittest discover -s tests -v` | planner hardening、decomposed regression 和既有能力回归通过，`213 tests OK` | 不替代真实 provider 或 Gradle build |

如果要进一步升级证据，可以追加一个单 case strict real provider build：

```powershell
py -3.11 -m agent.cli agent develop `
  "Create a ruby progression gameplay loop with ruby ore worldgen in the overworld, a compressor machine, ruby tools, recipes, and an auditable progression report." `
  --planner decomposed `
  --llm-provider openai-compatible `
  --require-llm `
  --workspace-name real-decomposed-build-smoke `
  --overwrite `
  --build `
  --json
```

该命令如果失败，需要分开记录 `provider_error`、planner/schema failure、audit failure、build environment failure 或 generated-code build failure。

## Development E2E 说明什么

- 自然语言需求能进入受控 `ModSpec`，不是让 LLM 无边界手写完整 Java。
- generator 能产出 NeoForge workspace 的 Java、JSON、资源和报告。
- audit gate 能验证 worldgen、machine、tool、recipe、progression report 等产物。
- modify flow 能从已有 ModSpec 追加 worldgen，并用 repeat modify 验证幂等。
- report 能明确给出 expected feature/category match rate、audit/build 结果和 repeat modify 结果。

## 不要过度声称

- `--no-build` 是 audit-level smoke，不是 Gradle build 通过。
- `--build` 也不等于 Minecraft runtime 自动验收。
- RAG 命中是 planner/repair 的领域上下文和 trace evidence，不替代 generator、audit 或 build。
- provider 连接失败要归类为 `provider_error`，不能算成 repair logic 失败。
