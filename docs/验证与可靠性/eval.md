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
py -3.11 -m agent.cli eval --cases examples/decomposed_modify_cross_feature_stress.json --planner decomposed --llm-provider mock --audit --no-build --json
py -3.11 -m agent.cli showcase --run-name codex-development-e2e-smoke --llm-provider mock --no-build --json
py -3.11 -m agent.cli showcase --run-name public-build-smoke --llm-provider mock --build --json
```

`--planner decomposed` 会额外落盘 `.agent/decomposed-planner/feature-plan.json`、`feature-jsons.json`、`composed-modspec-raw.json` 和 `bad-raw-outputs.json`，用于展示 natural language -> feature plan -> small JSON -> ModSpec -> audit/report 的可调试链路。

更严格的本地验收：

```powershell
py -3.11 -m agent.cli showcase --run-name codex-development-e2e-build --llm-provider mock --build --json
```

## 当前公开证据分层

当前 evidence 分成多层，展示时不要混在一起说。历史 run 可以作为补充材料，但公开入口优先引用当前可复现 smoke 和 CI/quality gate：

| 证据 | 命令/Run | 已证明 | 未证明 |
|---|---|---|---|
| unit tests | `py -3.11 -m unittest discover -s tests -v` | 本地/CI 回归通过；测试数量随能力增长变化，以命令输出和 Quality Gate 为准 | 不替代真实 provider、Gradle build 或 Minecraft runtime |
| public decomposed e2e smoke | `public-polish-decomposed-e2e-20260627` | mock + decomposed planner + audit + `--no-build`：2/2 cases success，audit 2/2，expected feature/category match rate = `1.0`，repeat modify 1/1，trace artifacts 完整 | 不证明真实 provider、Gradle build 或 Minecraft runtime |
| public build smoke | `public-build-smoke-clean` | mock showcase + `--build`：5/5 showcase steps pass，doctor 22 pass / 0 warning，development e2e 2/2 success，audit 2/2，Gradle build 2/2，生成 `progression_mod-0.1.0.jar` 和 `ruby_mod-0.1.0.jar` | 不证明真实 provider 或 Minecraft runtime |
| RC1 release benchmark | `rc1-release-bench` | mock develop/repair benchmark 2/2 success，audit / repair / patch accept 指标为 `1.0`，trace-backed report 可复查 | 使用 mock + `--no-build`，不证明真实 provider 或 Gradle build |
| RC2 RAG ablation | `rc2-rag-ablation` | RAG-on `3/3`，RAG-off `0/3`，证明 RAG policy/citation/trace 对指定 repair cases 有可观测差异 | 使用 mock + `--no-build`，不证明真实 provider、Gradle build 或 Minecraft runtime |
| real provider decomposed eval | `postmerge-real-decomposed-fragment-fix2` | real provider planning 成功，2/2 cases success，audit 2/2，expected feature/category match rate = `1.0`，trace artifacts 完整 | 未跑 Gradle build，因为使用 `--no-build` |
| strict real provider build smoke | `real-decomposed-build-smoke` | `openai-compatible` + decomposed + `--require-llm` + `--build` 单 case 成功；planner 生成 `15` features；audit `246` checks passed；Gradle build `exit_code=0`；生成 `ruby_progression-0.1.0.jar` | 未证明 full real-provider eval build，也未证明 Minecraft runtime |
| build smoke | `main-postmerge-build-smoke` | mock provider + decomposed planner 生成工程后，audit `280` checks passed，Gradle build `exit_code=0`，jar 已生成 | 未证明 real provider 同一 run 的 build，也未证明 Minecraft runtime |

单 case strict real provider build 的复现命令：

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

已验证 run `real-decomposed-build-smoke` 中 provider/model 为 `openai-compatible` / `deepseek-v4-flash`，LLM calls `16`，provider-reported total tokens `65,226`，`retry_attempts=0`、`schema_retry_attempts=0`、`json_repair_applied=false`。planner normalization warnings 包括 `compressor` 规范化为 `ruby_compressor`、6 个 progression fragments 合并为 `ruby_progression`、ore drop 和 dimension 规范化；这些是 deterministic hardening 生效的证据，不是失败。

该命令如果未来复跑失败，需要分开记录 `provider_error`、planner/schema failure、audit failure、build environment failure 或 generated-code build failure。

## Mock A/B Eval Snapshot

Post-merge 后补跑了一组 mock A/B，用同一份 `examples/agent_development_e2e.json` 比较 `planner=llm` 和 `planner=decomposed`：

```powershell
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner llm --llm-provider mock --audit --no-build --run-name ab-mock-llm-postmerge-20260616 --json
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --run-name ab-mock-decomposed-postmerge-20260616 --json
```

核心结果：

| Metric | `planner=llm` | `planner=decomposed` |
|---|---:|---:|
| success rate | `1.0` | `1.0` |
| audit success rate | `1.0` | `1.0` |
| expected feature match rate | `1.0` | `1.0` |
| expected category match rate | `1.0` | `1.0` |
| repeat modify success rate | `1.0` | `1.0` |
| generated files total | `81` | `64` |
| build attempted | `0` | `0` |
| fallback/provider/schema failure scan | none | none |

Prompt/call 体量使用 mock provider 的 `llm-stability.json` 估算，不代表真实 provider 计费：

| Scope | `planner=llm` | `planner=decomposed` |
|---|---:|---:|
| develop calls | `1` | `18` |
| develop total tokens | `84,414` | `34,559` |
| develop max input tokens per call | `79,747` | `2,719` |
| develop average input tokens per call | `79,747` | `1,519.1` |
| modify calls | `1` | `1` |
| modify total tokens | `81,264` | `80,538` |
| total calls across 2 cases | `2` | `19` |
| total tokens across 2 cases | `165,678` | `115,097` |

结论：

- Decomposed planner 在 develop/generate 场景中把一次大 `ModSpec` prompt 拆成多次小 feature prompt；调用次数增加，但单次最大输入从 `79,747` 降到 `2,719`，总 token 从 `84,414` 降到 `34,559`。
- 这组 post-merge A/B 记录的是 Decomposed Planner v1 状态；当时 modify 仍复用 controlled LLM patch planner，因此 modify 侧 token 体量基本不变。
- 这组 A/B 是 mock + `--no-build`，适合证明 planner 结构和 prompt 体量差异，不证明 real provider 成本，也不证明 Gradle build 或 Minecraft runtime。

## Decomposed Modify v2 Smoke

本地新增 `decomposed-modify-v2-smoke`，命令：

```powershell
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --run-name decomposed-modify-v2-smoke --json
```

结果边界：mock provider + audit + `--no-build`，不代表真实 provider 成本、Gradle build 或 Minecraft runtime 自动验收。

| Metric | Result |
|---|---:|
| total cases | `2` |
| success rate | `1.0` |
| audit success rate | `1.0` |
| expected feature match rate | `1.0` |
| expected category match rate | `1.0` |
| repeat modify success rate | `1.0` |
| decomposed modify used rate | `1.0` |
| modify LLM calls total | `2` |
| modify total tokens | `2,752` |
| modify max input tokens per call | `1,472` |
| modify average input tokens per call | `1,182.5` |
| modify context compaction ratio | `0.4363` |

v2 证据位于 modify workspace 的 `.agent/decomposed-modify/`：`existing-context.json`、`modify-feature-plan.json`、`feature-patches.json`、`composed-patch-modspec.json` 和 `merge-preview.json`。

补充 build smoke：`decomposed-modify-v2-build-base` 先用 mock + decomposed 生成 ruby/ruby_ore baseline，再运行：

```powershell
py -3.11 -m agent.cli agent modify decomposed-modify-v2-build-base "Add ruby ore worldgen in the overworld, Y -64 to 32, vein size 6, 4 per chunk." --planner decomposed --llm-provider mock --build --json
```

结果：`success=true`，`planner_mode_used=decomposed`，`updated=["ruby_ore"]`，patch-agent status `pass`，managed files `22`，audit `80` checks / 0 errors / 0 warnings，Gradle build `exit_code=0`，jar `workspace/decomposed-modify-v2-build-base/build/libs/ruby_mod-0.1.0.jar`。这条证明 mock single-case build gate，不证明真实 provider 或 Minecraft runtime。

补充 real provider smoke：`real-decomposed-modify-v2-base` 先用 mock + decomposed 生成 ruby/ruby_ore baseline，再运行：

```powershell
py -3.11 -m agent.cli agent modify real-decomposed-modify-v2-base "Add a ruby sword with 7 attack damage and 1.6 attack speed, crafted from two rubies and one stick." --planner decomposed --llm-provider openai-compatible --require-llm --no-build --json
```

结果：`success=true`，`planner_mode_used=decomposed`，`added=["ruby_sword"]`，`.agent/decomposed-modify/` evidence 写出完整 v2 产物，2 次 provider call，total tokens `3,943`，max input tokens `1,377`，patch-agent status `pass`，managed files `25`，audit `91` checks / 0 errors / 0 warnings。随后运行：

```powershell
py -3.11 -m agent.cli build real-decomposed-modify-v2-base --json
```

结果：Gradle build `exit_code=0`，jar `workspace/real-decomposed-modify-v2-base/build/libs/ruby_mod-0.1.0.jar`。这条证明真实 provider modify v2 能通过 workspace 级 audit 和 build follow-up；仍不证明 Minecraft runtime 自动验收。

补充 behavior item smoke：`real-modify-v2-behavior-base` 先用 mock + decomposed 生成 ruby baseline，再运行：

```powershell
py -3.11 -m agent.cli agent modify real-modify-v2-behavior-base "Add a ruby charm item that heals 4 health on right click with 20 seconds cooldown." --planner decomposed --llm-provider openai-compatible --require-llm --no-build --json
```

结果：`success=true`，`planner_mode_used=decomposed`，`added=["ruby_charm"]`，real provider 输出的 `right_click_behavior` / `cooldown_seconds` 被 deterministic hardening 为 `behavior.type=right_click_heal` / `cooldown_ticks=400`，`.agent/behavior-report.json` 记录 compiled item host `ruby_charm`，2 次 provider call，total tokens `4,141`，max input tokens `1,250`，patch-agent status `pass`，managed files `17`，audit `67` checks / 0 errors / 0 warnings。随后运行：

```powershell
py -3.11 -m agent.cli build real-modify-v2-behavior-base --json
```

结果：Gradle build `exit_code=0`，jar `workspace/real-modify-v2-behavior-base/build/libs/ruby_mod-0.1.0.jar`。这条证明真实 provider behavior item modify 能通过 v2 evidence、Behavior DSL/report、audit 和 build follow-up；仍不证明 Minecraft runtime 自动验收。

补充 tool/recipe smoke：`real-modify-v2-tool-recipe-base` 先用 mock + decomposed 生成 ruby baseline，再运行：

```powershell
py -3.11 -m agent.cli agent modify real-modify-v2-tool-recipe-base "Add a ruby pickaxe crafted from three rubies and two sticks." --planner decomposed --llm-provider openai-compatible --require-llm --no-build --json
```

结果：`success=true`，`planner_mode_used=decomposed`，`added=["ruby_pickaxe"]`，real provider 输出的 `ruby_pickaxe_recipe` recipe id 被 deterministic hardening 为 canonical `ruby_pickaxe`，最终 `tool_material=ruby`，`.agent/modspec.json` 含 `recipes=[ruby_pickaxe]`，生成 `src/main/resources/data/ruby_mod/recipe/ruby_pickaxe.json`，3 次 provider call，total tokens `6,465`，max input tokens `1,336`，patch-agent status `pass`，managed files `15`，audit `66` checks / 0 errors / 0 warnings。随后运行：

```powershell
py -3.11 -m agent.cli build real-modify-v2-tool-recipe-base --json
```

结果：Gradle build `exit_code=0`，jar `workspace/real-modify-v2-tool-recipe-base/build/libs/ruby_mod-0.1.0.jar`。这条证明真实 provider tool + recipe modify 能通过 v2 evidence、ModSpec recipe、managed resource、audit 和 build follow-up；仍不证明 Minecraft runtime 自动验收。

补充 progression update smoke：`real-modify-v2-progression-update-base` 先用 mock + decomposed 生成 ruby progression baseline，再运行：

```powershell
py -3.11 -m agent.cli agent modify real-modify-v2-progression-update-base "Update the ruby progression so entering the ruby realm unlocks a final mastery milestone stage with ruby_sword and ruby_pickaxe evidence." --planner decomposed --llm-provider openai-compatible --require-llm --no-build --json
```

结果：`success=true`，`planner_mode_used=decomposed`，`updated=["ruby_progression"]`，real provider 曾输出新 end stage 但漏 link，被 deterministic progression merge hardening 补为 `enter_ruby_realm -> mastery_milestone`，最终 `.agent/progression-report.json` 为 `8` stages / `7` links，`entry_reaches_end=true`，missing references `0`，2 次 provider call，total tokens `29,511`，max input tokens `8,441`，patch-agent status `pass`，managed files `64`，audit `280` checks / 0 errors / 0 warnings。随后运行：

```powershell
py -3.11 -m agent.cli build real-modify-v2-progression-update-base --json
```

结果：Gradle build `exit_code=0`，jar `workspace/real-modify-v2-progression-update-base/build/libs/progression_mod-0.1.0.jar`。这条证明真实 provider progression update modify 能通过 v2 evidence、progression report、audit 和 build follow-up；仍不证明 Minecraft runtime 自动验收。

## Decomposed Modify v2 Cross-feature Stress

新增 stress suite：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --cases examples/decomposed_modify_cross_feature_stress.json --planner decomposed --llm-provider mock --audit --no-build --run-name decomposed-modify-cross-feature-stress --json
```

