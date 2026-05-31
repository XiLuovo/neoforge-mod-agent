# Test Matrix

> 文档定位：这是测试覆盖查证文件，不建议从头读；只在需要证明某个能力有测试覆盖时查本文。

## V8.5 Capability Harvest Loop

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_free_code_lab tests.test_cli_parser tests.test_capabilities tests.test_tool_manifest -v
py -3.11 -m unittest discover -s tests -v
```

Expected:

- `agent lab-generate` parses `--from-workspace`, `--run-name`, `--llm-provider`, `--build/--no-build`, and `--json`.
- `harvest-report` parses `--run-name` and `--json`.
- Free-Code Lab copies the source workspace into `workspace/free-code-lab-runs/<run-id>/workspace`.
- Free-Code Lab writes `free-code-plan.json`, `free-code-diff.md`, `free-code-report.json`, `manual-runtime-checklist.md`, and `harvest-candidate.json`.
- Unsafe paths are rejected: traversal, absolute paths, `.git`, `gradle/wrapper`, build outputs, binary artifacts, and tool source paths outside allowed workspace roots.
- `replace_text` fails on zero or multiple matches and succeeds on exactly one match.
- Build failure marks the harvest candidate as `reject`.
- Missing manual runtime checklist prevents harvest readiness.
- Existing lab run names are not overwritten.
- `harvest-report` aggregates candidates from `workspace/free-code-lab-runs/*/.agent/harvest-candidate.json`.
- Full unittest discovery passes: 163 test cases.

## V8.4 ModSpec-First + Direct Code Lane

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_direct_code_agent tests.test_cli_parser tests.test_capabilities -v
py -3.11 -m unittest discover -s tests -v
```

Expected:

- `agent generate` and `agent modify` accept `--code-lane {hybrid,modspec,direct}`.
- Hybrid mode keeps the ModSpec path for normal mock cases.
- Direct Code Lane writes plan, review, diff, report, rollback report, and affected-file snapshots under `.agent/`.
- Direct Code changes are scoped to the generated workspace and reject absolute paths, path traversal, `.git`, Gradle wrapper jars, and build outputs.
- Full unittest discovery passes: 163 test cases.

## Evidence Chain Report

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_evidence_chain_report tests.test_cli_parser tests.test_capabilities tests.test_portfolio_demo -v
py -3.11 -m agent.cli evidence-chain-report --run-name local-evidence-chain --eval-limit 1 --repair-limit 1 --json
```

Expected:

- `workspace/evidence-chain-runs/local-evidence-chain/.agent/evidence-chain-report.json` exists.
- `workspace/evidence-chain-runs/local-evidence-chain/.agent/evidence-chain-report.md` exists.
- Report layers include `stable`, `behavior`, and `patch_agent`.
- Metrics include `layers_passed = 3`, `acceptance_success_rate = 1.0`, `recovery_rate = 1.0`, `failure_samples_total = 3`, and `runtime_validation_pass_rate = 1.0`.
- Stable layer includes mock eval success plus injected failure repair evidence.
- Behavior layer includes shared Behavior DSL generation, validator failure sample, and corrected recovery sample.
- Patch-agent layer includes managed-file patch plan evidence, an initial simulated build failure sample, rollback recommendation, and repair-loop recovery evidence.

## V8.3 DomainSpec Plugin Layer

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_domain_spec tests.test_cli_parser tests.test_capabilities -v
py -3.11 -m agent.cli domains --json
py -3.11 -m agent.cli agent generate "Create a ruby mod with ruby." --planner llm --llm-provider mock --workspace-name v83-domain-spec-smoke-20260514 --overwrite --no-build --json
py -3.11 -m agent.cli audit v83-domain-spec-smoke-20260514 --json
py -3.11 -m unittest discover -s tests -v
```

Expected:

- `domains --json` lists `minecraft.neoforge` as `stable`, plus `spring.api` and `unity.component` as `planned`.
- Generated `.agent/modspec.json` includes `domain = minecraft.neoforge` and `domain_spec_type = ModSpec`.
- Agent run payload includes `payload.runtime.domain_spec`.
- Smoke audit for `workspace/v83-domain-spec-smoke-20260514` passes with 0 errors.

## V8.2 Benchmark Report Page

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_benchmark_report tests.test_cli_parser tests.test_capabilities -v
py -3.11 -m agent.cli benchmark-report --run-name v82-benchmark-page-offline-20260514 --eval-limit 2 --repair-limit 2 --baseline-provider mock --candidate-provider openai-compatible --no-build --audit
py -3.11 -m unittest discover -s tests -v
```

Expected:

- `workspace/benchmark-runs/v82-benchmark-page-offline-20260514/.agent/benchmark-report.json` exists.
- `workspace/benchmark-runs/v82-benchmark-page-offline-20260514/.agent/benchmark-report.md` exists.
- `workspace/benchmark-runs/v82-benchmark-page-offline-20260514/.agent/benchmark-report.html` exists.
- Model A runs `mock`; Model B preflights `openai-compatible` and skips real calls unless `--run-real` or `--require-real` is passed.
- Benchmark metrics include model run counts, repair rate, build pass rate, and runtime pass rate.
- HTML page renders Model A/B, Failure Types, Runtime Evidence, and artifact paths.
- Full unittest discovery passes: 163 test cases.

## 2026-05-14 Real LLM Regeneration Check

本轮目标是用修复后的生成器重新生成三个固定 case，并且不手工 patch 生成 workspace。验收时 `llm->rules` 不计为 real LLM 成功。

| Case | Workspace | LLM result | ModSpec / audit | Build | Result |
| --- | --- | --- | --- | --- | --- |
| Ruby Basic | `workspace/real-llm-regen2-ruby-basic-20260514` | `planner_mode=llm` | audit 304 checks, 0 errors, 0 warnings | pass | 通过 |
| Machine | `workspace/real-llm-regen2-machine-20260514` | `planner_mode=llm` | audit 160 checks, 0 errors, 0 warnings | pass | 通过 |
| Progression strict | `workspace=null` via `real-llm-regen4-progression-strict-20260514` request | `planner_mode=llm`, provider timed out | not reached | not reached | 未通过 real LLM 标准 |
| Progression fallback hardening | `workspace/real-llm-regen3-progression-after-hardening-20260514` | `planner_mode=llm->rules` | audit 287 checks, 0 errors, 0 warnings | pass | 只证明 fallback 产物可 build，不计入 real LLM 成功 |

Source-level follow-up included in this round:

- `OPENAI_MODEL=gpt-5.5;gpt-image-2` now normalizes to `gpt-5.5` for text planning and records a warning.
- `agent generate --require-llm` fails instead of falling back when the real LLM request times out or errors.
- Entity codegen was updated for MC 26.1 and verified with `workspace/entity-regression-build-20260514` (`audit` 55 checks, `build` pass).

## 2026-05-13 Real LLM Natural Prompt Runtime Validation

本轮目标是验证真实 LLM 生成的 workspace 是否不只通过命令行检查，还能进入游戏完成基础人工测试。

| Case | Workspace | Result | Manual runtime checks |
| --- | --- | --- | --- |
| Machine | `workspace/real-llm-natural-machine-20260513` | 通过 | `real LLM` 返回成功；ModSpec 校验通过；audit 通过；build 通过；游戏内创建世界通过；创造物品栏中红宝石、红宝石矿石、红宝石压缩机图标正常；压缩机可放置、破坏、右键打开 GUI；工作台配方合成通过。 |
| Ruby Basic | `workspace/real-llm-natural-ruby-basic-20260513` | 通过 | `real LLM` 返回成功；ModSpec 校验通过；audit 通过；build 通过；进入世界时发现并修复 `worldgen/configured_feature` runtime JSON 问题；修复后游戏内验证通过。 |
| Progression | `workspace/real-llm-natural-progression-retry-20260513` | 通过 | `real LLM` 返回成功；ModSpec 校验通过；audit 通过；build 通过；修复 worldgen runtime schema、dimension type、biome carvers、advancement 背景资源后，游戏内创建世界、创造物品栏图标、方块放置/破坏、压缩机 GUI、工具/护甲和任务进度验证通过。 |

Runtime finding:

- `build` 通过不代表 Minecraft registry runtime 一定通过。
- 多个带矿石生成的 real LLM case 都暴露过同类问题：configured feature 的 `target` 不能是字符串，必须是 rule-test object。
- 修复后的合法形态为 `{"predicate_type": "minecraft:tag_match", "tag": "minecraft:stone_ore_replaceables"}`。
- Progression 额外暴露了 `dimension_type`、`worldgen/biome` 和根 advancement 背景资源的 runtime schema 风险。
- 源码层已补生成器、audit 和回归测试，避免后续新生成 workspace 再依赖手工 patch。

## V8 Resource Quality Upgrade

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_generation_audit tests.test_dashboard tests.test_capabilities -v
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli eval --run-name v80-readme-metrics-eval --planner llm --llm-provider mock --no-build --audit --json
py -3.11 -m agent.cli repair-eval --run-name v80-readme-metrics-repair-eval --json
py -3.11 -m agent.cli generate-from-spec .\examples\resource_quality_showcase.json --workspace-name v80-resource-smoke --overwrite --audit --no-build --json
py -3.11 -m agent.cli dashboard --run-name v80-resource-dashboard --json
py -3.11 -m agent.cli generate-from-spec .\examples\ruby_item.json --workspace-name v80-readme-metrics-build --overwrite --build --audit --json
```

Expected:

- Project version reports `8.0.0`.
- `compileall` succeeds for `src` and `tests`.
- Focused V8 tests pass for resource quality generation, dashboard rendering, and capability catalog entries.
- Full unittest discovery passes: 163 tests.
- Default eval passes 12/12 with audit enabled and `generated_files_total = 258`.
- Repair eval remains 5/5 full success.
- `workspace/v80-resource-smoke/.agent/resource-quality-report.json` exists and uses V8 schema version `8`.
- `workspace/v80-resource-smoke/.agent/texture-atlas.png` exists.
- `workspace/v80-resource-smoke/.agent/previews/ruby_gallery.png` exists.
- Dashboard HTML includes `Resource Preview`.
- Gradle build produces `workspace/v80-readme-metrics-build/build/libs/ruby_mod-0.2.0.jar`.

## V5.0 Portfolio Release

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_capabilities tests.test_dashboard -v
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli capabilities --run-name v50-capabilities --json
.\scripts\v5_portfolio_demo.ps1
py -3.11 -m agent.cli quality-gate --run-name v50-quality-gate --json
```

Expected:

- Project version reports `5.0.0`.
- Capability Matrix includes `portfolio_release_package`.
- README contains the V5.0 Chinese portfolio entry.
- `scripts/v5_portfolio_demo.ps1` runs `portfolio-demo` with mock LLM by default.
- `docs/portfolio-release.md`, `docs/interview-script.md`, `docs/architecture.md`, `docs/demo-cases.md`, and `docs/screenshots.md` exist.
- Portfolio report is written under `workspace/portfolio-runs/v50-portfolio/.agent/portfolio-demo-report.md`.
- Dashboard HTML is written under `workspace/portfolio-runs/v50-portfolio/runs/dashboard-runs/v50-portfolio-dashboard/index.html`.
- Quality gate passes with build smoke skipped by default.

## V4.7 Real LLM Agent Stability

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_llm_stability tests.test_agent_eval tests.test_capabilities tests.test_dashboard -v
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli agent generate "做一个红宝石模组，添加红宝石。" --planner llm --llm-provider openai-compatible --workspace-name v47-real-llm-fallback --overwrite --json
py -3.11 -m agent.cli capabilities --run-name v47-capabilities --json
```

Expected:

- `compileall` succeeds for `src` and `tests`.
- V4.7 focused tests pass for LLM stability, agent fallback, capabilities, and dashboard.
- Full unittest discovery passes.
- `doctor --no-java` reports LLM provider health without exposing secrets.
- Missing real LLM env causes `openai-compatible` to recommend fallback.
- If the machine already has a valid real provider, set `NEOFORGE_AGENT_LLM_BASE_URL=not-a-url` in the current shell to force the unhealthy-provider fallback smoke.
- `agent generate` with unhealthy `openai-compatible` still succeeds through deterministic rules fallback.
- Planner mode is reported as `llm->rules` when fallback is used.
- `.agent/llm-stability.json` records `provider_health`, `schema_retry_attempts`, and `schema_validation_attempts` when LLM artifacts are produced.
- `.agent/rag-context.json` records `quality`.
- Capability Matrix includes `real_llm_health_check`, `llm_schema_retry`, and `llm_rules_fallback`.
- Project version reports `4.7.0`.

## V4.6 RAG Citation Chain

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_agent_eval tests.test_dashboard tests.test_capabilities tests.test_replay -v
py -3.11 -m agent.cli agent generate "做一个红宝石模组，添加红宝石护符，右键回复4点生命值，冷却20秒。" --planner llm --llm-provider mock --workspace-name v46-rag-citations --overwrite --json
py -3.11 -m agent.cli dashboard --run-name v46-dashboard --json
py -3.11 -m agent.cli capabilities --run-name v46-capabilities --json
```

Expected:

- `agent-run.json` decisions contain `knowledge_ids` and `knowledge_refs`.
- `agent-decisions.md` displays `knowledge ids`.
- planner decisions include RAG references from `used_knowledge`.
- repair decisions include references from `repair_rag.hits` when repair is needed.
- dashboard HTML contains `RAG Citation Chain`.
- dashboard data contains `rag_reference_chains`.
- Capability Matrix includes `explainable_rag_citations` and `dashboard_rag_citation_chain`.
- Project version reports `4.6.0`.

## V4.5 Repair Eval Report

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_repair_eval tests.test_failure_lab tests.test_cli_parser tests.test_quality_gate tests.test_capabilities -v
py -3.11 -m agent.cli repair-eval --run-name v45-repair-eval --json
py -3.11 -m agent.cli repair-eval --run-name v45-recipe-repair-eval --case break_recipe_reference --json
py -3.11 -m agent.cli quality-gate --run-name v45-quality-gate --json
```

Expected:

- `repair-eval` succeeds.
- Report exists at `workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.json`.
- Markdown report exists at `workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.md`.
- Metrics include `audit_detected_rate`, `repair_rag_relevant_rate`, `repair_loop_repaired_rate`, `audit_recovered_rate`, and `full_success_rate`.
- Default five cases report `5/5` audit detected, `5/5` relevant repair RAG, `5/5` repair-loop repaired, and `5/5` audit recovered.
- Recipe reference case requires a relevant `recipes_loot_tags` RAG capability.
- `quality-gate` includes a `repair_eval` check by default.
- Project version reports `4.5.0`.

## V4.4 Failure Lab / 故障注入测试

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_failure_lab tests.test_cli_parser tests.test_quality_gate tests.test_capabilities -v
py -3.11 -m agent.cli failure-lab --run-name v44-failure-lab --json
py -3.11 -m agent.cli failure-lab --run-name v44-recipe-failure --case break_recipe_reference --json
py -3.11 -m agent.cli quality-gate --run-name v44-quality-gate --json
```

Expected:

- `failure-lab` 生成 5 个隔离坏项目。
- 每个 case 都先生成干净 workspace，再注入一个故障。
- `delete_texture` 删除生成 PNG 后，audit 报告 texture / texture-manifest 相关错误。
- `delete_model` 删除 item model 后，audit 报告 item model 缺失。
- `delete_worldgen_json` 删除 configured_feature 后，audit 报告 worldgen JSON 缺失。
- `delete_behavior_java` 删除 RubyCharmItem.java 后，audit 报告 behavior class 缺失。
- `break_recipe_reference` 修改实际 recipe JSON 引用后，audit 报告 `recipe:*:json_*` 引用错误。
- 每个 case 都生成 `.agent/repair-rag-context.json` 和 `.agent/repair-rag-context.md`。
- 每个 case 都运行 repair-loop，并在重生成 managed files 后 audit 通过。
- `quality-gate` 默认包含 `failure_lab` check。
- Project version reports `4.4.0`.

## V4.3 Repair RAG Visualization

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_replay tests.test_web_demo tests.test_dashboard tests.test_capabilities -v
py -3.11 -m agent.cli dashboard --run-name v43-dashboard --json
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli capabilities --run-name v43-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v43-quality-gate --json
```

Expected:

- Dashboard HTML contains `Repair RAG Advice`.
- Dashboard repair cards show RAG query and knowledge hit ids.
- Dashboard data includes `repair_rag_links` for root-cause/action/knowledge mapping.
- Replay output includes a `repair_rag` event.
- Replay metrics include `repair_rag_events_count` and `repair_rag_hits_count`.
- Web Demo HTML contains `Repair RAG`.
- Web Demo self-healing payload includes `repair_rag_hits_count`, `repair_rag_hits`, and `repair_rag_links`.
- Capability Matrix includes `dashboard_repair_rag`, `web_demo_repair_rag`, and `replay_repair_rag`.
- Project version reports `4.3.0`.

## V4.2 Repair RAG Advisor

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_repair_rag tests.test_agent_eval tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli capabilities --run-name v42-capabilities --json
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli quality-gate --run-name v42-quality-gate --json
```

Expected:

- `RepairRAGAdvisor` retrieves bundled NeoForge knowledge for audit/build repair failures.
- Missing texture or texture-manifest failures retrieve texture/audit knowledge.
- Agent repair payload contains `repair_rag`.
- `.agent/repair-rag-context.json` exists when repair analysis sees a failing check.
- `.agent/repair-rag-context.md` exists when repair analysis sees a failing check.
- `.agent/agent-repair-plan.md` includes a `Repair RAG Context` section.
- Dashboard data includes `repair_rag_runs` and `repair_rag_hits`.
- Capability Matrix includes `repair_rag`.
- Project version reports `4.2.0`.

## V4.1 Agent Run Replay

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_replay tests.test_cli_parser tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli agent generate "Create a ruby mod with ruby." --planner llm --llm-provider mock --workspace-name v41-replay-source --overwrite --no-build --json
py -3.11 -m agent.cli replay workspace/v41-replay-source --json
py -3.11 -m agent.cli replay workspace/v41-replay-source/.agent/agent-run.json --json
py -3.11 -m agent.cli capabilities --run-name v41-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v41-quality-gate --json
```

Expected:

- `replay` succeeds without rerunning LLMs, generators, audit, build, or repair.
- `.agent/agent-run-replay.json` exists.
- `.agent/agent-run-replay.md` exists.
- `.agent/agent-run-replay.html` exists and renders the static session trace viewer.
- Replay events include `run_start`, `role_step`, `decision`, `prompt_trace`, and `artifacts`.
- Metrics include step counts, decision count, prompt trace count, RAG hit count, JSON repair count, retry count, LLM usage totals, and artifact count.
- Capability Matrix includes `agent_replay` and `session_trace_viewer`.
- Project version reports `4.1.0`.

## V4.0 Portfolio One-Command Demo

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_portfolio_demo tests.test_cli_parser tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli portfolio-demo --run-name v40-portfolio --eval-limit 1 --json
py -3.11 -m agent.cli capabilities --run-name v40-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v40-quality-gate --json
```

Expected:

- `portfolio-demo` succeeds offline with mock LLM by default.
- Report exists at `workspace/portfolio-runs/<run-id>/.agent/portfolio-demo-report.json`.
- Markdown report exists at `workspace/portfolio-runs/<run-id>/.agent/portfolio-demo-report.md`.
- Steps include `doctor`, `showcase`, `dashboard`, `llm_eval_report`, `web_demo_smoke`, and `capabilities`.
- Dashboard `index.html` is generated under the portfolio run's nested dashboard directory.
- Capability Matrix includes `portfolio_demo`.
- Project version reports `4.0.0`.

## V3.9 Real LLM Eval And Compare Report

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_llm_eval_report tests.test_cli_parser tests.test_capabilities -v
py -3.11 -m agent.cli llm-eval-report --candidate-provider mock --limit 2 --run-name v39-llm-eval-mock --json
py -3.11 -m agent.cli llm-eval-report --candidate-provider openai-compatible --limit 1 --run-name v39-llm-eval-preflight --json
py -3.11 -m agent.cli capabilities --run-name v39-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v39-quality-gate --json
```

Expected:

- `llm-eval-report --candidate-provider mock` runs baseline eval, candidate eval, and eval-compare offline.
- Report exists at `workspace/llm-eval-runs/<run-id>/.agent/llm-eval-report.json`.
- Missing real provider config does not call the network and is recorded as a safe candidate skip unless `--require-real` is passed.
- Provider config summary does not expose API keys.
- Capability Matrix includes `llm_eval_report`, `real_llm_eval_compare`, and `llm_eval_preflight`.

## V3.8 Self-Healing Repair Visualization

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_web_demo tests.test_dashboard tests.test_capabilities -v
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli dashboard --run-name v38-dashboard --json
py -3.11 -m agent.cli dashboard --run-name v38-dashboard-fast --no-showcase --json
py -3.11 -m agent.cli capabilities --run-name v38-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v38-quality-gate --json
```

Expected:

- Web Demo HTML contains `V3.8 Self-Healing Agent Demo`, `repairView`, `repairStatus`, `Repair Agent`, and `Repair Loop`.
- Web Demo generate / modify payload contains `repair` and `self_healing`.
- Workspace detail API returns `repair_plan`, `repair_loop`, and `self_healing`.
- Dashboard HTML contains `Self-Healing Repair`.
- Dashboard data contains `repair_summary` and repair metrics such as `repair_runs`, `repair_executed`, and `repair_attempts`.
- Capability Matrix includes `web_demo_self_healing`, `dashboard_repair_summary`, and `self_healing_demo`.
- Existing V3.7 repair-agent safe execution tests still pass.

## V3.7 Repair Agent Safe Execution

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_agent_eval.AgentEvalTests.test_agent_repair_executes_safe_loop_after_audit_failure -v
py -3.11 -m unittest tests.test_agent_eval tests.test_repair_loop tests.test_capabilities -v
py -3.11 -m agent.cli capabilities --run-name v37-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v37-quality-gate --json
```

Expected:

- agent repair step detects audit/build failure.
- repair agent executes safe repair loop when repair is enabled.
- missing managed files are regenerated from `.agent/modspec.json`.
- repair payload includes `repair_executed=true`, `repair_success=true`, and embedded `repair_loop`.
- `.agent/agent-repair-plan.json` and `.agent/repair-loop-report.json` are written.
- existing repair-loop command still works independently.

## V3.6 Real LLM Stability

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_llm_stability -v
py -3.11 -m agent.cli doctor --run-name v36-doctor --no-java --json
py -3.11 -m agent.cli capabilities --run-name v36-capabilities --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby." --planner llm --llm-provider mock --workspace-name v36-llm-stability --overwrite --no-build --audit --json
```

Expected:

- JSON repair handles Markdown-fenced/prose-wrapped model output.
- planner retries after malformed JSON and records retry count.
- provider configuration inspection is secret-safe and does not call the network.
- `doctor` includes `llm.openai_compatible` as pass or warning.
- `.agent/llm-stability.json` records provider config summary, parse attempts, retries, and repair status.
- mock LLM smoke remains offline and deterministic.

## V3.5 Web Demo RAG Knowledge Browser

```powershell
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli web-demo --help
```

Manual demo:

```powershell
py -3.11 -m agent.cli web-demo --host 127.0.0.1 --port 8765
```

Expected:

- smoke succeeds without starting a blocking server
- HTML shell contains `RAG Knowledge` tab and `/api/knowledge` API wiring
- knowledge API returns bundled entries, category options, capability options, and tag options
- query `worldgen ore` returns `worldgen.overworld_ore`
- category / capability / tag filters narrow the displayed knowledge entries
- knowledge browser remains read-only and does not alter planner or generator behavior

## V3.4 Web Demo Live Logs And Build Output

```powershell
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli web-demo --help
```

Manual demo:

```powershell
py -3.11 -m agent.cli web-demo --host 127.0.0.1 --port 8765
```

Expected:

- smoke succeeds without starting a blocking server
- HTML shell contains async job API wiring for `/api/jobs/generate`, `/api/jobs/modify`, and `/api/job`
- HTML shell contains `Run Log` and `Build Output` tabs
- generate / modify buttons start background jobs and poll job status
- job payload includes queued/running/completed log events
- build output preview is available when Gradle log files exist
- original synchronous `/api/generate` and `/api/modify` APIs remain available

## V3.3 Web Demo Workspace Manage And Modify

```powershell
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli web-demo --help
```

Manual demo:

```powershell
py -3.11 -m agent.cli web-demo --host 127.0.0.1 --port 8765
```

Expected:

- smoke succeeds without starting a blocking server
- HTML shell contains workspace selector, workspace refresh/load controls, modify request input, and modify API wiring
- smoke creates a base workspace through the generate flow
- workspace list includes the generated smoke workspace
- workspace load returns current `ModSpec`, generated files, and existing audit/trace summary
- modify adds `ruby_charm` through the existing `AgentOrchestrator.run_modify` path
- merge summary reports `ruby_charm` as added, updated, or skipped according to existing workspace state
- `ModSpec diff` includes the changed feature ids
- audit result is returned after modify
- agent trace remains visible after generate and modify

## V3.2 Interactive Web Demo Dashboard

```powershell
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli web-demo --help
```

Manual demo:

```powershell
py -3.11 -m agent.cli web-demo --host 127.0.0.1 --port 8765
```

Expected:

- smoke succeeds without starting a blocking server
- HTML shell contains prompt input, planner selection, generate API, and eval API
- mock LLM generate returns a `ModSpec`
- generated file list is returned
- audit result is returned
- build result is shown as skipped unless build is enabled
- agent trace includes steps, decisions, and prompt traces
- browser page can run generate and eval from `http://127.0.0.1:8765/`

## V3.1 RAG Knowledge Enhancement

```powershell
py -3.11 -m agent.cli knowledge query "right click heal ruby charm item cooldown" --run-name v31-rag-behavior --json
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby charm item." --planner llm --llm-provider mock --workspace-name v31-agent-rag --overwrite --json
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --limit 3 --run-name v31-rag-eval --json
py -3.11 -m agent.cli dashboard --run-name v31-dashboard --json
```

Expected:

- knowledge query succeeds and returns behavior/right-click related hits
- `rag-query.json` includes `query_expansions`, `categories`, and `capabilities`
- agent workspace includes `.agent/llm-used-knowledge.json`
- `prompt-trace.json` includes `used_knowledge`, `rag_categories`, and `rag_capabilities`
- eval metrics include `rag_hit_rate`, `rag_hits_total`, `rag_categories_covered`, and `rag_capabilities_covered`
- dashboard data includes `rag_summary`
- dashboard HTML contains `RAG Hit Summary`

## V3.0 Multi-Agent Trace Smoke

```powershell
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby charm item." --planner llm --llm-provider mock --workspace-name v30-agent-ruby-charm --overwrite --json
```

Expected:

- command succeeds
- generated workspace has `.agent/agent-run.json`
- generated workspace has `.agent/agent-decisions.md`
- generated workspace has `.agent/prompt-trace.json`
- generated workspace has `.agent/agent-trace-summary.json`
- generated workspace has `.agent/agent-trace-summary.md`
- roles include `planner_agent`, `reviewer_agent`, `executor_agent`, `auditor_agent`, and `repair_agent`
- reviewer step includes `review_checks`
- LLM output is normalized into ModSpec, not Java or JSON assets

## V3.0 Dashboard Multi-Agent Trace

```powershell
py -3.11 -m agent.cli dashboard --run-name v30-dashboard --json
```

Expected:

- dashboard succeeds
- `workspace/dashboard-runs/v30-dashboard/index.html` exists
- dashboard HTML contains `Multi-Agent Trace`
- dashboard data includes `agent_traces`
- metrics include `agent_runs`, `agent_roles`, `agent_decisions`, and `prompt_traces`

## V2.9 Golden Tests

```powershell
py -3.11 -m agent.cli golden-test --run-name v29-golden --json
```

Expected:

- command succeeds
- `workspace/golden-runs/v29-golden/.agent/golden-report.json` exists
- golden cases cover item, block, behavior item, food effect, sword ignite, ore worldgen, tool set, armor set, and block variants
- each case checks generated file count, expected paths, expected feature ids, key JSON fields, and audit success

## V2.9 Quality Gate With Golden Tests

```powershell
py -3.11 -m agent.cli quality-gate --run-name v29-quality-gate --json
```

Expected:

- quality gate runs doctor, compileall, unittest, print-schema, test-examples, eval smoke, and golden tests
- default eval smoke covers V2.6 tool/armor and V2.8 block variants
- build smoke remains skipped unless `--build-smoke` is passed

Fast variant:

```powershell
py -3.11 -m agent.cli quality-gate --run-name v29-quality-gate-fast --no-golden --json
```

Expected:

- `golden_tests` check is skipped
- other enabled quality-gate checks still run

## V2.9 Dashboard Content Coverage

```powershell
py -3.11 -m agent.cli dashboard --run-name v29-dashboard --no-showcase --json
```

Expected:

- dashboard succeeds
- `workspace/dashboard-runs/v29-dashboard/index.html` exists
- dashboard data includes `content_coverage`
- metrics include `content_capabilities_total`, `content_capabilities_covered`, and `content_coverage_rate`

## V2.8 Block Variants Smoke

```powershell
py -3.11 -m agent.cli generate --build --audit "Create a ruby mod with ruby block variants." --workspace-name v28-block-variants --overwrite --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby block variants." --planner llm --llm-provider mock --workspace-name v28-llm-block-variants --overwrite --no-build --audit --json
py -3.11 -m agent.cli generate --build --audit "Create a ruby mod with ruby block." --workspace-name v28-modify-block-base --overwrite --json
py -3.11 -m agent.cli modify workspace\v28-modify-block-base "添加红宝石方块变体。" --build --audit --json
py -3.11 -m agent.cli modify workspace\v28-modify-block-base "添加红宝石方块变体。" --build --audit --json
```

Expected:

- rules planner creates `ruby_block`, `ruby_stairs`, `ruby_slab`, `ruby_wall`, `ruby_button`, `ruby_pressure_plate`, `ruby_fence`, `ruby_fence_gate`, `ruby_door`, and `ruby_trapdoor`
- generated ModSpec records `block_kind` and `base_block`
- Java registration uses vanilla subclasses such as `StairBlock`, `SlabBlock`, `ButtonBlock`, `DoorBlock`, and `TrapDoorBlock`
- recipes, loot tables, blockstates, block models, item models, textures, and lang keys are generated
- audit succeeds and checks class usage, assets, textures, recipes, and registration
- repeated modify skips existing block variants and recipes
- Gradle build succeeds for the full rules planner block variant project

## V2.7 Equipment Sets And Recipes Smoke

```powershell
py -3.11 -m agent.cli generate --build --audit "Create a ruby mod with ruby tool set." --workspace-name v27-tool-set --overwrite --json
py -3.11 -m agent.cli generate --build --audit "Create a ruby mod with ruby armor set." --workspace-name v27-armor-set --overwrite --json
py -3.11 -m agent.cli generate --build "Create a ruby mod with ruby." --workspace-name v27-modify-equipment --overwrite --json
py -3.11 -m agent.cli modify workspace\v27-modify-equipment "Add ruby tool set." --build --audit --json
py -3.11 -m agent.cli modify workspace\v27-modify-equipment "Add ruby tool set." --no-build --audit --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby tool set." --planner llm --llm-provider mock --workspace-name v27-llm-tool-set --overwrite --no-build --audit --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby armor set." --planner llm --llm-provider mock --workspace-name v27-llm-armor-set --overwrite --no-build --audit --json
py -3.11 -m agent.cli quality-gate --run-name v27-equipment-quality-gate --json
```

Expected:

- tool set generation creates `ruby`, `ruby_sword`, `ruby_pickaxe`, `ruby_axe`, `ruby_shovel`, `ruby_hoe`
- armor set generation creates `ruby`, `ruby_helmet`, `ruby_chestplate`, `ruby_leggings`, `ruby_boots`
- all generated equipment uses `tool_material` / `armor_material` value `ruby`
- shaped recipe JSON files are generated for every equipment piece
- audit checks models, textures, lang keys, registration, and recipe references
- build succeeds for rules planner tool and armor set smoke projects
- repeated modify skips existing equipment and recipe features
- mock LLM emits the same equipment and recipe ModSpec structure without using a real API

## V2.6 Tool And Armor Smoke

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石镐。" --workspace-name v26-ruby-pickaxe --overwrite --json
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加一套红宝石护甲。" --workspace-name v26-ruby-armor --overwrite --json
```

Expected:

- tool generation succeeds and build succeeds
- armor set generation succeeds and build succeeds
- audit checks item models, textures, lang keys, Java registration, tool method calls, and armor `ArmorType` usage
- `.agent/texture-manifest.json` records `tool_*` and `armor_*` templates

## V2.6 LLM Mock And Modify Smoke

```powershell
py -3.11 -m agent.cli generate "Create a ruby mod with ruby pickaxe." --planner llm --llm-provider mock --workspace-name v26-llm-pickaxe --overwrite --no-build --audit --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby armor set." --planner llm --llm-provider mock --workspace-name v26-llm-armor --overwrite --no-build --audit --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby." --workspace-name v26-modify-content-base --overwrite --no-build --json
py -3.11 -m agent.cli modify workspace\v26-modify-content-base "Add ruby pickaxe and ruby armor set." --no-build --audit --json
py -3.11 -m agent.cli modify workspace\v26-modify-content-base "Add ruby pickaxe and ruby armor set." --no-build --audit --json
```

Expected:

- mock LLM emits `tool` and `armor` ModSpec features
- modify adds `ruby_pickaxe` and the four armor pieces
- repeated modify reports existing tool/armor features as `skipped`
- audit succeeds after each generated or modified workspace

## V2.5 Dashboard Smoke

```powershell
py -3.11 -m agent.cli dashboard --run-name v25-dashboard --json
```

Expected:

- command succeeds
- `workspace/dashboard-runs/v25-dashboard/index.html` exists
- `.agent/dashboard-data.json` exists
- `.agent/dashboard-report.md` exists
- dashboard data includes capabilities, RAG hits, and showcase summary

## V2.5 Dashboard Fast Smoke

```powershell
py -3.11 -m agent.cli dashboard --run-name v25-dashboard-fast --no-showcase --json
```

Expected:

- command succeeds
- HTML dashboard exists
- showcase step is marked `skip`
- capabilities and RAG sections still render

## V2.5 Dashboard Unit Tests

```powershell
py -3.11 -m unittest tests.test_dashboard tests.test_cli_parser tests.test_capabilities -v
```

Expected:

- dashboard runner writes static HTML, JSON data, and Markdown report
- CLI parser accepts `dashboard`
- capability matrix includes `web_dashboard`

## V2.4 Knowledge Query Smoke

```powershell
py -3.11 -m agent.cli knowledge query "红宝石矿石自然生成在主世界地下" --run-name v24-rag-worldgen --json
```

Expected:

- command succeeds
- at least one hit is returned
- top hit is related to overworld ore worldgen
- `workspace/knowledge-runs/v24-rag-worldgen/.agent/rag-query.json` exists
- `workspace/knowledge-runs/v24-rag-worldgen/.agent/rag-query.md` exists

## V2.4 LLM Planner RAG Smoke

```powershell
py -3.11 -m agent.cli generate "Create a ruby mod with ruby ore worldgen in the overworld." --planner llm --llm-provider mock --workspace-name v24-rag-llm-worldgen --overwrite --no-build --audit --json
```

Expected:

- generation succeeds
- audit succeeds
- `.agent/rag-context.json` exists
- `.agent/rag-context.md` exists
- `.agent/planner-system-prompt.txt` contains `NeoForge RAG Context`
- RAG hits include `worldgen.overworld_ore`

## V2.4 RAG Unit Tests

```powershell
py -3.11 -m unittest tests.test_knowledge_base tests.test_cli_parser tests.test_capabilities -v
```

Expected:

- knowledge query returns relevant snippets
- RAG query reports are written
- LLM planner artifacts include RAG context
- CLI parser accepts `knowledge query`
- capability matrix includes `knowledge_query` and `rag_planner_context`

## V2.3 Programmatic Texture Smoke

```powershell
py -3.11 -m agent.cli generate "做一个红宝石模组，添加红宝石和红宝石矿石。" --workspace-name v23-texture-ruby --overwrite --no-build --audit --json
```

Expected:

- generation succeeds
- audit succeeds
- `.agent/texture-manifest.json` exists
- `src/main/resources/assets/ruby_mod/textures/item/ruby.png` exists
- `src/main/resources/assets/ruby_mod/textures/block/ruby_ore.png` exists
- generated texture PNGs are `16x16 RGBA`

## V2.3 Behavior Texture Smoke

```powershell
py -3.11 -m agent.cli generate "做一个红宝石模组，添加红宝石护符，右键回复4点生命值，冷却20秒。" --planner llm --llm-provider mock --workspace-name v23-texture-charm --overwrite --no-build --audit --json
```

Expected:

- generation succeeds
- audit succeeds
- `ruby_charm.png` exists under item textures
- `.agent/texture-manifest.json` records template `heal_badge`

## V2.3 Texture Audit / Repair Unit Tests

```powershell
py -3.11 -m unittest tests.test_generation_audit tests.test_repair_loop tests.test_capabilities -v
```

Expected:

- basic ruby generation writes texture PNGs and texture manifest
- audit fails when a generated item texture is missing
- repair-loop regenerates a missing managed texture
- capability matrix includes `procedural_textures` and `texture_audit`

## V2.3 Eval Compare Smoke

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --run-name v23-baseline --json
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --run-name v23-candidate --json
py -3.11 -m agent.cli eval-compare v23-baseline v23-candidate --run-name v23-compare --json
```

Expected:

- both eval runs succeed
- compare command succeeds
- `regressions_count = 0`
- `workspace/eval-comparisons/v23-compare/.agent/eval-compare-report.json` exists
- `workspace/eval-comparisons/v23-compare/.agent/eval-compare-report.md` exists

## V2.3 Eval Compare Unit Tests

```powershell
py -3.11 -m unittest tests.test_eval_compare tests.test_cli_parser tests.test_capabilities -v
```

Expected:

- identical reports compare successfully
- metric and case regressions are reported
- eval run names resolve to `workspace/eval-runs/<run-id>/.agent/eval-report.json`
- CLI parser accepts `eval-compare`
- capability matrix includes `eval_compare`

This matrix records the current smoke, regression, agent, evaluation, automated test, quality-gate, CI, doctor, showcase, capabilities, texture, and RAG commands for the V2.4 workflow.

All commands assume:

```powershell
Set-Location L:\projects\MinecraftMods\idea
$env:PYTHONPATH = (Resolve-Path .\src)
```

## Basic Ruby Generate / Build / Audit

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石。" --workspace-name v10-ruby --overwrite --json
```

Expected:

- generation succeeds
- build succeeds
- audit succeeds
- `workspace/v10-ruby/src/main/resources/pack.mcmeta` exists

## Behavior Item Generate / Build / Audit

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石护符，右键回复4点生命值，冷却20秒。" --workspace-name v10-behavior --overwrite --json
```

Expected:

- build succeeds
- audit succeeds
- custom `RubyCharmItem.java` is generated

## Food Effect Generate / Build

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石苹果，吃了给予生命恢复2，持续5秒。" --workspace-name v10-food-effect --overwrite --json
```

Expected:

- build succeeds
- audit succeeds
- food effect appears in generated Java

## Sword Ignite Generate / Build

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石剑，击中敌人点燃5秒。" --workspace-name v10-sword-ignite --overwrite --json
```

Expected:

- build succeeds
- audit succeeds
- custom `RubySwordItem.java` is generated

## Worldgen Generate / Build / Audit

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石和红宝石矿石，红宝石矿石挖掉掉落红宝石，并自然生成在主世界地下，Y -64 到 32，每矿脉6个，每区块4个。" --workspace-name v10-worldgen --overwrite --json
```

Expected:

- build succeeds
- audit succeeds
- configured feature JSON is generated
- placed feature JSON is generated
- biome modifier JSON is generated

## Modify Add Behavior

```powershell
py -3.11 -m agent.cli generate --build "做一个红宝石模组，添加红宝石。" --workspace-name v10-modify-behavior --overwrite --json
py -3.11 -m agent.cli modify workspace/v10-modify-behavior "添加红宝石护符，右键回复4点生命值，冷却20秒。" --build --audit --json
```

Expected:

- modify succeeds
- build succeeds
- audit succeeds
- `ruby_charm` is added

## Modify Add Worldgen

```powershell
py -3.11 -m agent.cli generate --build "做一个红宝石模组，添加红宝石和红宝石矿石，红宝石矿石挖掉掉落红宝石。" --workspace-name v10-modify-worldgen --overwrite --json
py -3.11 -m agent.cli modify workspace/v10-modify-worldgen "让红宝石矿石自然生成在主世界地下，Y -64 到 32，每矿脉6个，每区块4个。" --build --audit --json
```

Expected:

- modify succeeds
- build succeeds
- audit succeeds
- `ruby_ore` worldgen files are generated

## Audit Success

```powershell
py -3.11 -m agent.cli audit workspace/v10-worldgen --json
```

Expected:

- `success=true`
- `.agent/audit-report.json` exists
- `.agent/audit-report.md` exists

## Audit Negative

```powershell
Remove-Item workspace\v10-ruby\src\main\resources\assets\ruby_mod\models\item\ruby.json
py -3.11 -m agent.cli audit workspace/v10-ruby --json
```

Expected:

- `success=false`
- errors mention missing item model
- command exits non-zero

## Repair Broken Smoke

```powershell
py -3.11 -m agent.cli repair broken-smoke --json
```

Expected:

- `debug-context.md` is written
- `fix-request.md` is written
- `suspected-errors.json` is written

## Example Spec Regression

```powershell
py -3.11 -m agent.cli test-examples --no-build --json
```

Expected:

- bundled example specs generate successfully

## Schema Regression

```powershell
py -3.11 -m agent.cli print-schema --json
```

Expected:

- JSON schema prints successfully
- includes behavior and ore worldgen fields

## LLM Mock Behavior

```powershell
py -3.11 -m agent.cli generate "做一个红宝石模组，添加红宝石护符，右键回血。" --planner llm --llm-provider mock --build --audit --workspace-name v10-llm-behavior --overwrite --json
```

Expected:

- mock planning succeeds
- build succeeds
- audit succeeds

## LLM Mock Worldgen

```powershell
py -3.11 -m agent.cli generate "做一个红宝石模组，红宝石矿石自然生成在主世界地下，Y -64 到 32，每矿脉6个，每区块4个。" --planner llm --llm-provider mock --build --audit --workspace-name v10-llm-worldgen --overwrite --json
```

Expected:

- mock planning succeeds
- build succeeds
- audit succeeds

## V1.1 Agent Generate

```powershell
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby charm item." --planner llm --llm-provider mock --build --workspace-name v11-agent-behavior --overwrite --json
```

Expected:

- agent run succeeds
- build succeeds
- audit succeeds
- `.agent/agent-run.json` exists
- `.agent/agent-run.md` exists

## V1.1 Agent Modify

```powershell
py -3.11 -m agent.cli generate --build "Create a ruby mod with ruby and ruby ore." --workspace-name v11-agent-modify-base --overwrite --json
py -3.11 -m agent.cli agent modify workspace/v11-agent-modify-base "Make ruby ore generate underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk." --planner llm --llm-provider mock --build --json
```

Expected:

- agent run succeeds
- `ruby_ore` is updated
- build succeeds
- audit succeeds
- `.agent/agent-run.json` records planner, reviewer, executor, auditor, and repair roles

## V1.2 Eval Smoke

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --limit 2 --run-name v12-eval-smoke --json
```

Expected:

- eval command succeeds
- `workspace/eval-runs/v12-eval-smoke/.agent/eval-cases.json` exists
- `workspace/eval-runs/v12-eval-smoke/.agent/eval-report.json` exists
- `workspace/eval-runs/v12-eval-smoke/.agent/eval-report.md` exists
- metrics include success rate and expected feature match rate

## V1.2 Eval Full Offline Suite

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --run-name v12-eval-full --json
```

Expected:

- default eval cases run with mock LLM
- audit succeeds for generated workspaces
- expected feature checks pass
- report records planning, audit, feature, and modify metrics

## V1.2 Eval With Build

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --build --limit 2 --run-name v12-eval-build-smoke --json
```

Expected:

- eval command succeeds
- build is attempted for selected cases
- build success metrics are present
- this command is slower than `--no-build`

## V1.3 Automated Unit Regression

```powershell
py -3.11 -m unittest discover -s tests -v
```

Expected:

- all tests pass
- generation/audit tests pass
- negative audit test catches a missing item model
- agent mock LLM test passes
- eval metric tests pass
- CLI parser tests pass

## V1.4 Quality Gate

```powershell
py -3.11 -m agent.cli quality-gate --run-name v14-quality-gate-smoke --json
```

Expected:

- quality gate succeeds
- doctor environment preflight passes
- compileall passes
- unittest passes
- print-schema passes
- test-examples passes
- eval smoke passes
- build smoke is skipped by default
- `workspace/quality-gate-runs/v14-quality-gate-smoke/.agent/quality-gate-report.json` exists
- `workspace/quality-gate-runs/v14-quality-gate-smoke/.agent/quality-gate-report.md` exists

## V1.4 Quality Gate With Build Smoke

```powershell
py -3.11 -m agent.cli quality-gate --run-name v14-quality-gate-build --build-smoke --json
```

Expected:

- all fast checks pass
- build smoke generates a ruby workspace with `--build --audit`
- command is slower than the default quality gate

## V1.7 Quality Gate With Java Doctor

```powershell
py -3.11 -m agent.cli quality-gate --run-name v17-quality-gate-java --doctor-java --json
```

Expected:

- quality gate runs doctor with `java -version` diagnostics enabled
- Java lower than template target may be reported by doctor
- command succeeds unless doctor fails or another gate check fails

## V1.7 Quality Gate Without Doctor

```powershell
py -3.11 -m agent.cli quality-gate --run-name v17-quality-gate-no-doctor --no-doctor --json
```

Expected:

- `doctor_environment` is skipped
- other default fast checks still run
- command succeeds if compile, unittest, schema, examples, and eval smoke pass

## V1.5 Local CI Equivalent

```powershell
py -3.11 -m agent.cli quality-gate --run-name ci-quality-gate-local --json
```

Expected:

- quality gate succeeds
- build smoke is skipped by default
- report is written under `workspace/quality-gate-runs/ci-quality-gate-local/.agent/`
- command matches the GitHub Actions workflow behavior except for the run name

## V1.5 GitHub Actions Workflow Static Check

```powershell
Test-Path .github\workflows\quality-gate.yml
Select-String .github\workflows\quality-gate.yml -Pattern "quality-gate","actions/setup-python","upload-artifact","PYTHONPATH"
py -3.11 -m unittest tests.test_ci_workflow -v
```

Expected:

- workflow file exists
- workflow uses Python `3.11`
- workflow sets `PYTHONPATH=src`
- workflow runs `python -m agent.cli quality-gate --run-name ci-quality-gate --json`
- workflow uploads `.agent` quality gate artifacts
- workflow uploads `.agent` doctor artifacts
- default CI command does not include `--build-smoke`
- default CI command does not include `--no-doctor`

## V1.6 Environment Doctor

```powershell
py -3.11 -m agent.cli doctor --run-name v16-doctor-smoke --json
```

Expected:

- doctor command succeeds unless a required local prerequisite is missing
- report is written under `workspace/doctor-runs/v16-doctor-smoke/.agent/`
- checks include Python, project layout, template files, workspace, docs, CI workflow, and Java diagnostics
- Java version lower than the configured target is reported as a warning, not a default failure

## V1.6 Doctor Without Java

```powershell
py -3.11 -m agent.cli doctor --run-name v16-doctor-no-java --no-java --json
```

Expected:

- doctor command succeeds on machines where Java should not be checked
- `java.version` check is skipped
- doctor reports are still written

## V1.6 Doctor Unit Tests

```powershell
py -3.11 -m unittest tests.test_doctor -v
```

Expected:

- doctor runner writes JSON and Markdown reports
- core layout checks pass
- Java check can be skipped deterministically in tests

## V1.8 Showcase Smoke

```powershell
py -3.11 -m agent.cli showcase --run-name v18-showcase-smoke --json
```

Expected:

- showcase succeeds
- doctor step passes
- agent generate step passes
- agent modify step passes
- eval smoke step passes
- quality gate step is skipped by default
- `workspace/showcase-runs/v18-showcase-smoke/.agent/showcase-report.json` exists
- `workspace/showcase-runs/v18-showcase-smoke/.agent/showcase-report.md` exists

## V1.8 Showcase With Quality Gate

```powershell
py -3.11 -m agent.cli showcase --run-name v18-showcase-full --quality-gate --json
```

Expected:

- showcase succeeds
- quality gate step passes
- nested quality gate report is written under the showcase workspace area

## V1.8 Showcase Unit Tests

```powershell
py -3.11 -m unittest tests.test_showcase -v
```

Expected:

- showcase runner writes JSON and Markdown reports
- core showcase steps pass
- quality gate step can be skipped for fast tests

## V1.9 Capabilities Smoke

```powershell
py -3.11 -m agent.cli capabilities --run-name v19-capabilities --json
```

Expected:

- command succeeds
- version is `1.9.0`
- sections include workflows, content, behaviors, worldgen, planning, and reliability
- `workspace/capability-runs/v19-capabilities/.agent/capabilities.json` exists
- `workspace/capability-runs/v19-capabilities/.agent/capabilities.md` exists

## V1.9 Capabilities Unit Tests

```powershell
py -3.11 -m unittest tests.test_capabilities -v
```

Expected:

- capability catalog writes JSON and Markdown reports
- core sections exist
- core command capabilities include generate, quality-gate, showcase, and capabilities

## CLI Help

```powershell
py -3.11 -m agent.cli --help
py -3.11 -m agent.cli capabilities --help
py -3.11 -m agent.cli showcase --help
py -3.11 -m agent.cli doctor --help
py -3.11 -m agent.cli quality-gate --help
py -3.11 -m agent.cli eval --help
py -3.11 -m agent.cli agent --help
py -3.11 -m agent.cli agent generate --help
py -3.11 -m agent.cli agent modify --help
py -3.11 -m agent.cli generate --help
py -3.11 -m agent.cli modify --help
py -3.11 -m agent.cli audit --help
py -3.11 -m agent.cli repair --help
py -3.11 -m agent.cli print-schema --help
py -3.11 -m agent.cli test-examples --help
```

Expected:

- help output renders successfully
- `--audit` appears for `generate`, `generate-from-spec`, and `modify`
- `doctor` help includes `--no-java`, `--strict`, and `--run-name`
- `quality-gate` help includes `--no-doctor`, `--doctor-java`, and `--doctor-strict`
- `showcase` help includes `--quality-gate`, `--eval-limit`, and `--run-name`
- `capabilities` help includes `--run-name`
## V2.0 Agent Workflow Trace Smoke

```powershell
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby charm item." --planner llm --llm-provider mock --workspace-name v20-agent-trace --overwrite --no-build --json
```

Expected:

- command succeeds
- `.agent/agent-run.json` exists
- `.agent/agent-run.md` exists
- `.agent/agent-decisions.md` exists
- `.agent/prompt-trace.json` exists
- decisions include planner, reviewer, executor, auditor, and repair roles
- prompt trace includes normalized ModSpec

## V2.0 Agent Modify Trace Smoke

```powershell
py -3.11 -m agent.cli agent modify workspace\v20-agent-trace "Add ruby ore that generates underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk." --planner llm --llm-provider mock --no-build --json
```

Expected:

- command succeeds
- added includes `ruby` and `ruby_ore` when the base project does not already contain ruby
- audit succeeds
- `.agent/agent-decisions.md` is updated
- `.agent/prompt-trace.json` records the modify patch prompt and normalized patch

## V2.0 Unit Tests

```powershell
py -3.11 -m unittest tests.test_agent_eval tests.test_capabilities tests.test_cli_parser -v
```

Expected:

- agent generate writes decision and prompt trace artifacts
- capability catalog reports version `2.0.0`
- CLI parser still accepts existing commands
## V2.1 Repair Loop Smoke

Generate a simple workspace:

```powershell
py -3.11 -m agent.cli generate "Create a ruby mod with ruby." --workspace-name v21-repair-loop --overwrite --no-build --audit --json
```

Delete a generated item model:

```powershell
Remove-Item workspace\v21-repair-loop\src\main\resources\assets\ruby_mod\models\item\ruby.json
```

Run the repair loop:

```powershell
py -3.11 -m agent.cli repair-loop workspace\v21-repair-loop --max-attempts 1 --no-build --json
```

Expected:

- initial audit fails inside the repair-loop report
- managed files are regenerated
- final audit succeeds
- deleted item model exists again
- `.agent/repair-loop-report.json` exists
- `.agent/repair-loop-report.md` exists

## V2.1 Repair Loop Unit Tests

```powershell
py -3.11 -m unittest tests.test_repair_loop -v
```

Expected:

- healthy workspace is a no-op
- missing generated item model is restored

## V2.2 Eval Coverage Smoke

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --run-name v22-eval-smoke --json
```

Expected:

- eval command succeeds
- default cases cover basic item, behavior item, speed effect, food effect, sword ignite, ore worldgen, modify add behavior, and modify add worldgen
- metrics include `expected_category_match_rate`
- metrics include `agent_artifacts_complete_rate`
- metrics include `repeat_modify_success_rate`
- repeat modify cases do not report unexpected added/updated features
- `workspace/eval-runs/v22-eval-smoke/.agent/eval-report.json` exists
- `workspace/eval-runs/v22-eval-smoke/.agent/eval-report.md` exists

## V2.2 Eval Unit Tests

```powershell
py -3.11 -m unittest tests.test_agent_eval tests.test_capabilities -v
```

Expected:

- eval reports expected feature and category metrics
- agent trace artifacts are checked
- repeat modify idempotency is reported
- capability catalog reports version `2.2.0`
