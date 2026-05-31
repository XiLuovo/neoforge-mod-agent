# Version History

> 文档定位：这是历史版本查证文件，不建议从头读。当前边界见 [`project-limitations.md`](project-limitations.md)。

> 历史边界说明：本文保留每个版本发布时的原始说法。V8.4 之前出现的“LLM 只输出 ModSpec / 不直接写 Java / ModSpec-only”属于 historical boundary，不代表当前最新架构。current boundary 是 `ModSpec-first hybrid`：默认不让 LLM 裸写工程文件；当 `ModSpec` 表达不足时，允许 Direct Code Lane 产出 structured Direct Code Patch，并强制 `review -> snapshot -> audit -> build -> rollback evidence`。当前口径以 [`project-limitations.md`](project-limitations.md)、[`direct-code-lane.md`](direct-code-lane.md) 和 [`agent-workflow.md`](agent-workflow.md) 为准。

## V8.5 Capability Harvest Loop

目标：把后续主线从“让 Direct Code Lane 越来越像通用 coding agent”改成“让 LLM 在隔离实验区探索 generate gap，成功后再固化回稳定 generator”。

完成内容：

- 新增 `agent lab-generate "<request>" --from-workspace <workspace> --run-name <name> --build --json`。
- 新增 `harvest-report --run-name <name> --json`。
- package metadata 更新到 `8.5.0`。
- 新增 `FreeCodeLabRunner`，复制已有 generated workspace 到 `workspace/free-code-lab-runs/<run-id>/workspace`，只在实验副本里应用结构化补丁。
- Free-Code Lab 写入 `free-code-plan.json`、`free-code-plan.md`、`free-code-diff.md`、`free-code-report.json`、`manual-runtime-checklist.md` 和 `harvest-candidate.json`。
- 新增 `HarvestReportRunner`，聚合所有 Free-Code Lab candidate，输出 `workspace/harvest-runs/<run-id>/.agent/harvest-report.json` 和 Markdown 报告。
- 新增安全边界：拒绝绝对路径、路径穿越、`.git`、`gradle/wrapper`、build 输出、二进制产物、工具源码路径和危险 Java token。
- 同名 lab run 不覆盖，避免误删实验证据。
- 能力矩阵和 tool manifest 新增 `free_code_lab`、`capability_harvest_report`、`capability_harvest_loop`、`free_code_lab_generate` 和 `harvest_report`。
- 第一批固化方向记录为高级 machine GUI / BlockEntity 能力增强。
- 新增文档 [capability-harvest-loop.md](capability-harvest-loop.md)。

快速验证：

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_free_code_lab tests.test_cli_parser tests.test_capabilities tests.test_tool_manifest -v
py -3.11 -m agent.cli harvest-report --run-name local-harvest --json
```

边界：

- Free-Code Lab 是实验隔离区，不是稳定生成路径。
- 实验成功不会自动修改 generator。
- `harvest_into_generator` 必须依赖人工 runtime checklist、工程整理和回归测试。
- 第一版仍使用结构化 `write_file` / `replace_text`，方便审计和回放。

## V8.4 ModSpec-First + Direct Code Lane

目标：把 agent 从“只能输出 ModSpec/DSL”的单一路径升级为 `ModSpec-first` 混合架构。默认仍优先生成可审计的 `ModSpec`，当需求超出 ModSpec 表达能力时，进入 Direct Code Lane，以结构化补丁的方式修改生成 workspace。

完成内容：

- `agent generate` / `agent modify` 新增 `--code-lane {hybrid,modspec,direct}`，默认 `hybrid`。
- 新增 Direct Code Plan / Review / Apply 证据链，只允许 JSON `write_file` 和精确一次 `replace_text`。
- Direct Code Lane 限定在生成 workspace 内，禁止绝对路径、路径越界、`.git`、Gradle wrapper jar、build output 和工具项目源码。
- Runtime 的 stage state 扩展为 intent contract，可记录 `modspec`、`direct_code_plan` 和 `routing_decision`。
- Replay evidence 新增 `direct_code_reviewer` / `direct_code_agent` 角色输出。
- 每次 Direct Code apply 写入 plan、review、diff、report、rollback report 和 affected-file snapshots。
- Direct Code Lane 强制 audit plus Gradle build；失败时 run 不算成功，并把 rollback 标记为 recommended。
- 新增文档 [direct-code-lane.md](direct-code-lane.md) 和 [project-limitations.md](project-limitations.md)。

快速验证：

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli agent generate "Create a ruby mod with a custom helper outside ModSpec." --planner llm --llm-provider mock --code-lane hybrid --workspace-name v84-direct-code-smoke --overwrite --build --json
```

边界：

- Direct Code Lane 不是通用 coding agent，不接受自由 diff。
- 第一版没有 AST patch、自动 direct-code repair-loop、事务式自动恢复或 Minecraft runtime smoke 自动化。
- 当前本地回归基线：`py -3.11 -m unittest discover -s tests -v` 通过 163 个 unittest case。

## V8 Resource Quality Upgrade

目标：把资源从“只有占位图”推进到“可描述、可审计、可预览”的质量层，为后续材质 profile、模型 variant、结构预览图和 dashboard 可视化打基础。

完成内容：

- package metadata 更新到 `8.0.0`。
- `texture-manifest.json` 的每条 texture 新增 `quality_profile`、主色 `dominant_rgba` 和 `palette`。
- 新增 `.agent/resource-quality-report.json` 和 `.agent/resource-quality-report.md`，汇总 texture profile、模型 variant、结构预览和 dashboard-ready 摘要。
- 新增 `.agent/texture-atlas.png`，把生成贴图拼成静态像素 atlas，方便 dashboard 和作品集快速查看。
- 对 `structure` DSL 生成 `.agent/previews/<structure>.png` 俯视示意图，作为结构预览证据。
- `audit` 新增 V8 resource quality 检查，验证 report、atlas 和结构预览 PNG。
- `dashboard` 新增 `Resource Preview` 区块，展示 atlas、profile 统计、模型 variant 数量和结构预览图。
- 能力矩阵新增 `resource_quality_profiles`、`texture_atlas_preview`、`model_variant_report`、`structure_preview`、`dashboard_resource_preview` 和 `resource_quality_audit`。
- 新增示例 `examples/resource_quality_showcase.json` 和文档 `docs/resource-quality-upgrade.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_generation_audit tests.test_dashboard tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\resource_quality_showcase.json --workspace-name v80-resource-smoke --overwrite --audit --no-build --json
py -3.11 -m agent.cli dashboard --run-name v80-resource-dashboard --json
```

边界：

- V8 仍是确定性程序化资源，不是最终美术资源。
- `texture-atlas.png` 和结构预览图用于展示与审计，不是游戏内 runtime 资源。
- 结构预览是 schematic PNG，不是 NBT 结构渲染。
- 后续接 AI 贴图、用户贴图或真实结构截图时，应继续沿用 report / manifest 接口。

## V7.2 Quest / Advancement / Guide DSL

目标：把 V7 玩法线变成玩家能看见的目标，生成任务链、advancement、引导文本和 Patchouli-style guidebook 结构，让演示时不再需要用户猜玩法路线。

完成内容：

- package metadata 更新到 `7.2.0`。
- `ModSpec` 新增 `quest` / `quests`，支持 `target_progression`、`guidebook_id`、`category` 和结构化 `tasks`。
- 新增 `QuestGuideGenerator`，输出 `.agent/quest-report.json`、`.agent/quest-report.md`、`.agent/guidebook.md`。
- 生成 `data/<modid>/advancement/<quest>/<task>.json`，覆盖 obtain、craft、mine、machine、kill、dimension、structure 和 milestone 任务类型。
- 生成 Patchouli-style `book.json`、category JSON 和 entry JSON，作为 guidebook 数据结构证据。
- validator 检查 quest id、task id、task type、parent 链、目标 progression 引用和任务目标引用。
- audit / generation-summary / manual checklist / capabilities / rules planner / mock LLM 均接入 V7.2。
- 新增示例 `examples/quest_guide_gameplay_loop.json` 和文档 `docs/quest-guide-dsl.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_quest_guide_dsl tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\quest_guide_gameplay_loop.json --workspace-name v72-quest-smoke --overwrite --audit --no-build --json
```

边界：

- V7.2 是数据驱动任务 / 成就 / 指南结构，不是完整自定义任务运行时。
- Patchouli-style JSON 会被生成，但不会自动添加 Patchouli Gradle 依赖。
- 复杂剧情触发、跨维度脚本和任意 Java 逻辑仍属于后续受控扩展。

## V7.1 Recipe / Loot / Balance Planner

目标：让系统不只生成内容和玩法线，还能把配方、掉落、稀有度、机器耗时、能量消耗和战利品权重组织成一份可审计经济规划。

完成内容：

- package metadata 更新到 `7.1.0`。
- `ModSpec` 新增 `balance_plan` / `balance_plans`，可指向已有 `progression`。
- 新增 `BalancePlanGenerator`，输出 `.agent/balance-report.json` 和 `.agent/balance-report.md`。
- 报告覆盖已有配方建议、缺失配方建议、稀有度分配、机器 `max_progress` / `energy_per_tick` / `total_energy`、实体掉落概率、loot 权重和 economy summary。
- validator 检查 balance plan id、profile、目标 progression 引用，以及是否有可分析的经济对象。
- audit / generation-summary / capabilities / rules planner / mock LLM 均接入 V7.1。
- 新增示例 `examples/balance_gameplay_loop.json` 和文档 `docs/balance-planner.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_balance_planner tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\balance_gameplay_loop.json --workspace-name v71-balance-smoke --overwrite --audit --no-build --json
```

边界：

- V7.1 是 report-only 经济规划层，不直接改写任意 Java 或复杂玩法逻辑。
- 平衡建议可解释、可审计、可回放，但不能替代游戏内人工经济测试。
- 后续可以在受控 patch / apply 模式里把建议安全落回 `ModSpec`。

## V7 Progression / Gameplay Loop DSL

目标：让生成器不只生成一堆 feature，而是能表达一条玩家可游玩的成长路线：矿物 -> 材料 -> 机器加工 -> 装备 / 道具 -> 实体掉落 -> 结构战利品 -> 维度推进。

完成内容：

- package metadata 更新到 `7.0.0`。
- `ModSpec` 新增 `progression` / `progressions`，覆盖 stage、link、entry/end stage、requires/provides/unlocks/evidence。
- 新增 `ProgressionGenerator`，输出 `.agent/progression-report.json` 和 `.agent/progression-report.md`。
- validator 检查 progression id、stage type、link 引用、入口到终点可达性、循环提示，以及 evidence / requires / provides / unlocks 是否能解析到已有 ModSpec 对象或外部资源。
- audit / generation-summary / manual checklist / capabilities / rules planner / mock LLM 均接入 V7。
- 新增示例 `examples/progression_gameplay_loop.json` 和文档 `docs/progression-dsl.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_progression_dsl tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\progression_gameplay_loop.json --workspace-name v70-progression-smoke --overwrite --audit --no-build --json
```

边界：

- V7 是玩法线 DSL 和证据报告，不是任意任务系统、成就树、剧情脚本或 Java patch。
- stage evidence 必须尽量引用现有 ModSpec feature；未知引用会进入 warning 和 report 的 missing references。
- 实际机器配方、维度门逻辑、复杂剧情推进仍属于后续扩展。

## V6.1 Controlled Java Extension Acceptance Loop

目标：把 V6 的“受控新增 Java class”补成可证明版本，让演示时能说清楚：允许一点 Java，但必须经过 sandbox、diff、rollback、audit 和 Gradle build gate。

完成内容：

- package metadata 更新到 `6.1.0`。
- `.agent/java-extension-report.json` 新增 `build_gate`，在 `--build` 后回填 `pass` / `fail`，`--no-build` 时保持 `not_run`。
- 新增 `.agent/java-extension-diff.md`，把每个 extension class 渲染成 new-file diff，证明只新增托管 class。
- 新增 `.agent/java-extension-rollback-report.json` / `.md`，build 失败时标记 rollback recommended，并列出 managed files 和回滚步骤。
- 新增 sandbox 违规样例 `examples/invalid/controlled_java_extension_violation.json`，用于证明非法 import / forbidden token 会在生成前被拒绝。
- README 和 V6 文档补充 V6.1 demo 证据链。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_generation_audit tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli generate-from-spec .\examples\controlled_java_extension.json --workspace-name v61-java-extension-smoke --overwrite --audit --no-build --json
py -3.11 -m agent.cli generate-from-spec .\examples\controlled_java_extension.json --workspace-name v61-java-extension-build --overwrite --audit --build --json
```

边界：

- V6.1 仍然不是任意 Java patch 生成器。
- build gate 是验收证据，不是绕过 validator/audit 的许可。
- rollback 报告只处理 generated managed extension files，不会删除或修改用户手写文件。

## V6.2 Controlled Patch Agent

目标：把 `modify` 路径显式升级成受控 patch-agent。LLM 先输出 patch plan，系统只修改 managed files，并在执行后补齐 audit / build / rollback 证据。

完成内容：

- 新增 `.agent/patch-agent-plan.json` / `.md`，记录 patch plan、managed-file policy、before/after ModSpec、增删改跳过统计和 rollback steps。
- 新增 `.agent/patch-agent-report.json` / `.md`，记录 patch 执行结果、audit/build/repair gate、managed files 和最终成功状态。
- 新增 `.agent/patch-agent-rollback-report.json` / `.md`，在 audit 或 build 失败时给出 rollback 建议。
- `modify` 和 `agent modify` 现在明确通过 patch plan 驱动 managed-file regeneration，而不是让 LLM 直接改整个 repo。
- Capability matrix 和工作流说明同步补齐 patch-agent boundary。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m unittest tests.test_agent_eval tests.test_web_demo tests.test_capabilities -v
py -3.11 -m agent.cli modify .\workspace\demo --planner llm --llm-provider mock --json
```