结果边界：mock provider + audit + `--no-build`，用于证明连续 modify evaluator、v2 evidence 快照和 deterministic merge hardening；不代表真实 provider、Gradle build 或 Minecraft runtime 自动验收。

| Metric | Result |
|---|---:|
| total cases | `2` |
| modify step total | `5` |
| multi-step modify success rate | `1.0` |
| audit success rate | `1.0` |
| expected feature match rate | `1.0` |
| expected category match rate | `1.0` |
| repeat modify success rate | `1.0` |
| decomposed modify used rate | `1.0` |
| modify LLM calls total | `10` |
| modify total tokens | `30,189` |
| modify max input tokens per call | `5,542` |
| modify context compaction ratio | `0.516` |

suite 覆盖两条连续 modify 压测：

- `modify_cross_feature_item_tool_recipe_worldgen`：从 ruby baseline 连续追加 `ruby_charm` behavior item、`ruby_pickaxe` + shaped recipe、`ruby_ore` worldgen，并重复 tool/recipe step 验证幂等。
- `modify_cross_feature_progression_conflict`：从 ruby progression baseline 更新已有 `ruby_ore` worldgen，再更新 `ruby_progression` final mastery stage，并重复 progression update 验证幂等。

每个 modify step 会在 workspace 的 `.agent/eval-modify-steps/<step>/` 保存 `decomposed-modify/`、`patch-agent-report.json`、`prompt-trace.json`、`audit-report.json` 等快照，避免连续 modify 覆盖上一轮证据。建议查看：

- `workspace/eval-runs/decomposed-modify-cross-feature-stress/.agent/eval-report.md`
- `workspace/eval-runs/decomposed-modify-cross-feature-stress/01-modify_cross_feature_item_tool_recipe_worldgen-base/.agent/eval-modify-steps/add_tool_recipe/decomposed-modify/feature-patches.json`
- `workspace/eval-runs/decomposed-modify-cross-feature-stress/02-modify_cross_feature_progression_conflict-base/.agent/eval-modify-steps/update_progression_final_stage/decomposed-modify/merge-preview.json`

### Real-provider full eval and manual stress smoke

full real eval 通过 run：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --cases examples/decomposed_modify_cross_feature_stress.json --planner decomposed --llm-provider openai-compatible --require-llm --audit --no-build --limit 1 --run-name real-decomposed-modify-cross-feature-stress-behavior-fix-retry1 --json
```

结果：`real-decomposed-modify-cross-feature-stress-behavior-fix-retry1` 使用真实 provider 跑通 full eval 单 case，`success_rate=1.0`，expected features `3/3`，expected categories `9/9`，audit `1/1`，3 个 modify steps 全成功，real modify LLM calls `6`，total tokens `27,854`，max input tokens per call `4,243`，`decomposed_modify_used_rate=1.0`，`repeat_modify_success_rate=1.0`。本轮暴露并修复了 real provider 输出 `behavior: "right_click_heal"` 且把 `heal_amount/cooldown_seconds` 放在同层时，旧 normalization/merge 会丢 behavior 的 schema drift；修复后最终 `ruby_charm` 保留 `behavior.type=right_click_heal`、`amount=4.0`、`cooldown_ticks=400`。

证据路径：

- `workspace/eval-runs/real-decomposed-modify-cross-feature-stress-behavior-fix-retry1/.agent/eval-report.json`
- `workspace/eval-runs/real-decomposed-modify-cross-feature-stress-behavior-fix-retry1/.agent/eval-report.md`
- `workspace/eval-runs/real-decomposed-modify-cross-feature-stress-behavior-fix-retry1/01-modify_cross_feature_item_tool_recipe_worldgen-base/.agent/eval-modify-steps/add_behavior_item/decomposed-modify/feature-patches.json`
- `workspace/eval-runs/real-decomposed-modify-cross-feature-stress-behavior-fix-retry1/01-modify_cross_feature_item_tool_recipe_worldgen-base/.agent/modspec.json`

边界：该 run 使用 `--no-build`，证明的是 real provider setup + decomposed modify + audit + trace，不证明 Gradle build，也不证明 Minecraft runtime 自动验收。

旧 full real eval provider-error 边界：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --cases examples/decomposed_modify_cross_feature_stress.json --planner decomposed --llm-provider openai-compatible --require-llm --audit --no-build --limit 1 --run-name real-decomposed-modify-cross-feature-stress-smoke --json
```