边界：

- 仍然不是裸 repo patch。
- 只允许 managed files；用户手写文件不在 overwrite scope 内。
- patch-agent 的最终接受条件仍然是 audit / build / rollback 证据链。

## V6 Controlled Java Extension

目标：在不放开任意 Java patch 的前提下，给生成器增加一个受控 Java 扩展口。LLM / rules 仍然只能输出结构化 `ModSpec`，确定性生成器只在 `<package>.extension` 下新增托管 class。

完成内容：

- package metadata 更新到 `6.0.0`。
- `ModSpec` 新增 `java_extension` / `java_extensions`，覆盖 `class_name`、`purpose`、`explanation`、`allowed_imports` 和 String-returning `methods`。
- 新增 `JavaExtensionGenerator`，只生成 `src/main/java/<package>/extension/<ClassName>.java` 和 `.agent/java-extension-report.*`。
- validator / auditor 检查 class/method 命名、导入 allowlist、禁止 token、报告文件、package、final class 和 static method。
- rules planner / mock LLM / LLM schema / modify merge / capabilities / knowledge base / golden tests 接入 V6。
- 新增示例 `examples/controlled_java_extension.json` 和文档 `docs/controlled-java-extension.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_generation_audit tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli generate-from-spec .\examples\controlled_java_extension.json --workspace-name v60-java-extension-smoke --overwrite --audit --no-build --json
```

边界：

- V6 不是任意 Java patch 生成器。
- 不允许改已有源码、不允许 Gradle patch、不允许 raw package/import、不允许文件/网络/进程/反射/线程等危险 API。
- `--audit --no-build` 只证明结构和沙盒约束；正式验收仍需要 Gradle build gate。

## V5.4 World / Structure DSL

目标：把生成器从“内容、机器、生物”继续推进到数据驱动的世界玩法包，支持维度、群系、地物、矿脉规则、结构和战利品池。

完成内容：
- package metadata 更新到 `5.4.0`。
- `ModSpec` 新增 `dimension`、`biome`、`world_feature`、`structure`、`loot_pool` 五类 feature。
- `WorldgenGenerator` 新增 dimension type、dimension、biome、configured / placed feature、NeoForge biome modifier、jigsaw structure、structure set、template pool 和 chest loot table 生成。
- validator / auditor / rules planner / mock LLM / modify merge / checklist / capability matrix 均接入 V5.4 字段。
- 新增示例：`examples/world_ruby_realm.json`。

验证入口：

```powershell
py -3.11 -m agent.cli generate-from-spec .\examples\world_ruby_realm.json --workspace-name v54-world-smoke --audit --no-build --json
```

边界：
- 这是模板化 World / Structure DSL，不是任意 datapack / NBT / Java 生成器。
- 当前结构生成以 jigsaw 元数据、structure set 和 empty template pool 为主；真实结构 NBT 拼装、复杂地形噪声、多维度玩法逻辑仍在范围外。

## V5.3 Entity / Mob DSL

目标：把生成器从静态内容、行为模板、机器 GUI 推进到基础生物玩法，让它能生成怪物、宠物、Boss、NPC 这类实体骨架，同时继续保持 `ModSpec -> deterministic generator -> audit` 的边界。

完成内容：
- package metadata 更新到 `5.3.0`。
- `ModSpec` 新增 `entity` / `entities`，覆盖 `entity_kind`、实体分类、尺寸、追踪范围、经验、属性、掉落、生成规则、AI goals 和攻击方式。
- 新增 `EntityGenerator`，确定性生成 `EntityType` 注册、实体 Java 类、属性注册、客户端 renderer 注册类。
- 资源生成接入实体贴图、语言 key、实体 loot table 和 NeoForge `add_spawns` biome modifier。
- validator、audit、manual checklist、capability matrix、knowledge base、golden tests 和回归测试覆盖实体链路。
- 新增示例 `examples/entity_ruby_goblin.json` 和文档 `docs/entity-dsl.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest tests.test_generation_audit tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\entity_ruby_goblin.json --workspace-name v53-entity-smoke --audit --no-build --json
```

边界：
- 当前是模板化实体系统，不是任意 Java / 任意 AI / 任意动画生成。
- 稳定攻击模板为 `melee` 和 `none`；远程弹幕、复杂驯服、交易、Boss 阶段和模型动画属于后续路线。

## V5.2 BlockEntity + GUI

目标：把 V5.1 的“行为可组合”继续推进到“方块有状态、有容器、有界面”，让生成器能产出熔炉类机器、压缩机、升级台、魔法祭坛和储物方块这类更接近真实 Mod 的内容。

完成内容：
- package metadata 更新到 `5.2.0`。
- `ModSpec` 新增 `machine` / `machines`，覆盖 `machine_kind`、槽位数、能量容量、每 tick 能耗、最大进度和菜单标题。
- 新增 `MachineGenerator`，确定性生成机器 Block、BlockEntity、AbstractContainerMenu、客户端 Screen 和 Screen 注册类。
- 机器方块支持右键打开菜单，BlockEntity 持有 `SimpleContainer`、能量和进度字段，并用 `ContainerData` 同步到 GUI。
- 资源生成、loot table、mineable / tool tier 标签、语言文件和程序化机器贴图接入机器类型。
- planner 能从 furnace、compressor、upgrade table、magic altar、storage 以及中文机器关键词生成机器 spec。
- validator、audit、capability matrix、手工测试 checklist 和回归测试覆盖机器结构。
- 新增示例 `examples/machine_ruby_compressor.json` 和文档 `docs/machine-dsl.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli generate-from-spec .\examples\machine_ruby_compressor.json --workspace-name v52-machine-smoke --audit --no-build --json
```

边界：
- 当前是模板化机器系统，不是任意 Java / 任意 GUI 生成。
- 机器默认提供槽位、能量、进度、Menu、Screen 和数据同步骨架，复杂配方逻辑、能源网络、多方块结构和实体 AI 仍是后续路线。

## V5.1 Behavior DSL

目标：先把“行为”做通用，让生成器从静态物品/方块推进到受控玩法模板。

完成内容：
- 新增 `BehaviorEventSpec`、`BehaviorActionSpec`、`BehaviorConditionSpec`，支持 `event -> condition -> action` 结构。
- 支持右键触发、攻击命中、背包 tick、方块交互、条件判断、消耗物品、给予效果、生成粒子和播放声音。
- `BehaviorGenerator` 确定性生成对应的 Item / Sword / Block Java 子类，保持 LLM 只输出 `ModSpec`。
- 新增 `docs/behavior-dsl.md` 和 `examples/behavior_dsl_battle_charm.json`。
- validator、audit 和回归测试覆盖行为 DSL。

边界：
- Behavior DSL 不是任意 Java 生成，只覆盖受控触发器、条件和动作集合。
- 机器方块右键已保留给 GUI 打开动作，复杂机器逻辑进入 V5.2 的机器 DSL。

## V5.0 作品集发布版

目标：把 V4.x 已经具备的 generate、modify、RAG、multi-agent、audit、repair、eval、dashboard 能力收口成一个可以投简历、可以现场演示、可以讲 10 分钟的发布版。

完成内容：
- package metadata 更新到 `5.0.0`。
- README 顶部新增中文项目首页式说明，包含一句话介绍、核心链路、快速演示、面试材料和能力概览。
- 新增一键演示脚本 `scripts/v5_portfolio_demo.ps1`，默认使用 mock LLM，离线稳定可跑。
- 新增 `docs/portfolio-release.md`，说明 V5.0 演示路线和展示顺序。
- 新增 `docs/interview-script.md`，提供 30 秒和 10 分钟中文面试讲解稿。
- 新增 `docs/architecture.md`，提供 Mermaid 架构图、多 Agent 分工图和 LLM 边界图。
- 新增 `docs/demo-cases.md`，收集基础生成、行为物品、装备套装、worldgen、modify、self-healing 等典型 demo case。
- 新增 `docs/screenshots.md` 和 `docs/assets/.gitkeep`，记录项目截图清单和推荐文件名。
- Capability Matrix 新增 `portfolio_release_package`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli capabilities --run-name v50-capabilities --json
.\scripts\v5_portfolio_demo.ps1
```

边界：
- V5.0 不新增大型游戏内容类型，重点是作品集交付物和演示闭环。
- 默认 demo 不依赖真实 LLM API。
- Gradle build 默认关闭，避免现场演示耗时；需要时可以传 `-Build`。

## V4.7 真实 LLM Agent 稳定化

目标：让真实 OpenAI-compatible LLM 更适合现场演示。即使 provider 没配置、返回坏 JSON、返回不合法 ModSpec，系统也能留下诊断证据，并安全降级到确定性的 rules planner。

完成内容：
- 新增 `LLMProviderHealth` 和 `check_llm_provider_health`，默认做不联网的 config-only provider health check。
- `doctor` 会报告 LLM provider 健康状态，并给出 fallback 推荐。
- `plan_with_llm` 和 `plan_modification_with_llm` 支持 validator schema retry，不只重试 JSON 解析失败，也会重试不合法 ModSpec。
- 新增 `NEOFORGE_AGENT_LLM_SCHEMA_RETRIES` / `OPENAI_SCHEMA_RETRIES`，默认 schema retry 为 1 次。
- `agent generate`、`modify`、普通 `generate` 的 LLM 路径都支持失败降级，planner mode 会显示为 `llm->rules` 或 `auto->rules`。
- RAG artifact 新增 `rag_quality`，记录 hit 数量、top score、平均分、分类覆盖和质量等级。
- prompt trace 和 agent trace 会带上 provider health、schema retry attempts、schema validation attempts、RAG quality。
- `.agent/llm-stability.json` 记录 provider health、JSON repair、parse attempts 和 schema validation attempts。
- Capability Matrix 新增：
  - `real_llm_health_check`
  - `llm_schema_retry`
  - `llm_rules_fallback`
- package metadata 更新到 `4.7.0`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_llm_stability tests.test_agent_eval tests.test_capabilities tests.test_dashboard -v
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli agent generate "做一个红宝石模组，添加红宝石。" --planner llm --llm-provider openai-compatible --workspace-name v47-real-llm-fallback --overwrite --json
py -3.11 -m agent.cli capabilities --run-name v47-capabilities --json
```

边界：
- 默认 health check 不联网，只检查配置完整性，避免测试依赖真实 API。
- LLM 仍然不能直接写 Java、JSON、PNG 或 Gradle。
- 降级到 rules 后，项目仍通过 deterministic generator、audit、build、repair 链路。

## V4.6 RAG 引用链增强

目标：把“用了 RAG”升级成“可解释 RAG”，让 planner / repair 的关键决策都能回溯到具体 knowledge id。

完成内容：
- `AgentDecision` 新增 `knowledge_ids` 和 `knowledge_refs`。
- planner decision 会记录 `PlannerArtifacts.used_knowledge` 中的知识条目。
- repair decision 会记录 `repair_rag.hits` 中的知识条目。
- `.agent/agent-decisions.md` 显示每条决策引用的 knowledge id。
- `.agent/agent-trace-summary.json` 增加 role 级别的 knowledge 引用聚合。
- Dashboard 新增 `RAG Citation Chain` 区块。
- Capability Matrix 新增：
  - `explainable_rag_citations`
  - `dashboard_rag_citation_chain`
- package metadata 更新到 `4.6.0`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest tests.test_agent_eval tests.test_dashboard tests.test_capabilities tests.test_replay -v
py -3.11 -m agent.cli agent generate "做一个红宝石模组，添加红宝石护符，右键回复4点生命值，冷却20秒。" --planner llm --llm-provider mock --workspace-name v46-rag-citations --overwrite --json
py -3.11 -m agent.cli dashboard --run-name v46-dashboard --json
```

## V4.5 Repair Eval 报告

目标：把自修复能力从“能演示”升级成“可量化”，让简历和面试里可以直接讲成功率、命中率和恢复率。

完成内容：

- 新增 `repair_eval.py`，提供 `RepairEvalRunner`。
- 新增 CLI 命令：`repair-eval`。
- `repair-eval` 会复用 V4.4 Failure Lab 的故障样例，并统计：
  - audit 是否发现预期故障。
  - repair RAG 是否命中与故障类型相关的知识能力。
  - repair-loop 是否完成安全修复。
  - 修复后 audit 是否恢复。
  - 完整闭环成功率。
- 新增报告：
  - `workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.json`
  - `workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.md`
- Failure Lab case 结果新增：
  - `expected_rag_capabilities`
  - `repair_rag_knowledge_ids`
  - `repair_rag_capabilities`
  - `repair_rag_categories`
  - `repair_rag_relevant`
- `quality-gate` 默认加入 `repair_eval` check，可用 `--no-repair-eval` 跳过。
- Capability Matrix 新增 `repair_eval`。
- package metadata 更新到 `4.5.0`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli repair-eval --run-name v45-repair-eval --json
py -3.11 -m unittest tests.test_repair_eval tests.test_failure_lab tests.test_cli_parser tests.test_quality_gate tests.test_capabilities -v
py -3.11 -m agent.cli quality-gate --run-name v45-quality-gate --json
```

## V4.4 Failure Lab / 故障注入测试

目标：证明系统不是 happy path demo，而是能对典型坏项目完成“发现问题、解释原因、给出修复证据、执行安全修复”的闭环。

完成内容：

- 新增 `failure_lab.py`，提供 `FailureLabRunner`。
- 新增 CLI 命令：`failure-lab`。
- 默认注入 5 类故障：
  - 删除生成 texture。
  - 删除生成 model。
  - 删除 ore worldgen configured_feature JSON。
  - 删除 behavior item 自定义 Java 类。
  - 破坏实际 recipe JSON 中的引用。
- 每个 case 都会执行：
  - 生成干净 workspace。
  - 注入故障。
  - 运行 `audit`，确认能检测到预期失败。
  - 运行 `RepairRAGAdvisor`，写出 repair RAG 上下文。
  - 运行 `repair-loop`，基于 `.agent/modspec.json` 重生成 managed files。
  - 再次确认 audit 通过。
- `auditor.py` 增强：现在会检查实际 recipe JSON 文件里的 `result`、`key`、`ingredients` 引用，而不只检查 ModSpec recipe 字段。
- `quality-gate` 默认加入 Failure Lab，可用 `--no-failure-lab` 跳过。
- Capability Matrix 新增 `failure_lab`。
- package metadata 更新到 `4.4.0`。

边界：

- Failure Lab 只在隔离的 `workspace/failure-lab-runs/<run-id>/workspaces` 下制造坏项目。
- repair RAG 只提供证据和解释，不直接改 Java / JSON / PNG。
- repair-loop 仍然只基于 `.agent/modspec.json` 重生成 managed files。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli failure-lab --run-name v44-failure-lab --json
py -3.11 -m unittest tests.test_failure_lab tests.test_cli_parser tests.test_quality_gate tests.test_capabilities -v
py -3.11 -m agent.cli quality-gate --run-name v44-quality-gate --json
```

## V4.3 Repair RAG 可视化增强

目标：把 V4.2 的 repair RAG 上下文从“藏在 JSON/MD artifact 里”升级成可展示、可回放、可讲述的证据链，方便解释 Agent 为什么选择某个修复动作。

完成内容：

- Dashboard 的 `Self-Healing Repair` 区域新增：
  - repair RAG query
  - repair RAG hit count
  - 命中的 knowledge id
  - root cause / repair action / knowledge 的确定性映射卡片
- `replay` 新增 `repair_rag` 回放事件。
- replay metrics 新增：
  - `repair_rag_events_count`
  - `repair_rag_hits_count`
- Web Demo 的 Self-Healing 页新增：
  - `Repair RAG` 摘要
  - RAG query
  - categories / capabilities
  - RAG hit 列表
  - root cause -> action -> knowledge 映射
- Capability Matrix 新增：
  - `dashboard_repair_rag`
  - `web_demo_repair_rag`
  - `replay_repair_rag`
- package metadata 更新到 `4.3.0`。

边界：

- 这版只增强可视化和回放，不改变 safe repair loop 的执行策略。
- RAG 仍然只提供证据和解释，不自动应用补丁。
- LLM 仍然不能直接写 Java / JSON / PNG / Gradle。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest tests.test_replay tests.test_web_demo tests.test_dashboard tests.test_capabilities -v
py -3.11 -m agent.cli dashboard --run-name v43-dashboard --json
py -3.11 -m agent.cli web-demo --smoke --json
```

## V4.2 更强 RAG + Repair 联动

目标：让 `repair_agent` 在 audit/build 失败时，不只给出 root causes 和 safe repair loop，还能自动检索本地 NeoForge RAG 知识库，把相关规则、约束和排查提示写入 repair artifacts。

完成内容：

- 新增 `repair_rag.py`，提供 `RepairRAGAdvisor` 和 `RepairRAGResult`。
- `agent generate` / `agent modify` 的 repair payload 新增 `repair_rag`。
- audit/build 失败时生成：
  - `.agent/repair-rag-context.json`
  - `.agent/repair-rag-context.md`
- `.agent/agent-repair-plan.md` 新增 `Repair RAG Context` 区块。
- Dashboard 新增 repair RAG 指标和 artifact 链接。
- Capability Matrix 新增 `repair_rag`。
- package metadata 更新到 `4.2.0`。

边界：

- RAG 不调用真实 LLM。
- RAG 不自动修改 Java / JSON / PNG / Gradle 文件。
- RAG 不影响 repair 成败判定；即使没有命中知识，也不会掩盖原始失败。
- safe repair loop 仍然只会基于 `.agent/modspec.json` 重生成 managed files。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest tests.test_repair_rag tests.test_agent_eval tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli capabilities --run-name v42-capabilities --json
```

## V4.1 Agent Run Replay / 历史运行回放

目标：让已经保存下来的 `.agent/agent-run.json` 可以被离线回放，形成一份按时间线组织的中文报告，方便面试展示和问题复盘。

完成内容：

- 新增 `replay.py`。
- 新增 CLI 命令：`replay <target> [--json]`。
- `target` 支持：
  - workspace 路径或 workspace 名称
  - `.agent` 目录
  - 直接的 `agent-run.json` 文件路径
- 回放不会重新执行：
  - LLM provider
  - generator
  - audit
  - build
  - repair
- 回放报告会整理：
  - run metadata
  - role steps
  - decisions
  - prompt traces
  - RAG hit / used knowledge 统计
  - JSON repair / retry 统计
  - artifact 路径索引
- 新增 artifact：
  - `.agent/agent-run-replay.json`
  - `.agent/agent-run-replay.md`
- Capability Matrix 新增 `agent_replay`。
- package metadata 更新到 `4.1.0`。

价值：

- 面试时可以展示历史 agent run 的完整证据链，而不必每次现场重跑。
- 调试时可以快速复盘 planner、reviewer、executor、auditor、repair agent 的输入、输出、决策和失败点。
- 继续保持确定性边界：replay 只读历史 artifact，不让 LLM 或 generator 参与。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent generate "Create a ruby mod with ruby." --planner llm --llm-provider mock --workspace-name v41-replay-source --overwrite --no-build --json
py -3.11 -m agent.cli replay workspace/v41-replay-source --json
```

## V4.0 作品集级一键演示模式

目标：把已经完成的 generate、modify、agent trace、RAG、dashboard、LLM eval、repair 和 capability matrix 串成一次适合简历与面试展示的一键离线 Demo。

完成内容：

- 新增 `portfolio_demo.py`。
- 新增 CLI 命令：`portfolio-demo`。
- `portfolio-demo` 默认使用 mock LLM，不依赖真实 API，也默认不跑 Gradle build。
- 一键流程包含：
  - `doctor`
  - `showcase`
  - `dashboard`
  - `llm-eval-report`
  - `web-demo --smoke`
  - `capabilities`
- 新增组合报告：
  - `workspace/portfolio-runs/<run-id>/.agent/portfolio-demo-report.json`
  - `workspace/portfolio-runs/<run-id>/.agent/portfolio-demo-report.md`
- Markdown 报告使用中文叙事，包含项目一句话介绍、演示链路、关键 artifact、面试讲解重点和下一步展示方式。
- Capability Matrix 新增 `portfolio_demo`。
- package metadata 更新到 `4.0.0`。

价值：