`real-decomposed-modify-cross-feature-stress-smoke` 和 `real-decomposed-modify-cross-feature-stress-smoke-retry1` 都在 setup generation 阶段遇到 `LLM provider returned HTTP 500`，`success_rate=0.0`，`require_llm=true`，`modify_llm_calls=0`；`real-decomposed-modify-cross-feature-stress-behavior-fix` 后续遇到 `LLM provider returned HTTP 403`，同样是 setup 阶段、`modify_llm_calls=0`。这些 run 说明 `--require-llm` 没有 silent fallback，provider/auth 错误会保留为 provider_error，不能表述成通过。

manual real-provider stress smoke：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent develop "Create a ruby mod with ruby." --planner decomposed --llm-provider mock --workspace-name real-cross-feature-modify-stress-smoke --overwrite --no-build
py -3.11 -m agent.cli agent modify real-cross-feature-modify-stress-smoke "Add a ruby charm item that heals 4 health on right click with 20 seconds cooldown." --planner decomposed --llm-provider openai-compatible --require-llm --no-build
py -3.11 -m agent.cli agent modify real-cross-feature-modify-stress-smoke "Add a ruby pickaxe crafted from three rubies and two sticks." --planner decomposed --llm-provider openai-compatible --require-llm --no-build
py -3.11 -m agent.cli agent modify real-cross-feature-modify-stress-smoke "Add ruby ore worldgen in the overworld, Y -64 to 32, vein size 6, 4 per chunk." --planner decomposed --llm-provider openai-compatible --require-llm --no-build
py -3.11 -m agent.cli build real-cross-feature-modify-stress-smoke --json
```

| Step | Provider calls | Total tokens | Audit checks | Patch-agent | Evidence |
|---|---:|---:|---:|---|---|
| `ruby_charm` behavior item | `3` | `6,771` | `67` | `pass` | `.agent/manual-real-cross-feature-smoke/step-01-ruby-charm/` |
| `ruby_pickaxe` + recipe | `3` | `7,130` | `90` | `pass` | `.agent/manual-real-cross-feature-smoke/step-02-ruby-pickaxe-recipe/` |
| `ruby_ore` worldgen | `2` | `6,905` | `127` | `pass` | `.agent/manual-real-cross-feature-smoke/step-03-ruby-ore-worldgen/` |

结果：三步实际 provider 均为 `openai-compatible`，planner 均为 `decomposed`，audit 均为 0 errors / 0 warnings；最终 Gradle build `exit_code=0`，jar `workspace/real-cross-feature-modify-stress-smoke/build/libs/ruby_mod-0.1.0.jar`。real provider 暴露的 nested `behavior.right_click.heal` 和 recipe `{item: ...}` key object 已沉淀为 deterministic normalization，audit 也新增非法 recipe resource reference guard。该 smoke 证明 mock baseline 上的连续 real modify + audit/build follow-up，不证明 full real eval build，也不证明 Minecraft runtime 自动验收。

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