- 面试时可以用一条命令复现完整 Agent 工程闭环，而不是手动串多个命令。
- 默认离线可跑，适合没有真实 LLM key 的演示环境。
- 保持核心边界：LLM 只输出 ModSpec、patch 或 repair plan，Java / JSON / PNG / Gradle 文件仍由 deterministic generator 产出。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli portfolio-demo --run-name v40-portfolio --eval-limit 1 --json
```

## V3.9 真实 LLM 评测与对比报告

目标：把真实 LLM provider 纳入可重复评测和对比报告，而不是只靠单次手工试跑判断效果。

完成内容：

- 新增 `llm_eval_report.py`。
- 新增 CLI 命令：
  - `llm-eval-report`
- `llm-eval-report` 会执行：
  - mock baseline eval
  - candidate eval
  - eval-compare
  - 汇总 `llm-eval-report.json` 和 `llm-eval-report.md`
- candidate provider 支持：
  - `mock`
  - `openai-compatible`
- 默认测试仍然不依赖真实 LLM：
  - `--candidate-provider mock` 可完整跑通 baseline / candidate / compare
  - 缺少真实 provider 配置时，默认安全跳过 candidate eval
  - 使用 `--require-real` 时，真实 provider 未配置会返回失败
- 报告会记录 provider 预检信息：
  - API key 是否存在，但不暴露密钥
  - base URL
  - model
  - timeout / retry 配置
- Capability Matrix 新增：
  - `llm_eval_report`
  - `real_llm_eval_compare`
  - `llm_eval_preflight`
- package metadata 更新到 `3.9.0`。

价值：

- 可以把“真实 LLM 效果如何”变成可复现的 benchmark 报告。
- 面试时可以展示 mock baseline 与真实模型 candidate 的成功率、规划率、audit 率、RAG 命中率和 regressions。
- 继续保持边界：真实 LLM 只输出 `ModSpec`，不直接写 Java / JSON / PNG。

## V3.8 Self-Healing Agent Demo / Repair 可视化

目标：把 V3.7 的 repair agent 安全自动修复能力从“隐藏在 JSON 里”推进到“Web Demo 和 Dashboard 中可讲、可看、可追踪”。

完成内容：

- `web_demo.py` 的 generate / modify payload 新增 `repair` 和 `self_healing` 摘要。
- `GET /api/workspace` 现在会读取：
  - `.agent/agent-repair-plan.json`
  - `.agent/repair-loop-report.json`
  - 并返回 `repair_plan`、`repair_loop`、`self_healing`
- Web Demo 页面新增 `Self-Healing` 标签页，展示：
  - `Repair Agent`
  - `Repair Loop`
  - `repair_needed`
  - `repair_executed`
  - `repair_success`
  - root causes
  - repair attempts
  - repair artifact 路径
- `dashboard.py` 新增 `Self-Healing Repair` 区块，汇总 repair runs、needed、executed、success 和 attempts。
- Dashboard artifact 链接新增 agent repair plan 和 repair loop report。
- Capability Matrix 新增：
  - `web_demo_self_healing`
  - `dashboard_repair_summary`
  - `self_healing_demo`
- package metadata 更新到 `3.8.0`。

价值：

- 面试演示时可以直接讲清楚“Agent 如何发现生成项目损坏，并在安全边界内恢复受控文件”。
- repair 不再只是命令行或 JSON artifact，而是进入可视化演示链路。
- 仍然保持核心原则：LLM 不直接写 Java / JSON / PNG，只输出 `ModSpec` 或 repair plan；修复动作由 deterministic repair loop 执行。

## V3.7 Repair Agent 增强

目标：让 repair agent 不再只是“失败后写一份修复建议”，而是在明确安全边界内自动执行确定性修复。

完成内容：

- `AgentOrchestrator` 接入 `AutoRepairRunner`。
- `agent generate` / `agent modify` 在 audit 或 build 失败时，会自动执行一次 safe repair loop。
- 修复动作仍然只有安全动作：
  - 从 `.agent/modspec.json` 读取真相源
  - 重生成受控 Java / JSON / PNG / lang / model / worldgen / pack metadata
  - 重新运行本次请求过的 audit/build 检查
- `repair_agent` payload 新增：
  - `repair_executed`
  - `repair_success`
  - `repair_loop`
  - `repair_loop_report_json_path`
  - `repair_loop_report_md_path`
- `.agent/agent-repair-plan.md` 会展示 repair-loop 执行摘要。
- 如果安全修复成功，agent run 最终可以恢复为 `success=true`。
- capability matrix 新增：
  - `repair_agent_execute`
  - `safe_repair_execution`
- package metadata 更新到 `3.7.0`。

价值：

- audit/build 发现受控生成文件缺失或损坏时，Agent 可以自己恢复，不需要用户手动再跑 `repair-loop`。
- 仍然不让 LLM 直接改源码，风险低，适合简历中讲“可验证、可恢复的 Agent 工程闭环”。
- 修复全过程有 `.agent` artifacts，可用于复盘和 Web/Dashboard 展示。

## V3.6 真实 LLM 稳定化

目标：让真实 OpenAI-compatible LLM 在本地 Demo 和多 Agent 链路中更稳定、更好诊断，同时继续保持“LLM 只输出 ModSpec，确定性 generator 负责 Java/JSON/PNG”的边界。

完成内容：

- `llm_client.py` 新增 provider 配置检查：
  - 支持 `NEOFORGE_AGENT_LLM_BASE_URL`
  - 支持 `NEOFORGE_AGENT_LLM_API_KEY`
  - 支持 `NEOFORGE_AGENT_LLM_MODEL`
  - 支持 `NEOFORGE_AGENT_LLM_TIMEOUT_SECONDS`
  - 支持 `NEOFORGE_AGENT_LLM_MAX_RETRIES`
  - 兼容 `OPENAI_*` 环境变量
- `OpenAICompatibleClient` 新增 provider 请求重试和 timeout 配置。
- `llm_planner.py` 新增 JSON 修复：
  - Markdown code fence
  - 前后解释文本
  - 平衡 JSON object 提取
  - 尾逗号修复
- planner 在 JSON 解析失败后会重试，并把过程记录到 `.agent/llm-stability.json`。
- `doctor` 新增 `llm.openai_compatible` 检查，离线检查真实 LLM 配置，不联网，不暴露 API Key。
- capability matrix 新增：
  - `llm_provider_config_check`
  - `llm_json_repair`
  - `llm_retry`
- multi-agent prompt trace 记录 parse attempts、retry attempts、provider config 摘要和 JSON repair 状态。
- package metadata 更新到 `3.6.0`。

价值：

- 真实 LLM 输出不稳定时，系统能先自动修复常见 JSON 问题。
- provider 配置错误可以通过 `doctor` 提前发现，而不是等到 generate/agent 流程中才失败。
- 所有修复和重试都有 artifact，可用于调试、复盘和简历 Demo 展示。

## V3.5 RAG 知识库管理台

目标：把 V3.1 的本地 NeoForge RAG 知识库从“只在 planner/eval/dashboard 背后工作”推进到“可以在 Web Demo 里直接浏览和筛选”，方便演示 LLM 规划时依赖了哪些本地规则。

完成内容：

- `web_demo.py` 新增知识库浏览 API：
  - `GET /api/knowledge?query=&category=&capability=&tag=&limit=50`
- Web Demo 页面新增：
  - `RAG Knowledge` 标签页
  - 知识库搜索输入框
  - category 筛选
  - capability 筛选
  - tag 筛选
  - 知识条目详情展示
- API 返回：
  - knowledge entry id
  - title
  - category
  - capability
  - tags
  - summary
  - content
  - source
  - query score / matched terms / snippet
- capability matrix 新增 `web_demo_knowledge_browser`。
- package metadata 更新到 `3.5.0`。

价值：

- 面试演示时可以展示“RAG 不是一个黑盒 buzzword”，而是有真实可检索、可筛选、可解释的本地知识条目。
- 用户可以看到哪些知识属于 worldgen、behavior、assets、audit、limits 等分类。
- 继续保持只读知识库管理台，不让 LLM 编辑知识库，也不让 LLM 直接生成 Java/JSON/PNG。

## V3.4 Web Demo 实时运行日志 / Build 输出展示

目标：让 Web Demo 更像真实的 Agent 控制台，而不是只在执行结束后展示一份静态结果。演示 generate / modify 时，用户可以看到后台 job 状态、运行事件和 Gradle build 输出尾部。

完成内容：

- `web_demo.py` 新增内存 job 管理：
  - `start_generate_job`
  - `start_modify_job`
  - `get_job`
- 新增 Web Demo job API：
  - `POST /api/jobs/generate`
  - `POST /api/jobs/modify`
  - `GET /api/job?id=<job_id>`
- Web 页面 generate / modify 按钮改为异步 job 模式，前端轮询 job 状态。
- 页面新增：
  - `Run Log` 标签页
  - `Build Output` 标签页
- build 输出展示会读取：
  - `.agent/logs/gradle-build.log`
  - `.agent/logs/gradle-build.stdout.log`
  - `.agent/logs/gradle-build.stderr.log`
- 原有同步 API 保留：
  - `POST /api/generate`
  - `POST /api/modify`
- capability matrix 新增 `web_demo_live_logs`。
- package metadata 更新到 `3.4.0`。

价值：

- 面试演示时可以解释“Agent 不是黑盒等结果”，而是有可观察的运行过程。
- 勾选 build 后，可以直接在浏览器里看到 Gradle 输出尾部，失败时更容易讲清楚 build / repair 链路。
- 继续保持核心边界：自然语言 / LLM -> ModSpec patch -> deterministic generator -> audit/build/repair。

## V3.3 Web Demo Workspace 管理与 Modify 交互

目标：把 V3.2 的交互式 Web Demo 从“生成一个新项目”扩展为“管理并修改已有生成项目”，形成更完整的演示闭环。

完成内容：

- `web_demo.py` 新增 workspace 管理 API：
  - `GET /api/workspaces`
  - `GET /api/workspace?name=<workspace>`
- `web_demo.py` 新增 modify API：
  - `POST /api/modify`
- Web Demo 页面新增：
  - workspace 下拉选择
  - 刷新 workspace
  - 读取当前 workspace
  - modify request 输入框
  - modify 执行按钮
  - Workspace 结果页
  - Diff / Merge 结果页
- modify 后展示：
  - `added`
  - `updated`
  - `skipped`
  - `ModSpec diff`
  - audit/build 结果
  - agent trace
- `web-demo --smoke --json` 现在会验证：
  - generate
  - workspace list
  - workspace load
  - modify
  - audit
  - diff
- capability matrix 新增 `web_demo_modify`。
- package metadata 更新到 `3.3.0`。

价值：

- 项目演示从“自然语言生成新 Mod”升级为“自然语言持续维护已有 Mod”。
- 面试时可以现场演示：先生成 ruby，再对已有 workspace 增量添加 ruby_charm，并展示 merge/diff/trace。
- 继续保持核心边界：自然语言 / LLM -> ModSpec patch -> deterministic generator -> audit/build/repair。

## V3.2 Web Demo Dashboard 交互化

目标：把 V2.5/V3.1 的 dashboard 从“静态报告页”升级成“可操作演示台”，方便实习简历、面试和现场 demo。

完成内容：

- 新增 `web_demo.py`。
- 新增 CLI 命令：
  - `web-demo`
- `web-demo` 使用 Python 标准库 HTTP server，不引入前端框架或第三方依赖。
- 页面支持输入 prompt。
- 页面支持选择 planner：
  - `rules`
  - `mock-llm`
  - `real-llm`
  - `auto-mock`
  - `auto-real`
- 后端复用 `AgentOrchestrator.run_generate`，仍然保持：
  - LLM 只输出 `ModSpec`
  - Java/JSON/PNG 由 deterministic generator 生成
  - audit/build/repair 继续兜底
- 页面展示：
  - `ModSpec`
  - generated files
  - audit result
  - build result
  - eval result
  - agent steps / decisions / prompt traces
- 新增 `web-demo --smoke --json`，用于不启动长驻服务的快速验证。
- capability matrix 新增 `interactive_web_demo`。
- package metadata 更新到 `3.2.0`。

价值：

- 面试时不再只能打开一堆 JSON 或静态 HTML，而是可以现场输入需求并展示完整 Agent 链路。
- 真实 LLM、mock LLM、rules planner 的差异可以在同一个页面里演示。
- 保持项目核心边界不变：自然语言 / LLM -> ModSpec -> deterministic generator -> audit/build/eval/repair。

本文记录项目从最早的红宝石物品 Demo，到当前 V3.1 RAG 知识库增强工作流的演进。

## V3.1 RAG 知识库增强

目标：把 V2.4 的本地 NeoForge 知识库升级成可分类、可追踪、可评估的 RAG 层，让真实 LLM / Multi-Agent 工作流更容易解释和调试。

完成内容：

- `KnowledgeEntry` 增加 capability 分类，query result 会输出 categories 和 capabilities。
- RAG query 增加自动 query expansion，会根据 prompt 中的行为、worldgen、材质、工具/护甲、方块变体、recipe/audit 等线索追加检索词。
- LLM planner artifact 增加 `used_knowledge`、`rag_categories`、`rag_capabilities`、`rag_query_expansions`。
- 生成项目时写入 `.agent/llm-used-knowledge.json`。
- `prompt-trace.json` 记录每次 planner 使用了哪些知识。
- `eval` 增加 RAG 命中率、总命中数、平均命中数、覆盖知识分类和覆盖能力指标。
- dashboard 增加 `RAG Hit Summary`，展示 RAG 命中类别和能力覆盖。
- capability matrix 新增 `rag_hit_dashboard`、`knowledge_categories`、`rag_used_knowledge`、`rag_eval_metrics`。
- package metadata 更新到 `3.1.0`。

价值：

- 面试时可以说明“LLM 不是裸跑，而是带本地 NeoForge 规则检索上下文”。
- 每次规划都能追踪检索到了哪些知识、为什么影响 planner。
- eval/dashboard 能量化 RAG 是否真的参与了规划。

## V3.0 真实 LLM / Multi-Agent 强化版

目标：把已有 `agent generate/modify` 能力升级成更适合简历展示的多角色 Agent 闭环，同时继续坚持 LLM 不直接写 Java/JSON/PNG，只输出 `ModSpec` 或 repair plan。

完成内容：

- 标准化多角色链路：`planner_agent`、`reviewer_agent`、`executor_agent`、`auditor_agent`、`repair_agent`。
- `reviewer_agent` 增加结构化 `review_checks`，记录 ModSpec schema 边界、feature presence、validator error/warning 和内容覆盖提示。
- `repair_agent` 增加 deterministic `repair_plan`，把 build/audit 失败映射成可读的下一步修复动作。
- 新增 agent trace summary artifact：`.agent/agent-trace-summary.json` 和 `.agent/agent-trace-summary.md`。
- dashboard 新增 `Multi-Agent Trace` 区块，展示每个 agent role 的输入、输出、决策理由和 prompt trace 数量。
- capability matrix 新增 `multi_agent_trace`、`multi_agent_dashboard`、`repair_plan`。
- eval 指标把 agent trace summary 纳入 artifact 完整性检查。
- package metadata 更新到 `3.0.0`。

价值：

- 面试时可以讲清楚“多 Agent 如何分工”，而不是只说调用了 LLM。
- dashboard 可以直接展示每个 agent 的输入、输出和决策理由。
- 真实 LLM 接入仍然被 ModSpec 边界约束，不破坏确定性生成和 audit/build/repair 兜底。

## V2.9 自动验收增强 / Golden Tests

目标：把现有内容生成能力沉淀成可重复执行的 golden snapshot 验收，让项目可靠性从 build/audit/eval 继续升级到“金标生成快照”。

完成内容：

- 新增 `golden_tests.py`。
- 新增 CLI 命令：
  - `golden-test`
- 默认 golden case 覆盖：
  - basic ruby item
  - ruby block
  - ruby charm behavior
  - ruby food effect
  - ruby sword ignite
  - ruby ore worldgen
  - ruby tool set
  - ruby armor set
  - ruby block variants
- Golden checks 会验证：
  - generation success
  - audit success
  - expected feature ids
  - generated file count lower bound
  - expected generated paths
  - generation-summary 是否记录关键路径
  - item/block model、recipe、worldgen、pack.mcmeta、texture manifest 等关键 JSON 字段
- `quality-gate` 默认加入 `golden_tests`，并保留 `--no-golden` 快速跳过选项。
- `quality-gate --eval-limit` 默认从 2 提升到 10，用于覆盖 V2.6 tool/armor 与 V2.8 block variants。
- `eval` 指标增加 content category coverage 汇总。
- `dashboard` 新增 Content Coverage 区块和 metrics。
- capability matrix 新增：
  - `golden_tests`
  - `golden_snapshot_checks`
  - `content_coverage_dashboard`
- package metadata 更新到 `2.9.0`。

价值：

- 让项目更像成熟 Agent 工程，而不是只堆生成能力。
- 能快速回答“当前能力到底有没有被自动验收覆盖”。
- 让 quality gate、eval 和 dashboard 形成更完整的可靠性闭环。

## V2.8 More Block Content

目标：进入“可交互但不复杂”的方块扩展，让普通 block 可以声明常见建筑/红石方块变体，同时继续强化 deterministic generator。

完成内容：

- `BlockSpec` 新增 `block_kind` 与 `base_block`。
- 支持的 `block_kind`：
  - `cube`
  - `stairs`
  - `slab`
  - `wall`
  - `button`
  - `pressure_plate`
  - `fence`
  - `fence_gate`
  - `door`
  - `trapdoor`
- rules planner 支持：
  - `红宝石方块变体`
  - `红宝石建筑方块套装`
  - `ruby block variants`
  - `ruby building block set`
  - 单独的 `红宝石楼梯 / ruby stairs`、`红宝石门 / ruby door` 等表达。
- 生成器会为方块变体确定性生成：
  - vanilla block subclass Java 注册
  - blockstate JSON
  - block model JSON
  - item model JSON
  - loot table
  - shaped/shapeless recipe
  - language key
  - 16x16 PNG texture
- `door` 使用 `DoubleHighBlockItem`，避免门被当成普通 `BlockItem`。
- schema、validator、LLM planner、MockLLMClient、auditor、capability matrix、RAG knowledge 和 eval coverage 均已更新。
- `generate --build --audit "Create a ruby mod with ruby block variants."` 已验证通过。
- package metadata 更新到 `2.8.0`。

价值：

- 让方块内容从“只有 cube”扩展到更接近真实建筑玩法的常见方块链。
- 这类能力主要靠 JSON、注册、模型、loot 和 recipe，风险低但展示效果明显。
- 后续可以继续升级到自定义方块行为、方块实体或更复杂建筑/装饰系统。

## V2.7 Equipment Sets And Recipes

目标：把 V2.6 的工具/护甲单件生成补成更完整的装备链，让一句话就能生成可合成、可审计、可构建的红宝石工具套装和护甲套装。

完成内容：

- rules planner 支持：
  - `红宝石工具套装`
  - `一套红宝石工具`
  - `ruby tool set`
  - `ruby tools`
  - `红宝石护甲套装`
  - `一套红宝石护甲`
  - `ruby armor set`
  - `ruby armor`
- 红宝石工具套装会生成：
  - `ruby`
  - `ruby_sword`
  - `ruby_pickaxe`
  - `ruby_axe`
  - `ruby_shovel`
  - `ruby_hoe`
- 红宝石护甲套装会生成：
  - `ruby`
  - `ruby_helmet`
  - `ruby_chestplate`
  - `ruby_leggings`
  - `ruby_boots`
- 自动生成每件装备对应的 shaped crafting recipe：
  - 工具/剑使用 `ruby_mod:ruby` + `minecraft:stick`
  - 护甲使用 `ruby_mod:ruby`
- `tool_material` 和 `armor_material` 支持 `ruby`。
- Java generator 将 `ruby` 材料映射到安全的 vanilla `IRON` 基线，保持 build 稳定。
- schema、validator、LLM planner、MockLLMClient、capability matrix 和测试覆盖同步更新。
- audit 继续覆盖装备模型、贴图、语言 key、注册代码和 recipe 引用。
- package metadata 更新到 `2.7.0`。

价值：

- V2.6 的工具/护甲不再只是“能注册”，而是形成完整可玩的装备链。
- 仍然保持核心边界：自然语言或 LLM 只产出 ModSpec，Java/JSON/PNG 仍由确定性 generator 生成。
- 为后续真正自定义材料属性、套装效果和更复杂配方系统打基础。

## V2.6 More Mod Content Types

目标：在不引入复杂 GUI、BlockEntity 或实体系统的前提下，扩展更常见、可演示的 Mod 内容类型。

完成内容：

- 新增 `tool` ModSpec 类型。
- 支持工具类型：
  - `pickaxe`
  - `axe`
  - `shovel`
  - `hoe`
- 新增 `armor` ModSpec 类型。
- 支持护甲类型：
  - `helmet`
  - `chestplate`
  - `leggings`
  - `boots`
- 扩展 schema、validator、rules planner、LLM planner、MockLLMClient、modify merge、Java generator、asset generator、auditor、capability matrix 和 eval coverage。
- 工具生成使用确定性 Java 注册：
  - `properties.pickaxe(...)`
  - `properties.axe(...)`
  - `properties.shovel(...)`
  - `properties.hoe(...)`
- 护甲生成使用确定性 Java 注册：
  - `properties.humanoidArmor(..., ArmorType.HELMET)`
  - `ArmorType.CHESTPLATE`
  - `ArmorType.LEGGINGS`
  - `ArmorType.BOOTS`
- 程序化材质支持工具和护甲图标。
- audit 检查工具/护甲模型、贴图、语言 key、Java 注册、工具方法和护甲 `ArmorType`。
- package metadata 更新到 `2.6.0`。

价值：

- 内容生成能力从基础物品/方块/矿石/食物/剑扩展到更完整的装备层。
- 保持核心边界：自然语言或 LLM 只产出 ModSpec，Java/JSON/PNG 仍由确定性 generator 生成。
- 为后续 V2.7+ 做更复杂装备套装、材料系统、配方自动生成和实战演示打基础。

## V2.5 Web Demo Dashboard

目标：把现有 CLI / agent / eval / RAG / capability 报告汇总成一个可直接打开的本地 Web 展示页，方便简历项目和面试演示。

完成内容：

- 新增 `dashboard.py`。
- 新增 CLI 命令：
  - `dashboard`
- 默认输出：
  - `workspace/dashboard-runs/<run-id>/index.html`
  - `workspace/dashboard-runs/<run-id>/.agent/dashboard-data.json`
  - `workspace/dashboard-runs/<run-id>/.agent/dashboard-report.md`
- Dashboard 默认汇总：
  - capability matrix
  - V2.4 RAG knowledge query
  - showcase 多 Agent 演示
  - eval smoke 摘要
  - 原始 artifact 链接
- 新增 `--no-showcase`，可快速生成 capabilities + RAG 页面。
- capability matrix 增加：
  - `web_dashboard`
- package metadata 更新到 `2.5.0`。

价值：

- 让项目从“能跑的 CLI 工具”更像“能展示的 Agent 产品”。
- 面试时可以直接打开 HTML 讲完整链路。
- 继续保持离线、无前端依赖、无服务启动的轻量形态。

## V2.4 NeoForge Knowledge Base / RAG

目标：为 LLM planner 增加一个本地、可审计、确定性的 NeoForge 知识检索层，让模型在生成 ModSpec 前能看到项目内已验证的约束和路径规则。

完成内容：

- 新增 `knowledge_base.py`。
- 新增 CLI 命令：
  - `knowledge query <query>`
- 内置 NeoForge 知识条目覆盖：
  - ModSpec 边界
  - NeoForge deferred register
  - assets / models / textures 路径
  - 程序化材质
  - texture audit
  - right click item behavior
  - food effects
  - sword ignite
  - recipes / loot tables / tags
  - overworld ore worldgen
  - pack.mcmeta
  - unsupported boundaries
- `knowledge query` 写出：
  - `workspace/knowledge-runs/<run-id>/.agent/rag-query.json`
  - `workspace/knowledge-runs/<run-id>/.agent/rag-query.md`
- `plan_with_llm` 和 `plan_modification_with_llm` 自动检索 RAG context，并注入 system prompt。
- LLM planner artifacts 写出：
  - `.agent/rag-context.json`
  - `.agent/rag-context.md`
- Agent prompt trace 增加：
  - `rag_query`
  - `rag_hits`
- capability matrix 增加：
  - `knowledge_query`
  - `rag_planner_context`
- package metadata 更新到 `2.4.0`。

价值：

- LLM 不再只依赖一个静态大 prompt，而是获得与请求相关的本地知识片段。
- RAG 检索结果可复现、可审计，适合简历和面试讲解。
- 继续保持核心边界：RAG 只辅助生成 ModSpec，不允许 LLM 直接生成 Java/JSON/PNG。

## V2.3 Programmatic Texture Generation

目标：把生成材质纳入正式、可审计、可修复的确定性生成链路，减少游戏内黑紫缺失材质。

完成内容：

- 为 `item`、`food`、`sword`、`block`、`ore` 生成确定性的 `16x16 RGBA PNG` 材质。
- 行为物品会根据行为类型选择不同模板：
  - `right_click_heal` 使用 `heal_badge`
  - `right_click_effect` 使用 `effect_crystal`
- 普通 item 使用 `gem` 模板。
- food 使用 `apple` 模板。
- sword 使用 `sword` 模板。
- block 使用 `solid_block` 模板。
- ore 使用 `ore_block` 模板。
- 新增 `.agent/texture-manifest.json`，记录每个生成材质的 feature 类型、id、路径、模板、尺寸和颜色格式。
- `generation-summary.json` 会记录 `.agent/texture-manifest.json` 和生成的 PNG 文件。
- `audit` 新增材质检查：
  - manifest 是否存在
  - manifest JSON 是否可解析
  - manifest 中的 texture 文件是否存在
  - feature 对应的 PNG 是否存在
  - PNG 是否为 `16x16 RGBA`
- `repair-loop` 可以恢复缺失的受控材质文件。
- `capabilities` 增加：
  - `procedural_textures`
  - `texture_audit`

价值：

- 程序化材质不是最终美术，但能让生成项目更适合打开游戏演示。
- 黑紫块问题从“人工进游戏才发现”前移到 `audit` 阶段。
- 后续接入 LLM / 多 Agent 材质创作时，可以把 `.agent/texture-manifest.json` 作为稳定接口。

## V2.3 Eval Compare

目标：让 V2.2 的 benchmark 指标可以做两次运行之间的回归对比。

完成内容：

- 新增 `eval_compare.py`。
- 新增 CLI 命令：
  - `eval-compare <baseline> <candidate>`
- baseline 和 candidate 支持：
  - eval report JSON 路径
  - eval run 目录
  - eval run 名称
- 对比并监控这些 rate 指标：
  - `success_rate`
  - `expected_feature_match_rate`
  - `expected_category_match_rate`
  - `planning_success_rate`
  - `audit_success_rate`
  - `build_success_rate`
  - `agent_artifacts_complete_rate`
  - `prompt_trace_present_rate`
  - `repeat_modify_success_rate`
- 对比每个 eval case 是否从 pass 退步为 fail。
- 生成对比报告：
  - `workspace/eval-comparisons/<run-id>/.agent/eval-compare-report.json`
  - `workspace/eval-comparisons/<run-id>/.agent/eval-compare-report.md`
- `capabilities` 增加 `eval_compare` 能力。
- package metadata 更新到 `2.3.0`。

价值：

- V2.2 解决“单次评测有没有覆盖足够信息”，V2.3 解决“这次升级有没有比上次退步”。
- 适合后续作为 release 前的 benchmark regression gate。
- 对简历叙事更完整：项目不仅有 Agent、eval 和 quality gate，还有跨版本评测对比能力。

## V2.2 Eval Coverage Metrics

目标：把已有 benchmark 从“运行 prompt 并统计成功率”升级为更细的能力覆盖评测。

完成内容：

- 扩展 `EvalCase`，新增 `expected_categories` 和 `repeat_request`。
- 扩展 `EvalCaseResult`，记录期望能力分类命中 / 缺失、agent trace artifact 是否存在、repeat modify 幂等性结果。
- eval 现在会检查 `.agent/agent-run.json`、`.agent/agent-run.md`、`.agent/agent-decisions.md`、`.agent/prompt-trace.json` 是否真实生成。
- 新增聚合指标：`expected_category_match_rate`、`category_expectation_success_rate`、`agent_artifacts_complete_rate`、`repeat_modify_success_rate`。
- 默认 eval case 覆盖 basic ruby、right-click heal、right-click effect、food effect、sword ignite、ore worldgen、modify add behavior、modify add worldgen。
- `MockLLMClient` 支持 modify 场景下的 ruby charm behavior patch。
- `capabilities` 增加 `eval_coverage_metrics` 能力。
- package metadata 更新到 `2.2.0`。

价值：

- 评测报告不只说明“是否成功”，还能说明“覆盖了哪些能力”。
- 对简历和面试更友好：可以展示 feature expectation、capability coverage、agent trace、modify idempotency 四类工程指标。
- 后续更换 planner、LLM provider 或 generator 时，可以用同一套 benchmark 做稳定对比。

## V0.1 Ruby Item Demo

Goal: prove that the project can generate a minimal NeoForge mod workspace with one custom item.

Completed:

- Generated a basic ruby item.
- Established the first NeoForge workspace generation path.
- Verified the copied template can be adapted into a custom mod project.

Value:

- Confirmed the feasibility of deterministic mod project generation.
- Created the first working baseline for later content generation.

## V0.2 Basic Content Generation

Goal: expand from a single demo item into structured content generation.

Completed:

- Introduced `ModSpec` as the structured source of truth.
- Added rule-based planning from natural language into `ModSpec`.
- Added deterministic generation for basic assets and project metadata.
- Started separating planner, model, generator, and validator responsibilities.

Value:

- Moved the system from a demo script toward an extensible generator architecture.
- Established the core principle: natural language becomes `ModSpec`, not arbitrary generated code.

## V0.3 Playable In-Game Base Content

Goal: make generated content usable inside Minecraft, not only present on disk.

Completed:

- Generated playable `item`, `block`, `ore`, `food`, and `sword` content.
- Generated item/block models, blockstates, language files, tags, recipes, and loot tables.
- Added placeholder textures for generated content.
- Verified generated content through build and manual in-game checks.

Value:

- Turned the project into a usable mod content generator.
- Established the first meaningful gameplay smoke tests.

## V0.4 Build Repair Loop

Goal: make failures diagnosable and repairable instead of opaque.

Completed:

- Added Gradle build execution through the CLI.
- Captured build logs under `.agent/logs`.
- Classified common build errors such as missing symbols, bad imports, constructor mismatches, resource JSON errors, and dependency issues.
- Generated repair artifacts:
  - `.agent/debug-context.md`
  - `.agent/fix-request.md`
  - `.agent/suspected-errors.json`
- Added `repair` command and build repair integration.

Value:

- Built the first reliability loop around generation.
- Made build failures easier to hand to a human or future repair agent.

## V0.5 LLM Planner

Goal: add LLM support without allowing the LLM to directly write project files.

Completed:

- Added optional `llm` planner mode while keeping `rules` as the default.
- Added `auto` planner mode.
- Added `MockLLMClient` for offline deterministic tests.
- Added OpenAI-compatible client support through environment variables.
- Added LLM planner artifacts:
  - planner input
  - raw LLM JSON
  - normalized LLM JSON
  - planner warnings
- Normalized and validated LLM output into `ModSpec`.

Value:

- Introduced LLM capability while preserving deterministic generation.
- Avoided the common failure mode of letting the model directly emit Java or Gradle code.

## V0.6 Modify Existing Workspace

Goal: support incremental changes to already generated projects.

Completed:

- Added `modify` command.
- Used `.agent/modspec.json` as the existing project source of truth.
- Planned change requests as patches instead of re-generating from scratch.
- Added merge behavior with `added`, `updated`, and `skipped` outcomes.
- Preserved user files by only cleaning files recorded in `generation-summary.json`.
- Added modify artifacts:
  - `.agent/modspec.before.json`
  - `.agent/modspec.after.json`
  - `.agent/last-modify-request.txt`
  - `.agent/modify-summary.json`
  - `.agent/modify-history.jsonl`

Value:

- Added the second core workflow: `modify`.
- Made repeated modify requests idempotent for already existing features.
- Established the generated workspace as a persistent project, not a one-shot output folder.

## V0.7 Simple Behavior Items

Goal: support controlled gameplay behavior without allowing arbitrary Java generation.

Completed:

- Added behavior declarations to `ModSpec`.
- Supported item behavior:
  - `right_click_heal`
  - `right_click_effect`
- Supported food effects through `food.effects`.
- Supported sword hit behavior through `sword.on_hit.ignite`.
- Generated custom Java item classes when behavior requires code.
- Generated custom sword item classes for on-hit ignite behavior.
- Extended rules planner and mock LLM behavior prompts.
- Extended validator to check behavior types, ranges, effect ids, cooldowns, probabilities, and allowed feature attachment.
- Verified behavior content through build and manual in-game tests.

Value:

- Moved from static content generation into behavior-driven generation.
- Preserved the project architecture: behavior is declared in `ModSpec`, Java is still generated deterministically.

## V0.7.1 Placeholder Texture Follow-Up

Goal: investigate placeholder texture rendering issues.

Completed:

- Investigated item placeholder texture generation.
- Confirmed gameplay behavior worked even when some generated textures still appeared as missing black/purple placeholders in-game.
- Decided not to block the Agent roadmap on final art generation.

Value:

- Clarified that asset artistry is separate from the core Agent pipeline.
- Kept the roadmap focused on generation reliability and agent workflow.

## V0.8 Ore Worldgen

Goal: make ore features naturally generate in the world.

Completed:

- Added `ore.worldgen` to `ModSpec`.
- Supported overworld underground ore generation.
- Added `worldgen_generator.py`.
- Generated worldgen files:
  - `data/<modid>/worldgen/configured_feature/<ore_id>.json`
  - `data/<modid>/worldgen/placed_feature/<ore_id>.json`
  - `data/<modid>/neoforge/biome_modifier/add_<ore_id>.json`
- Extended validator for worldgen constraints:
  - worldgen only on ore
  - only `minecraft:overworld`
  - valid Y range
  - positive vein size
  - positive veins per chunk
- Extended rules planner and mock LLM for worldgen prompts.
- Supported modify updates for existing ore worldgen.

Value:

- Completed the basic content loop for ores: item, block, drop, tags, loot, and natural generation.
- Added a realistic datapack-generation capability while keeping JSON deterministic.

## V0.9 Project Audit

Goal: verify generated workspace structure beyond what Gradle build can catch.

Completed:

- Added `auditor.py`.
- Added `audit` CLI command.
- Read `.agent/modspec.json` and `.agent/generation-summary.json`.
- Checked base project files.
- Checked generated files listed in `generation-summary.json`.
- Checked item, block, ore, food, sword, recipe, behavior, and worldgen outputs.
- Wrote audit artifacts:
  - `.agent/audit-report.json`
  - `.agent/audit-report.md`
- Added negative audit testing by deleting a generated model file.

Value:

- Added deterministic structural validation of generated projects.
- Covered gaps that Gradle build alone cannot detect, such as missing models, missing lang keys, missing worldgen files, and stale generated-file records.

## V0.9.1 Pack Metadata

Goal: include `pack.mcmeta` as a first-class generated artifact.

Completed:

- Generated `src/main/resources/pack.mcmeta`.
- Added `pack.mcmeta` to `generation-summary.json`.
- Extended audit to check:
  - file existence
  - valid JSON
  - `pack` object
  - `pack.description`
  - integer `pack.pack_format`
- Preserved compatibility with older workspaces.

Value:

- Completed a small but important resource-pack/data-pack metadata requirement.
- Made audit cleaner and more complete before V1.0.

## V1.0 MVP Documentation And Workflow Polish

Goal: turn the working generator into a presentable MVP.

Completed:

- Added a full README.
- Added Chinese README section.
- Added `docs/modspec.md`.
- Added `docs/test-matrix.md`.
- Documented commands for:
  - generate
  - modify
  - audit
  - build
  - repair
  - print-schema
  - test-examples
  - LLM mock
  - OpenAI-compatible LLM
- Added `generate --audit`, `modify --audit`, and `generate-from-spec --audit`.
- Improved CLI help text.

Value:

- Made the project easier to run, explain, and evaluate.
- Created documentation suitable for GitHub, interviews, and project demos.

## V1.1 Lightweight Agent Orchestration

Goal: add a portfolio-friendly multi-agent workflow while preserving deterministic generation.

Completed:

- Added `agent_models.py`.
- Added `agent_orchestrator.py`.
- Added CLI command group:
  - `agent generate`
  - `agent modify`
- Added explicit role trace:
  - `planner_agent`
  - `reviewer_agent`
  - `executor`
  - `auditor_agent`
  - `repair_agent`
- Default agent planner uses `llm` + `mock` for offline demonstration.
- Supported OpenAI-compatible provider through the existing LLM client.
- Wrote agent artifacts:
  - `.agent/agent-run.json`
  - `.agent/agent-run.md`
  - `.agent/agent-repair-plan.json` when repair analysis is needed
  - `.agent/agent-repair-plan.md` when repair analysis is needed
- Added `docs/agent-workflow.md`.
- Updated README and test matrix with V1.1 commands.
- Verified agent generate and agent modify with build and audit.

Value:

- Turned the project into a clearer LLM-assisted Agent system.
- Demonstrated multi-role orchestration without sacrificing reliability.
- Created strong portfolio talking points:
  - structured intermediate representation
  - constrained LLM planning
  - deterministic execution
  - project audit
  - build verification
  - repair-oriented failure analysis

## V1.2 Evaluation And Benchmark

Goal: add a measurable benchmark layer for the Agent workflow.

Completed:

- Added `evaluator.py`.
- Added CLI command:
  - `eval`
- Added default offline benchmark cases for:
  - basic ruby generation
  - behavior item generation
  - right-click effect item generation
  - food effect generation
  - ore worldgen generation
  - modify existing ore to add worldgen
- Reused V1.1 `AgentOrchestrator` instead of creating a separate generation path.
- Added expected feature checks against final `.agent/modspec.json`.
- Added aggregate metrics:
  - success rate
  - feature expectation match rate
  - planning success rate
  - audit success rate
  - optional build success rate
  - generated file counts
  - modify added / updated / skipped totals
- Wrote eval artifacts:
  - `workspace/eval-runs/<run-id>/.agent/eval-cases.json`
  - `workspace/eval-runs/<run-id>/.agent/eval-report.json`
  - `workspace/eval-runs/<run-id>/.agent/eval-report.md`
- Added `docs/eval.md`.
- Updated README and test matrix with V1.2 eval commands.

Value:

- Moved the project from one-off smoke tests toward repeatable benchmark evaluation.
- Made the Agent system easier to compare across future planner, LLM, and generator changes.
- Added a stronger portfolio story: the project has not only LLM planning and multi-agent orchestration, but also deterministic evaluation metrics.

## V1.3 Automated Regression Tests

Goal: turn core smoke coverage into a fast, repeatable test suite.

Completed:

- Added `tests/`.
- Added standard-library `unittest` coverage with no third-party test dependency.
- Added generation and audit tests:
  - basic ruby generation succeeds
  - generated project passes audit
  - `pack.mcmeta` is generated and recorded
- Added negative audit test:
  - deleting a generated item model makes audit fail
- Added Agent workflow test:
  - mock LLM `agent generate` succeeds and writes `agent-run.json`
- Added Eval workflow tests:
  - default eval subset reports feature metrics
  - missing expected feature makes eval fail
- Added CLI parser tests:
  - top-level help includes `eval` and `agent`
  - `eval` options parse correctly
  - `generate --audit` parses correctly
- Exported `ModProjectPlanner` from package top-level API.
- Added `docs/testing.md`.
- Updated README and test matrix with V1.3 test commands.

Value:

- Made the project easier to regression-test before future feature work.
- Kept the default test suite fast by skipping Gradle builds.
- Added a stronger engineering reliability story for resumes and interviews.

## V1.4 Quality Gate

Goal: provide a one-command reliability gate for demos, commits, and future feature work.

Completed:

- Added `quality_gate.py`.
- Added CLI command:
  - `quality-gate`
- The default quality gate runs:
  - Python `compileall`
  - `unittest discover`
  - `print-schema --json`
  - `test-examples --no-build --json`
  - `eval --planner llm --llm-provider mock --no-build --limit 2 --json`
- Added optional `--build-smoke` for slower Gradle compile verification.
- Added per-check stdout/stderr logs under:
  - `workspace/quality-gate-runs/<run-id>/.agent/logs/`
- Wrote quality gate artifacts:
  - `workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.json`
  - `workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.md`
- Added skip flags for development:
  - `--no-compile`
  - `--no-unittest`
  - `--no-schema`
  - `--no-examples`
  - `--no-eval`
- Added `docs/quality-gate.md`.
- Updated README and test matrix with V1.4 commands.
- Added tests for quality gate parser and schema-only runner behavior.

Value:

- Turned separate reliability commands into a single reproducible gate.
- Made the project easier to validate before demos or future feature work.
- Added a clean CI-style story without introducing external dependencies.

## V1.5 CI Quality Gate

Goal: make the project GitHub-ready by connecting the local quality gate to CI.

Completed:

- Added GitHub Actions workflow:
  - `.github/workflows/quality-gate.yml`
- Configured CI to run on:
  - push to `main`
  - pull request
  - manual `workflow_dispatch`
- Configured CI with Python `3.11` and `PYTHONPATH=src`.
- Reused the existing V1.4 command:
  - `python -m agent.cli quality-gate --run-name ci-quality-gate --json`
- Uploaded quality gate artifacts from:
  - `workspace/quality-gate-runs/ci-quality-gate/.agent/**`
- Kept Gradle build smoke out of the default CI path so hosted runs remain fast and stable.
- Added `docs/ci.md`.
- Added workflow static tests under `tests/test_ci_workflow.py`.
- Updated README and test matrix with V1.5 CI instructions.
- Updated package metadata to version `1.5.0`.

Value:

- Turned the local reliability gate into an automated GitHub workflow.
- Made the project easier to present as a real engineering project, not just a local demo.
- Preserved the fast default CI path while keeping stronger local validation available through `quality-gate --build-smoke`.

## V1.6 Environment Doctor

Goal: add a local preflight diagnostic command so new checkouts are easier to debug.

Completed:

- Added `doctor.py`.
- Added CLI command:
  - `doctor`
- Doctor checks:
  - Python version
  - project layout
  - compatibility CLI entrypoint
  - NeoForge template directory
  - template Gradle wrapper files
  - template Java toolchain version
  - workspace root and parent writability
  - `PYTHONPATH`
  - important docs
  - GitHub Actions workflow
  - `java -version`
- Added `--no-java` to skip Java diagnostics.
- Added `--strict` to treat warnings as failures.
- Wrote doctor artifacts:
  - `workspace/doctor-runs/<run-id>/.agent/doctor-report.json`
  - `workspace/doctor-runs/<run-id>/.agent/doctor-report.md`
- Added `docs/doctor.md`.
- Added doctor tests and CLI parser coverage.
- Updated README and test matrix with V1.6 commands.
- Updated package metadata to version `1.6.0`.

Value:

- Helps users quickly understand why local setup may not run.
- Adds another portfolio-friendly reliability layer alongside audit, eval, tests, quality gate, and CI.
- Keeps diagnostics deterministic and read-only, so it is safe to run before generation.

## V1.7 Integrated Doctor Quality Gate

Goal: make environment diagnostics part of the normal reliability path instead of a standalone-only command.

Completed:

- Integrated doctor into `quality-gate` as the first default check:
  - `doctor_environment`
- Default quality gate now runs:
  - `doctor --no-java --json`
  - Python `compileall`
  - `unittest discover`
  - `print-schema --json`
  - `test-examples --no-build --json`
  - mock LLM eval smoke
  - optional build smoke
- Added quality gate flags:
  - `--no-doctor`
  - `--doctor-java`
  - `--doctor-strict`
- Updated GitHub Actions artifact upload to include:
  - `workspace/quality-gate-runs/ci-quality-gate/.agent/**`
  - `workspace/doctor-runs/ci-quality-gate-doctor/.agent/**`
- Updated CI workflow tests to ensure doctor is not disabled.
- Updated quality gate tests for doctor pass/skip behavior.
- Updated README, CI docs, doctor docs, quality gate docs, and test matrix.
- Updated package metadata to version `1.7.0`.

Value:

- Makes local and CI reliability checks more self-explanatory: failures can now show environment problems before deeper generator checks.
- Keeps CI fast by skipping Java diagnostics in the default gate.
- Preserves stronger local validation through `quality-gate --doctor-java --build-smoke`.

## V1.8 Showcase Reports

Goal: provide a one-command, portfolio-friendly demo flow that summarizes the current Agent system.

Completed:

- Added `showcase.py`.
- Added CLI command:
  - `showcase`
- The default showcase flow runs:
  - environment doctor preflight without Java diagnostics
  - mock LLM multi-role `agent generate`
  - mock LLM multi-role `agent modify`
  - offline eval smoke benchmark
  - optional quality gate when `--quality-gate` is passed
- Showcase workspaces are isolated under:
  - `workspace/showcase-runs/<run-id>/workspaces/`
- Showcase artifacts are written to:
  - `workspace/showcase-runs/<run-id>/.agent/showcase-report.json`
  - `workspace/showcase-runs/<run-id>/.agent/showcase-report.md`
- Added flags:
  - `--run-name`
  - `--planner`
  - `--llm-provider`
  - `--eval-limit`
  - `--build`
  - `--quality-gate`
- Added `docs/showcase.md`.
- Added showcase runner tests and CLI parser coverage.
- Updated README and test matrix.
- Updated package metadata to version `1.8.0`.

Value:

- Creates a concise report suitable for GitHub, resumes, and interview walkthroughs.
- Demonstrates the project as a complete Agent system: doctor, LLM planner, multi-agent orchestration, modify, audit, eval, and optional quality gate.
- Keeps the default showcase fast by avoiding Gradle builds unless explicitly requested.

## V1.9 Capability Matrix

Goal: export a structured source of truth for the current project capabilities.

Completed:

- Added `capabilities.py`.
- Added CLI command:
  - `capabilities`
- Capability matrix includes:
  - project metadata
  - core workflows
  - generated content types
  - behavior templates
  - worldgen support
  - planner and LLM boundaries
  - reliability and verification layers
  - current limitations
- Capability artifacts are written to:
  - `workspace/capability-runs/<run-id>/.agent/capabilities.json`
  - `workspace/capability-runs/<run-id>/.agent/capabilities.md`
- Added `docs/capabilities.md`.
- Added capability catalog tests and CLI parser coverage.
- Updated README and test matrix.
- Updated package metadata to version `1.9.0`.

Value:

- Gives README, showcase, resumes, and interview walkthroughs a single structured capability source.
- Makes it easier to explain the project as a complete system rather than a list of scattered commands.
- Keeps capability documentation machine-readable for future automation.

## Current Architecture Summary

The project now supports:

- `generate`: natural language or spec to new workspace
- `modify`: natural language patch to existing workspace
- `audit`: deterministic workspace consistency check
- `build`: Gradle verification
- `repair`: build failure artifact generation
- `agent generate`: multi-role orchestration for new workspace generation
- `agent modify`: multi-role orchestration for existing workspace modification
- `eval`: benchmark evaluation for agent workflows
- `unittest`: fast automated regression checks
- `quality-gate`: one-command reliability gate
- GitHub Actions CI: automated quality gate for pushes and pull requests
- `doctor`: local environment diagnostics
- integrated doctor preflight inside `quality-gate`
- `showcase`: one-command portfolio demo report
- `capabilities`: structured capability matrix export

The main design principle is:

```text
LLM / natural language -> ModSpec -> deterministic Java/JSON generation -> audit/build/repair
```

This keeps LLM output constrained and makes generated projects easier to test, reproduce, and debug.

---

# 版本说明

本文档记录项目从最早的红宝石物品 Demo 到当前 V1.9 能力矩阵工作流的演进过程。

## V0.1 红宝石物品 Demo

目标：证明项目可以生成一个最小可用的 NeoForge Mod 工作区，并包含一个自定义物品。

完成内容：

- 生成基础红宝石物品。
- 建立第一条 NeoForge 工作区生成路径。
- 验证模板项目可以被改造成自定义 Mod 项目。

价值：

- 验证了确定性 Mod 项目生成的可行性。
- 为后续内容生成建立了第一个可运行基线。

## V0.2 基础内容生成

目标：从单个 Demo 物品扩展到结构化内容生成。

完成内容：

- 引入 `ModSpec` 作为结构化真相源。
- 增加从自然语言到 `ModSpec` 的 rules planner。
- 增加基础资源和项目元信息的确定性生成。
- 初步拆分 planner、model、generator、validator 职责。

价值：

- 让系统从 Demo 脚本走向可扩展生成器架构。
- 建立核心原则：自然语言先转成 `ModSpec`，而不是直接生成任意代码。

## V0.3 游戏内可玩基础内容

目标：让生成内容真正能在 Minecraft 游戏内使用，而不只是存在于磁盘文件中。

完成内容：

- 支持生成可玩的 `item`、`block`、`ore`、`food`、`sword`。
- 生成 item/block model、blockstate、语言文件、tag、recipe 和 loot table。
- 为生成内容添加占位贴图。
- 通过 build 和人工游戏内测试验证基础内容。

价值：

- 将项目推进为可用的 Mod 内容生成器。
- 建立第一批有意义的游戏内 smoke test。

## V0.4 Build Repair Loop

目标：让构建失败变得可诊断、可修复，而不是只看到一段 Gradle 报错。

完成内容：

- 增加 CLI 里的 Gradle build 执行能力。
- 将 build 日志记录到 `.agent/logs`。
- 分类常见构建错误，例如 missing symbol、bad import、constructor mismatch、resource JSON error 和 dependency issue。
- 生成 repair artifacts：
  - `.agent/debug-context.md`
  - `.agent/fix-request.md`
  - `.agent/suspected-errors.json`
- 增加 `repair` 命令和 build repair 集成。

价值：

- 为生成链路建立第一层可靠性闭环。
- 让失败信息可以交给人类开发者或后续 repair agent 使用。

## V0.5 LLM Planner

目标：加入 LLM 能力，但不允许 LLM 直接写项目文件。

完成内容：

- 增加可选 `llm` planner，同时保持 `rules` 为默认模式。
- 增加 `auto` planner。
- 增加 `MockLLMClient`，用于离线确定性测试。
- 增加 OpenAI-compatible client，支持通过环境变量接入真实模型服务。
- 增加 LLM planner artifacts：
  - planner input
  - raw LLM JSON
  - normalized LLM JSON
  - planner warnings
- 将 LLM 输出 normalize 并 validate 成 `ModSpec`。

价值：

- 在保持确定性生成的前提下引入 LLM。
- 避免“让模型直接吐 Java/Gradle 文件”带来的不可控风险。

## V0.6 Modify 已有项目

目标：支持对已经生成的项目做增量修改。

完成内容：

- 增加 `modify` 命令。
- 使用 `.agent/modspec.json` 作为已有项目的真相源。
- 将修改请求规划成 patch，而不是重新生成整个项目。
- 增加 merge 行为，输出 `added`、`updated`、`skipped`。
- 只清理 `generation-summary.json` 中记录的受控生成文件，保留用户自定义文件。
- 增加 modify artifacts：
  - `.agent/modspec.before.json`
  - `.agent/modspec.after.json`
  - `.agent/last-modify-request.txt`
  - `.agent/modify-summary.json`
  - `.agent/modify-history.jsonl`

价值：

- 增加第二条核心工作流：`modify`。
- 让重复 modify 请求对已有 feature 具备幂等基础。
- 让生成工作区从一次性输出目录变成可持续修改的项目。

## V0.7 简单行为型物品

目标：支持受控的游戏行为生成，但仍然不开放任意 Java 代码生成。

完成内容：

- 在 `ModSpec` 中加入行为声明。
- 支持 item behavior：
  - `right_click_heal`
  - `right_click_effect`
- 支持 food effects：`food.effects`。
- 支持 sword hit behavior：`sword.on_hit.ignite`。
- 当行为需要 Java 代码时，生成自定义 item class。
- 为 sword on-hit ignite 生成自定义 sword item class。
- 扩展 rules planner 和 mock LLM 行为 prompt。
- 扩展 validator，校验行为类型、数值范围、effect id、cooldown、probability 和行为允许挂载的位置。
- 通过 build 和人工游戏内测试验证行为内容。

价值：

- 将项目从静态内容生成推进到行为驱动生成。
- 保持架构原则：行为在 `ModSpec` 中声明，Java 仍由确定性生成器生成。

## V0.7.1 占位贴图跟进

目标：调查占位贴图在游戏内显示异常的问题。

完成内容：

- 调查 item placeholder texture 生成。
- 确认即使部分物品在游戏内仍显示为黑紫缺失贴图，核心 gameplay behavior 仍然正常。
- 决定不让最终美术资源阻塞 Agent 主线能力建设。

价值：

- 明确资源美术质量和 Agent 生成管线是两个问题。
- 让路线继续聚焦在生成可靠性和 Agent 工作流上。

## V0.8 矿石自然生成 / Worldgen

目标：让 ore feature 能自然生成在世界里。

完成内容：

- 在 `ModSpec` 中加入 `ore.worldgen`。
- 支持主世界地下矿石生成。
- 新增 `worldgen_generator.py`。
- 生成 worldgen 文件：
  - `data/<modid>/worldgen/configured_feature/<ore_id>.json`
  - `data/<modid>/worldgen/placed_feature/<ore_id>.json`
  - `data/<modid>/neoforge/biome_modifier/add_<ore_id>.json`
- 扩展 validator 校验 worldgen 约束：
  - worldgen 只能挂在 ore 上
  - 只支持 `minecraft:overworld`
  - Y 范围合法
  - vein size 必须为正
  - veins per chunk 必须为正
- 扩展 rules planner 和 mock LLM 的 worldgen prompt。
- 支持 modify 给已有 ore 新增或更新 worldgen。

价值：

- 补齐 ore 的基本闭环：item、block、drop、tag、loot、自然生成。
- 加入真实 datapack JSON 生成能力，同时仍保持确定性。

## V0.9 结构化验收 / Project Audit

目标：检查 Gradle build 无法覆盖的生成结构一致性问题。

完成内容：

- 新增 `auditor.py`。
- 新增 `audit` CLI 命令。
- 读取 `.agent/modspec.json` 和 `.agent/generation-summary.json`。
- 检查基础项目文件。
- 检查 `generation-summary.json` 中记录的生成文件是否真实存在。
- 检查 item、block、ore、food、sword、recipe、behavior 和 worldgen 输出。
- 写入 audit artifacts：
  - `.agent/audit-report.json`
  - `.agent/audit-report.md`
- 增加负向测试：删除生成的 model 文件后 audit 能失败并报告错误。

价值：

- 增加确定性的项目结构审计能力。
- 覆盖 Gradle build 不一定能发现的问题，例如缺 model、缺 lang key、缺 worldgen 文件、generated file 记录过期等。

## V0.9.1 Pack Metadata

目标：将 `pack.mcmeta` 纳入正式生成产物。

完成内容：

- 生成 `src/main/resources/pack.mcmeta`。
- 将 `pack.mcmeta` 记录到 `generation-summary.json`。
- 扩展 audit 检查：
  - 文件存在
  - JSON 可解析
  - 包含 `pack` object
  - 包含 `pack.description`
  - 包含整数型 `pack.pack_format`
- 保持对旧 workspace 的兼容。

价值：

- 补齐资源包 / 数据包基础元信息。
- 让 V1.0 前的 audit 更完整。

## V1.0 MVP 文档与工作流收口

目标：将已经可工作的生成器整理成可展示、可复现的 MVP。

完成内容：

- 增加完整 README。
- 增加 README 中文版本。
- 增加 `docs/modspec.md`。
- 增加 `docs/test-matrix.md`。
- 文档化以下命令：
  - generate
  - modify
  - audit
  - build
  - repair
  - print-schema
  - test-examples
  - LLM mock
  - OpenAI-compatible LLM
- 增加 `generate --audit`、`modify --audit`、`generate-from-spec --audit`。
- 改善 CLI help 文案。

价值：

- 让项目更容易运行、解释和评估。
- 形成适合 GitHub、面试和项目展示的文档基础。

## V1.1 轻量 Agent 编排

目标：在不破坏确定性生成的前提下，加入适合简历展示的多 Agent 工作流。

完成内容：

- 新增 `agent_models.py`。
- 新增 `agent_orchestrator.py`。
- 新增 CLI 命令组：
  - `agent generate`
  - `agent modify`
- 增加显式角色 trace：
  - `planner_agent`
  - `reviewer_agent`
  - `executor`
  - `auditor_agent`
  - `repair_agent`
- agent 默认使用 `llm + mock`，方便离线演示。
- 复用现有 OpenAI-compatible LLM client。
- 写入 agent artifacts：
  - `.agent/agent-run.json`
  - `.agent/agent-run.md`
  - 需要 repair analysis 时写入 `.agent/agent-repair-plan.json`
  - 需要 repair analysis 时写入 `.agent/agent-repair-plan.md`
- 增加 `docs/agent-workflow.md`。
- 更新 README 和 test matrix 中的 V1.1 命令。
- 验证 agent generate 和 agent modify 均可通过 build 与 audit。

价值：

- 将项目升级成更清晰的 LLM-assisted Agent 系统。
- 展示多角色编排能力，同时不牺牲可靠性。
- 形成适合简历和面试讲解的亮点：
  - 结构化中间表示
  - 受约束的 LLM planning
  - 确定性执行
  - 项目结构审计
  - build 验证
  - repair-oriented failure analysis

## V1.2 评测与 Benchmark

目标：给 Agent 工作流增加可量化、可重复的评测层。

完成内容：

- 新增 `evaluator.py`。
- 新增 CLI 命令：
  - `eval`
- 增加默认离线 benchmark case，覆盖：
  - 基础红宝石生成
  - 行为型物品生成
  - 右键药水效果物品生成
  - 食物效果生成
  - 矿石自然生成
  - modify 给已有矿石添加 worldgen
- 复用 V1.1 的 `AgentOrchestrator`，没有另开一条生成路径。
- 增加 expected feature 检查，会读取最终 `.agent/modspec.json`，确认期望 feature 是否真的存在。
- 增加聚合指标：
  - 总体成功率
  - 期望 feature 命中率
  - planner 成功率
  - audit 成功率
  - 可选 build 成功率
  - generated files 数量统计
  - modify added / updated / skipped 统计
- 写入 eval artifacts：
  - `workspace/eval-runs/<run-id>/.agent/eval-cases.json`
  - `workspace/eval-runs/<run-id>/.agent/eval-report.json`
  - `workspace/eval-runs/<run-id>/.agent/eval-report.md`
- 新增 `docs/eval.md`。
- 更新 README 和 test matrix 中的 V1.2 命令。

价值：

- 让项目从“单次 smoke test 能跑通”升级到“可以批量评测 Agent 表现”。
- 后续更换 planner、LLM provider 或 generator 逻辑时，可以用同一套 benchmark 做对比。
- 对简历和面试叙事更有说服力：项目不只是接入 LLM 和多 Agent，还具备结构化评测指标。

## V1.3 自动化回归测试

目标：把核心 smoke 覆盖沉淀成快速、可重复执行的测试套件。

完成内容：

- 新增 `tests/`。
- 使用 Python 标准库 `unittest`，不引入第三方测试依赖。
- 增加生成与审计测试：
  - 基础红宝石生成成功
  - 生成项目可以通过 audit
  - `pack.mcmeta` 被生成并记录
- 增加负向 audit 测试：
  - 删除生成的 item model 后，audit 会失败并报告错误
- 增加 Agent 工作流测试：
  - mock LLM 的 `agent generate` 可以成功，并写入 `agent-run.json`
- 增加 Eval 工作流测试：
  - 默认 eval 子集能输出 feature metrics
  - expected feature 缺失时 eval 会失败
- 增加 CLI 参数解析测试：
  - 顶层 help 包含 `eval` 和 `agent`
  - `eval` 参数能正确解析
  - `generate --audit` 参数能正确解析
- 从包顶层 API 导出 `ModProjectPlanner`。
- 新增 `docs/testing.md`。
- 更新 README 和 test matrix 中的 V1.3 测试命令。

价值：

- 后续继续加功能前，可以先跑自动化测试确认旧链路没坏。
- 默认测试不跑 Gradle build，因此速度快、环境依赖少。
- 对简历和面试叙事更完整：项目不只“能生成”，还有自动化回归测试保障。

## V1.4 一键质量门禁

目标：给项目增加一个适合 demo、提交前检查和后续开发的统一质量门禁命令。

完成内容：

- 新增 `quality_gate.py`。
- 新增 CLI 命令：
  - `quality-gate`
- 默认质量门禁会运行：
  - Python `compileall`
  - `unittest discover`
  - `print-schema --json`
  - `test-examples --no-build --json`
  - `eval --planner llm --llm-provider mock --no-build --limit 2 --json`
- 增加可选 `--build-smoke`，用于执行较慢的 Gradle build smoke。
- 每个检查都会记录 stdout/stderr 日志：
  - `workspace/quality-gate-runs/<run-id>/.agent/logs/`
- 写入 quality gate artifacts：
  - `workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.json`
  - `workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.md`
- 增加开发时可用的跳过参数：
  - `--no-compile`
  - `--no-unittest`
  - `--no-schema`
  - `--no-examples`
  - `--no-eval`
- 新增 `docs/quality-gate.md`。
- 更新 README 和 test matrix 中的 V1.4 命令。
- 增加 quality gate CLI 参数解析和 schema-only runner 测试。

价值：

- 把分散的可靠性检查整合成一个可复现的一键命令。
- 后续做功能升级前，可以先跑质量门禁确认基础链路稳定。
- 对简历和面试叙事更像工程项目：不仅有 Agent、评测和测试，还有统一质量门禁。

## V1.5 CI 质量门禁

目标：把本地的一键质量门禁接入 GitHub Actions，让项目具备更完整的 GitHub 展示和工程化验证能力。

完成内容：

- 新增 GitHub Actions workflow：
  - `.github/workflows/quality-gate.yml`
- CI 触发条件包括：
  - push 到 `main`
  - pull request
  - 手动触发 `workflow_dispatch`
- CI 使用 Python `3.11`，并设置 `PYTHONPATH=src`。
- CI 复用 V1.4 的质量门禁命令：
  - `python -m agent.cli quality-gate --run-name ci-quality-gate --json`
- CI 会上传质量门禁产物：
  - `workspace/quality-gate-runs/ci-quality-gate/.agent/**`
- 默认 CI 不运行 `--build-smoke`，避免 GitHub runner 上的 Gradle / NeoForge 构建过慢或不稳定。
- 新增 `docs/ci.md`。
- 新增 `tests/test_ci_workflow.py`，静态检查 workflow 的关键配置。
- 更新 README 和 test matrix 中的 V1.5 CI 说明。
- 更新 package metadata 到 `1.5.0`。

价值：

- 让项目从“本地可验证”推进到“GitHub 上也能自动验证”。
- 对简历和面试叙事更完整：项目不仅有 LLM、多 Agent、eval、unittest、quality gate，还有 CI。
- 保持默认 CI 快速稳定，同时仍保留本地 `quality-gate --build-smoke` 作为更强验证。

## V1.6 环境诊断 Doctor

目标：增加一个本地 preflight 诊断命令，让新环境、新 clone 或面试展示前更容易确认项目是否具备运行条件。

完成内容：

- 新增 `doctor.py`。
- 新增 CLI 命令：
  - `doctor`
- Doctor 会检查：
  - Python 版本
  - 项目目录结构
  - 兼容入口 `src/agent/cli.py`
  - NeoForge 模板目录
  - 模板里的 Gradle wrapper 文件
  - 模板 Java toolchain 版本
  - workspace 目录和父目录写入权限
  - `PYTHONPATH`
  - 关键文档
  - GitHub Actions workflow
  - `java -version`
- 增加 `--no-java`，可跳过 Java 检查。
- 增加 `--strict`，可把 warning 也视为失败。
- 写入 doctor artifacts：
  - `workspace/doctor-runs/<run-id>/.agent/doctor-report.json`
  - `workspace/doctor-runs/<run-id>/.agent/doctor-report.md`
- 新增 `docs/doctor.md`。
- 新增 doctor 单元测试和 CLI 参数解析测试。
- 更新 README 和 test matrix 中的 V1.6 命令。
- 更新 package metadata 到 `1.6.0`。

价值：

- 让别人拿到项目后，可以先运行 `doctor` 判断环境问题，而不是直接在 generate/build 里撞报错。
- 继续增强工程可靠性叙事：项目不仅有 Agent、eval、tests、quality gate、CI，还有本地环境诊断。
- Doctor 是只读诊断，不会生成 Mod，也不会改已有 workspace，适合安全地作为第一步检查。

## V1.7 Doctor 集成质量门禁

目标：让环境诊断不只作为单独命令存在，而是进入默认可靠性链路，成为 `quality-gate` 的第一步。

完成内容：

- 将 doctor 集成进 `quality-gate`，新增默认检查：
  - `doctor_environment`
- 默认质量门禁现在会运行：
  - `doctor --no-java --json`
  - Python `compileall`
  - `unittest discover`
  - `print-schema --json`
  - `test-examples --no-build --json`
  - mock LLM eval smoke
  - 可选 build smoke
- 增加 quality gate 参数：
  - `--no-doctor`
  - `--doctor-java`
  - `--doctor-strict`
- 更新 GitHub Actions artifact 上传路径，额外上传：
  - `workspace/quality-gate-runs/ci-quality-gate/.agent/**`
  - `workspace/doctor-runs/ci-quality-gate-doctor/.agent/**`
- 更新 CI workflow 测试，确认 CI 没有禁用 doctor。
- 更新 quality gate 测试，覆盖 doctor pass / skip 行为。
- 更新 README、CI 文档、doctor 文档、quality gate 文档和测试矩阵。
- 更新 package metadata 到 `1.7.0`。

价值：

- 让本地和 CI 的可靠性检查更完整：如果是环境问题，会先在 doctor 阶段暴露出来。
- 默认质量门禁跳过 Java 诊断，保持 CI 快速稳定。
- 需要强验证时，仍可使用 `quality-gate --doctor-java --build-smoke`。

## V1.8 Showcase 展示报告

目标：增加一个适合 GitHub、简历和面试展示的一键 demo flow，把当前 Agent 系统能力汇总成一份报告。

完成内容：

- 新增 `showcase.py`。
- 新增 CLI 命令：
  - `showcase`
- 默认 showcase 会运行：
  - 环境诊断 doctor，不检查 Java
  - mock LLM 多角色 `agent generate`
  - mock LLM 多角色 `agent modify`
  - 离线 eval smoke benchmark
  - 可选 quality gate，传入 `--quality-gate` 时执行
- 展示用 workspace 隔离在：
  - `workspace/showcase-runs/<run-id>/workspaces/`
- 展示报告写入：
  - `workspace/showcase-runs/<run-id>/.agent/showcase-report.json`
  - `workspace/showcase-runs/<run-id>/.agent/showcase-report.md`
- 增加参数：
  - `--run-name`
  - `--planner`
  - `--llm-provider`
  - `--eval-limit`
  - `--build`
  - `--quality-gate`
- 新增 `docs/showcase.md`。
- 新增 showcase runner 测试和 CLI 参数解析测试。
- 更新 README 和 test matrix。
- 更新 package metadata 到 `1.8.0`。

价值：

- 形成一份适合放到 GitHub、简历或面试演示里的项目展示报告。
- 展示项目已经不是单点 demo，而是一套完整 Agent 系统：doctor、LLM planner、多 Agent 编排、modify、audit、eval 和可选 quality gate。
- 默认不跑 Gradle build，保证 showcase 足够快；需要强验证时可以显式加 `--build`。

## V1.9 Capability 能力矩阵

目标：导出一份结构化能力矩阵，作为当前项目能力的统一真相源。

完成内容：

- 新增 `capabilities.py`。
- 新增 CLI 命令：
  - `capabilities`
- 能力矩阵覆盖：
  - 项目元信息
  - 核心工作流
  - 生成内容类型
  - 行为模板
  - worldgen 支持
  - planner 与 LLM 边界
  - 可靠性和验证层
  - 当前限制
- 能力矩阵产物写入：
  - `workspace/capability-runs/<run-id>/.agent/capabilities.json`
  - `workspace/capability-runs/<run-id>/.agent/capabilities.md`
- 新增 `docs/capabilities.md`。
- 新增 capability catalog 测试和 CLI 参数解析测试。
- 更新 README 和 test matrix。
- 更新 package metadata 到 `1.9.0`。

价值：

- 让 README、showcase、简历和面试讲解可以引用同一份结构化能力清单。
- 更容易把项目解释成一套完整系统，而不是一堆零散命令。
- 为后续自动化生成项目介绍、版本说明或展示页打基础。

## 当前架构总结

项目当前支持：

- `generate`：从自然语言或 spec 创建新 workspace
- `modify`：对已有 workspace 做自然语言增量修改
- `audit`：确定性检查 workspace 与 `ModSpec` 是否一致
- `build`：Gradle 构建验证
- `repair`：生成构建失败修复上下文
- `agent generate`：多角色编排的新项目生成
- `agent modify`：多角色编排的已有项目修改
- `eval`：面向 Agent 工作流的 benchmark 评测
- `unittest`：快速自动化回归检查
- `quality-gate`：一键可靠性门禁
- GitHub Actions CI：push / pull request 时自动运行质量门禁
- `doctor`：本地环境诊断
- `quality-gate` 内置 doctor preflight
- `showcase`：一键生成项目展示报告
- `capabilities`：结构化项目能力矩阵导出

核心设计原则：

```text
LLM / natural language -> ModSpec -> deterministic Java/JSON generation -> audit/build/repair
```

这让 LLM 输出保持受控，也让生成项目更容易测试、复现和调试。
## V2.0 Agent Workflow Trace

目标：把已有 `agent generate` / `agent modify` 从轻量步骤编排升级为可追踪的多角色 Agent 工作流。

完成内容：

- 新增 `AgentDecision` 和 `AgentPromptTrace` 数据结构。
- `agent-run.json` 现在包含：
  - `steps`
  - `decisions`
  - `prompt_traces`
- 每次 workspace agent run 额外写入：
  - `.agent/agent-decisions.md`
  - `.agent/prompt-trace.json`
- `llm_planner` 的 artifacts 现在记录 system prompt，并写入：
  - `.agent/planner-system-prompt.txt`
- `agent generate` 记录 planner / reviewer / executor / auditor / repair 的决策。
- `agent modify` 记录 context_loader / planner / reviewer / executor / auditor / repair 的决策。
- 修复 mock LLM modify 被 existing ModSpec 污染的问题：modify 模式优先只根据 Change Request 生成 patch。
- `capabilities` 增加：
  - `agent_prompt_trace`
  - `agent_decision_log`
- package metadata 更新到 `2.0.0`。
- 新增 `docs/agent-workflow.md`。

价值：

- 面试叙事更清晰：项目现在不是单纯的生成器，而是可追踪的多角色 LLM 开发 Agent。
- 调试更容易：可以从 `prompt-trace.json` 看到 planner 输入、LLM 原始 JSON、normalized ModSpec 和 warnings。
- 复盘更容易：可以从 `agent-decisions.md` 看到每个角色的决策理由。
## V2.1 Repair Loop 2.0

目标：把已有 repair artifacts 推进一步，形成安全的自动修复闭环。

完成内容：

- 新增 `repair_loop.py`。
- 新增 CLI 命令：
  - `repair-loop`
- `repair-loop` 支持：
  - `--max-attempts`
  - `--audit` / `--no-audit`
  - `--build` / `--no-build`
  - `--json`
- 第一版自动修复策略为：
  - `regenerate_managed_files`
- 修复过程会根据 `.agent/modspec.json` 重新生成受控文件：
  - Java source
  - item/block models
  - textures
  - lang files
  - loot tables
  - tags
  - worldgen JSON
  - `pack.mcmeta`
- 每次 repair loop 写入：
  - `.agent/repair-loop-report.json`
  - `.agent/repair-loop-report.md`
- 如果 build 失败，继续复用已有 repair artifacts：
  - `.agent/debug-context.md`
  - `.agent/fix-request.md`
  - `.agent/suspected-errors.json`
- 新增 `docs/repair-loop.md`。
- 新增 `tests/test_repair_loop.py`，覆盖：
  - 健康 workspace 不做修复
  - 删除生成的 item model 后 repair-loop 可自动恢复
- package metadata 更新到 `2.1.0`。

价值：

- 修复闭环从“只给修复上下文”升级为“能自动修复一类安全问题”。
- 保持安全边界：V2.1 不让 LLM 直接改 Java，只从 ModSpec 重生成受控文件。
- 对演示很有用：可以故意删除一个生成文件，然后运行 `repair-loop` 展示自动恢复能力。
