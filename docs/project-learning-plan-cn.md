# 7 天学会 NeoForge Mod Agent

> 文档定位：这是唯一主学习路线。其他学习、简历、八股和作品集文档都作为补充材料；如果只能看一个文件，就先看本文。

这份文档不是面试展示稿，而是学习路线。目标是让你在 7 天内真正理解这个项目：知道它为什么这样设计、一次生成经过哪些阶段、关键源码在哪里、失败时先看什么证据。

学完后不要求你马上能独立扩展大功能，但要能用自己的话讲清：

- 项目整体架构。
- 自然语言到 workspace 的完整数据流。
- `ModSpec-first + Direct Code Lane` 的设计取舍。
- Agent、LLM、RAG、audit、build、repair、eval、replay 各自负责什么。
- 关键源码模块的位置和职责。

## 学习主线

先记住这条数据流：

```text
CLI
-> Agent Runtime
-> Planner / LLM Provider
-> ModSpec / Validator
-> Generator
-> optional Direct Code Lane
-> Auditor / Builder / Repair
-> Eval / Replay / Dashboard
```

更具体地说：

```text
自然语言需求
-> ModSpec-first routing
-> ModSpec / Behavior DSL / repair plan / direct-code plan
-> deterministic generator / reviewed Direct Code Lane
-> Java / JSON / PNG / resources
-> audit / build / repair
-> eval / benchmark / replay / dashboard evidence
```

## Day 1：跑通项目

目标：先知道项目会产生什么，不急着读全部源码。

读：

- `README.md`
- `docs/README.md`
- `docs/readme-glossary-cn.md`
- `docs/project-limitations.md`

跑：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name learning-ruby --overwrite --no-build --json
py -3.11 -m agent.cli audit learning-ruby --json
```

重点看：

```text
workspace/learning-ruby/.agent/modspec.json
workspace/learning-ruby/.agent/generation-summary.json
workspace/learning-ruby/.agent/audit-report.json
workspace/learning-ruby/.agent/agent-run.json
workspace/learning-ruby/.agent/prompt-trace.json
workspace/learning-ruby/src/main/java/
workspace/learning-ruby/src/main/resources/
```

必须能回答：

- 一次 `agent generate` 最终创建了哪些目录？
- `.agent/modspec.json` 和 `.agent/generation-summary.json` 分别证明什么？
- `mock` LLM 为什么适合学习和本地复现？
- `audit` 是重新生成文件，还是检查已有 workspace？

## Day 2：理解 ModSpec 和规格层

目标：理解为什么 `ModSpec` 是项目的真相源。

读：

- `docs/domain-spec.md`
- `docs/modspec.md`
- `docs/llm-capability-layers-cn.md`

看源码：

- `src/neoforge_agent/domain_spec.py`
- `src/neoforge_agent/models.py`
- `src/neoforge_agent/schema.py`
- `src/neoforge_agent/validator.py`

跑：

```powershell
py -3.11 -m agent.cli domains --json
py -3.11 -m agent.cli domains --status stable --json
```

必须能回答：

- `DomainSpec` 和 `ModSpec` 有什么区别？
- 为什么当前只能说 `minecraft.neoforge` 是稳定 domain？
- validator 主要检查的是用户需求，还是结构化规格？
- 为什么 generator / audit / repair 都要围绕 `ModSpec`？

## Day 3：理解生成层

目标：理解 Java、JSON、PNG 不是 LLM 自由写的，而是 generator 根据规格稳定生成的。

读：

- `docs/behavior-dsl.md`
- `docs/machine-dsl.md`
- `docs/entity-dsl.md`
- `docs/world-structure-dsl.md`

看源码：

- `src/neoforge_agent/project_generator.py`
- `src/neoforge_agent/code_generator.py`
- `src/neoforge_agent/asset_generator.py`
- `src/neoforge_agent/worldgen_generator.py`
- `src/neoforge_agent/behavior_generator.py`
- `src/neoforge_agent/machine_generator.py`
- `src/neoforge_agent/entity_generator.py`

跑：

```powershell
py -3.11 -m agent.cli generate-from-spec .\examples\ruby_item.json --workspace-name learning-spec-ruby --overwrite --audit --no-build --json
```

必须能回答：

- `agent generate` 和 `generate-from-spec` 有什么区别？
- 为什么 deterministic generator 比 LLM 直接写最终工程文件更稳定？
- `src/main/java` 和 `src/main/resources` 分别主要放什么？
- Behavior DSL、Machine DSL、Entity DSL 各自解决什么类型的问题？

## Day 4：理解 audit / build / repair

目标：理解生成完成后，系统如何证明它不是“看起来成功”。

读：

- `docs/testing.md`
- `docs/test-matrix.md`
- `docs/failure-repair-demo.md`
- `docs/repair-loop.md`
- `docs/repair-eval.md`

看源码：

- `src/neoforge_agent/auditor.py`
- `src/neoforge_agent/builder.py`
- `src/neoforge_agent/failure_lab.py`
- `src/neoforge_agent/repair.py`
- `src/neoforge_agent/repair_loop.py`

跑：

```powershell
.\scripts\failure_repair_demo.ps1 -RunName learning-failure -Case delete_model
py -3.11 -m unittest discover -s tests -v
```

必须能回答：

- `audit` 能发现什么问题？
- `audit` 不能替代什么？
- `build` 通过为什么不等于 Minecraft runtime 一定通过？
- repair-loop 为什么不让 LLM 随便改文件？

## Day 5：理解 Agent 流程

目标：理解 Agent 不是“起了几个名字”，而是一个有阶段、有状态、有证据的 workflow。

读：

- `docs/agent-workflow.md`
- `docs/agent-design-report-cn.md`
- `docs/agent-run-replay.md`

看源码：

- `src/neoforge_agent/agent_runtime.py`
- `src/neoforge_agent/agent_orchestrator.py`
- `src/neoforge_agent/planner.py`
- `src/neoforge_agent/llm_planner.py`
- `src/neoforge_agent/replay.py`

跑：

```powershell
py -3.11 -m agent.cli replay workspace/learning-ruby --json
```

重点看：

```text
workspace/learning-ruby/.agent/agent-run.json
workspace/learning-ruby/.agent/agent-decisions.md
workspace/learning-ruby/.agent/agent-run-replay.md
workspace/learning-ruby/.agent/agent-run-replay.html
```

必须能回答：

- planner、reviewer、executor、auditor、repair 分别负责什么？
- `agent-run.json` 为什么比普通日志更有价值？
- 这个项目更像 ReAct，还是 Plan-and-Execute 加验证闭环？
- replay 是重新执行任务，还是只读历史证据？

## Day 6：理解 LLM / RAG / Tool

目标：理解大模型工程部分的边界：mock、real provider、RAG、tool manifest 都不是装饰。

读：

- `docs/real-vs-mock-llm-report.md`
- `docs/real-llm-stability.md`
- `docs/llm-engineering-report.md`
- `docs/rag-indexing-strategy-cn.md`
- `docs/tool-calling-contract.md`

看源码：

- `src/neoforge_agent/llm_client.py`
- `src/neoforge_agent/llm_provider.py`
- `src/neoforge_agent/llm_planner.py`
- `src/neoforge_agent/knowledge_base.py`
- `src/neoforge_agent/repair_rag.py`
- `src/neoforge_agent/rag_eval.py`
- `src/neoforge_agent/tool_manifest.py`

跑：

```powershell
py -3.11 -m agent.cli rag-eval --json
py -3.11 -m agent.cli tools-manifest --run-name learning-tools --json
py -3.11 -m agent.cli llm-engineering-report --run-name learning-llm --json
```

必须能回答：

- mock LLM 和 real LLM 分别承担什么角色？
- 为什么 fallback 成功不能算真实 LLM 成功？
- RAG 在 planner 和 repair 里怎么体现？
- tool manifest 和 Function Calling / MCP 是什么关系？

## Day 7：理解 Direct Code Lane、Capability Harvest Loop 和项目不足

目标：理解 Direct Code Lane 是为了突破 ModSpec 表达上限，但仍然不是无边界 Coding Agent；同时理解后续主线为什么要用 Free-Code Lab 收集成功样本，再固化回稳定 generator。

读：

- `docs/direct-code-lane.md`
- `docs/capability-harvest-loop.md`
- `docs/project-limitations.md`
- `docs/controlled-java-extension.md`

看源码：

- `src/neoforge_agent/direct_code_agent.py`
- `src/neoforge_agent/free_code_lab.py`
- `src/neoforge_agent/agent_runtime.py`
- `tests/test_direct_code_agent.py`
- `tests/test_free_code_lab.py`
- `tests/test_agent_eval.py`

跑：

```powershell
py -3.11 -m unittest tests.test_direct_code_agent tests.test_free_code_lab tests.test_agent_eval -v
py -3.11 -m agent.cli harvest-report --run-name learning-harvest --json
```

必须能回答：

- Direct Code Lane 为什么存在？
- 它支持哪些 patch 操作？
- 为什么它不是自由 diff / 任意 coding agent？
- review、snapshot、audit、build、rollback evidence 分别解决什么风险？
- Free-Code Lab 和 Direct Code Lane 有什么区别？
- 为什么成功 lab 样本不能直接进入 generator？
- 当前最大的 5 个不足是什么？

## Day 01-07 人话讲义与复述练习

这一节是给复习用的，不是新的任务清单。前面的 Day 1-7 告诉你读什么、跑什么；这里告诉你每一天到底要理解成什么，以及面试时怎么讲。

复习时建议按这个顺序看：

```text
先看“人话理解”
再看“关键证据”
最后背“面试说法”
```

### Day 01：项目跑通后，到底证明了什么？

人话理解：

Day 1 不是为了炫命令跑成功，而是为了建立第一张地图：这个项目接收一句自然语言，然后生成一个完整的 NeoForge workspace。生成结果不是只有 Java 文件，还包括资源 JSON、PNG 贴图、`.agent` 证据文件和审计报告。

你跑的核心命令是：

```powershell
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name learning-ruby --overwrite --no-build --json
py -3.11 -m agent.cli audit learning-ruby --json
```

关键证据：

```text
workspace/learning-ruby/.agent/modspec.json
workspace/learning-ruby/.agent/generation-summary.json
workspace/learning-ruby/.agent/audit-report.json
workspace/learning-ruby/.agent/agent-run.json
workspace/learning-ruby/.agent/prompt-trace.json
```

这些文件分别证明：

- `modspec.json`：系统最终认定要生成什么，是生成、审计、修复共同围绕的真相源。
- `generation-summary.json`：实际写出了哪些文件，证明 generator 真的落盘了哪些 Java / JSON / PNG。
- `audit-report.json`：生成后检查是否通过，证明不是“看起来生成了”。
- `agent-run.json`：一次 agent run 的结构化记录，说明每个阶段发生了什么。
- `prompt-trace.json`：planner 的输入、provider、RAG、模型输出和规范化过程。

复述说法：

> 我先用 mock LLM 跑通完整生成链路。mock 的价值不是替代真实模型，而是稳定、离线、可复现，适合学习、CI 和演示。一次 `agent generate` 会生成完整 NeoForge workspace，并在 `.agent/` 下留下 ModSpec、生成摘要、审计报告、agent trace 和 prompt trace，所以可以复盘每一步，而不是只看最后有没有文件。

不要这样说：

> mock 跑通就说明真实 LLM 一定没问题。

正确边界是：

> mock 证明工程链路稳定，real LLM 还需要单独验证 provider、schema、成本、延迟和失败样本。

### Day 02：为什么 ModSpec 是真相源？

人话理解：

`DomainSpec` 是“领域规格”的抽象概念，表示这个 agent 未来可以支持不同领域。`ModSpec` 是当前稳定落地的 NeoForge 规格。也就是说，`DomainSpec` 是上层抽象，`ModSpec` 是 `minecraft.neoforge` 这个 domain 的具体实现。

你看到的 domain 命令结果说明：

```text
stable: minecraft.neoforge
planned: spring.api, unity.component
```

这意味着当前只能说 NeoForge 是稳定 domain。Spring / Unity 只是 planned entry，不能包装成已经完成多领域生成器。

关键源码：

```text
src/neoforge_agent/domain_spec.py
src/neoforge_agent/models.py
src/neoforge_agent/schema.py
src/neoforge_agent/validator.py
```

怎么理解 validator：

validator 检查的不是用户自然语言本身，而是自然语言被 planner 转成的结构化规格。它会看 ID、字段、引用、feature 类型和可生成边界是否合理。

复述说法：

> 这个项目的关键设计是把自然语言先转成结构化 `ModSpec`。`ModSpec` 是生成、审计和修复的共同真相源。validator 不直接判断用户说得好不好，而是检查 planner 产出的结构化规格能不能被稳定生成。这样 LLM 的不确定性被限制在规划层，后面的 generator / audit / repair 都可以围绕同一份规格做确定性处理。

不要这样说：

> 项目已经支持 Spring 和 Unity。

正确边界是：

> `spring.api` 和 `unity.component` 目前只是 planned domain registry entries，真正稳定的是 `minecraft.neoforge`。

### Day 03：生成层不是 LLM 自由写代码

人话理解：

Day 3 的重点是：Java、JSON、PNG 不是 LLM 直接写出来的，而是 generator 根据 `ModSpec` 和 DSL 稳定生成的。

两条路线的区别：

```text
agent generate
= 自然语言 -> planner/mock or real LLM -> ModSpec -> generator -> audit

generate-from-spec
= 已有 JSON ModSpec -> validator -> generator -> audit
```

你对比过两个 workspace：

```text
learning-ruby
= 自然语言 + mock planner
= 生成 item / block / ore / food / sword / recipes 等较完整内容

learning-spec-ruby
= 直接 examples/ruby_item.json
= 只生成一个 ruby item
```

关键源码：

```text
src/neoforge_agent/project_generator.py
src/neoforge_agent/code_generator.py
src/neoforge_agent/asset_generator.py
src/neoforge_agent/worldgen_generator.py
src/neoforge_agent/behavior_generator.py
src/neoforge_agent/machine_generator.py
src/neoforge_agent/entity_generator.py
```

目录理解：

```text
src/main/java
= 注册类、行为类、机器、实体、受控 extension 等 Java 代码

src/main/resources
= models、textures、lang、recipes、loot tables、tags、worldgen 等资源
```

复述说法：

> 我没有让 LLM 直接写最终 Minecraft Mod。LLM 或规则 planner 先产出 `ModSpec`，再由确定性 generator 渲染 Java、资源 JSON 和 PNG。这样做的好处是路径、命名、资源引用和注册结构更稳定，也方便 audit 对照 `ModSpec` 检查。

不要这样说：

> LLM 会自动生成所有 Java 和资源文件。

正确边界是：

> LLM 主要负责规划结构化意图；最终文件主要由 generator 生成。只有 Direct Code Lane 场景下，才允许结构化、受审查的小范围 patch。

### Day 04：audit / build / repair 是验证闭环

人话理解：

Day 4 的核心是：生成完成不等于可信。项目要用 audit、build、repair 证明结果不是只有 happy path。

三个概念分清：

```text
audit
= 检查 workspace 文件、资源、模型、贴图、loot、worldgen、generation summary 和 ModSpec 是否一致

build
= 跑 Gradle 编译，检查 Java/API/依赖层面问题

repair-loop
= 失败后基于 .agent/modspec.json 重新生成 managed files，而不是让 LLM 随便改文件
```

你跑过故障注入：

```powershell
.\scripts\failure_repair_demo.ps1 -RunName learning-failure -Case delete_model
```

这次故障是故意删除模型文件。初始 audit 失败，repair-loop 根据 `modspec.json` 重生成 managed files，最终 audit 成功。

关键报告：

```text
workspace/failure-repair-demos/learning-failure/.agent/failure-repair-demo-report.md
workspace/failure-lab-runs/learning-failure/.agent/failure-lab-report.md
workspace/failure-lab-runs/learning-failure/workspaces/delete_model/.agent/repair-rag-context.md
workspace/failure-lab-runs/learning-failure/workspaces/delete_model/.agent/repair-loop-report.md
workspace/failure-lab-runs/learning-failure/workspaces/delete_model/.agent/audit-report.md
```

这些报告怎么读：

- `failure-repair-demo-report.md`：人类总览，看整次 demo 成功还是失败。
- `failure-lab-report.md`：故障实验汇总，这次只跑了 `delete_model`。
- `repair-rag-context.md`：修复前检索到的知识依据，不直接修文件。
- `repair-loop-report.md`：修复执行过程，最关键。
- `audit-report.md`：最终 workspace 是否健康。

复述说法：

> 这个项目有验证和恢复闭环。audit 检查生成资源和 `ModSpec` 是否一致，build 检查编译层面问题，repair-loop 在可控范围内根据 `.agent/modspec.json` 重生成 managed files。修复不是让 LLM 自由编辑文件，而是利用真相源和确定性 generator 做受控恢复。

必须守住的边界：

```text
audit 不能替代 build
build 不能替代 Minecraft runtime 测试
repair-loop 不能修所有失败，只能修受控 managed files 范围内的问题
```

### Day 05：Agent 是 workflow，不是几个名字

人话理解：

Day 5 要理解：这个项目不是“起了 planner、reviewer、executor 几个名字”就叫 Agent。它是一套有阶段、有状态、有证据的 workflow agent。

核心流程：

```text
planner
-> reviewer
-> executor
-> auditor
-> repair
-> trace / replay
```

角色职责：

- `planner_agent`：把自然语言转成 `ModSpec`、patch、DSL 或 direct-code plan。
- `reviewer_agent`：用 schema / validator 检查 planner 输出是否可信。
- `executor_agent`：调用确定性 generator 或受控 patch 执行落盘。
- `auditor_agent`：检查 workspace 是否符合 `ModSpec` 和生成摘要。
- `repair_agent`：失败后根据 audit/build 证据做 root cause、RAG 和修复计划。
- `trace_writer`：把运行过程写成可复盘证据。

你跑过 replay：

```powershell
py -3.11 -m agent.cli replay workspace/learning-ruby --json
```

replay 不是重新执行任务。它只读取历史 `.agent/agent-run.json`，生成：

```text
workspace/learning-ruby/.agent/agent-run-replay.json
workspace/learning-ruby/.agent/agent-run-replay.md
workspace/learning-ruby/.agent/agent-run-replay.html
```

复述说法：

> 这个项目更像 Plan-and-Execute 加验证闭环，而不是开放式 ReAct。Planner 先给出结构化计划，Reviewer 校验，Executor 执行，Auditor 验证，Repair 根据失败证据恢复。每次运行会留下 `agent-run.json`、`agent-decisions.md`、`prompt-trace.json` 和 replay 页面，所以它不是黑箱调用模型，而是可复盘的 workflow agent。

不要这样说：

> 这是多个自治 Agent 互相聊天完成任务。

正确边界是：

> 它是单 runtime 下的 multi-role workflow agent，不是多个完全自治的聊天机器人。

### Day 06：LLM / RAG / Tool 的边界

人话理解：

Day 6 要把四个容易混淆的词分开：

```text
mock LLM
= 稳定、离线、可复现，用于学习、CI、演示

real LLM
= 验证真实模型规划能力，但有 key、网络、成本、超时和 schema 风险

RAG
= 给 planner 和 repair 提供本地项目知识，不替代 validator / audit / build

tool manifest
= 把内部 CLI 能力写成工具契约，未来可包装成 Function Calling / MCP，但当前不是 MCP server
```

你生成过三类报告：

```text
workspace/rag-eval-runs/<run-id>/.agent/rag-eval-report.md
workspace/tool-manifest-runs/learning-tools/.agent/tools-manifest.md
workspace/llm-engineering-runs/learning-llm/.agent/llm-engineering-report.md
```

RAG eval 怎么读：

```text
Recall@1
= 正确知识是否排第 1

Recall@K
= 正确知识是否出现在前 K 个结果里

MRR
= 正确答案排得越靠前越好

category / capability hit
= 不仅命中文本，还要命中正确知识类别和能力
```

Tool manifest 怎么读：

它列出 `agent_generate`、`agent_modify`、`audit_workspace`、`repair_loop`、`rag_eval`、`evidence_chain_report` 等内部能力，并描述：

```text
输入 schema
输出 artifacts
安全边界
副作用
未来可以映射到 Function Calling / MCP
```

但它明确不是正在运行的 MCP server。

复述说法：

> LLM 在项目里主要承担 planner 角色。mock provider 用于稳定回归和演示，real provider 用于验证真实模型能力。RAG 是本地可回放知识层，给 planner 和 repair 提供 NeoForge/API/资源路径/修复规则等上下文，但最终正确性仍由 validator、audit 和 build 决定。tool manifest 是内部工具能力的 schema 化契约，是未来接 Function Calling 或 MCP 的基础，但当前不应宣称已经实现 MCP server。

必须会答：

```text
fallback 成功为什么不能算真实 LLM 成功？
```

答案：

> 因为 fallback 可能是规则 planner 或备用路径兜底成功。只有明确使用 real provider、没有 fallback，并且 prompt trace / llm engineering report 证明真实调用成功，才能算 real LLM 成功。

### Day 07：Direct Code Lane 和项目不足

人话理解：

Day 7 是为了回答一个面试高频追问：

```text
你这个是不是通用 Coding Agent？
```

答案是：不是。

它是 `ModSpec-first + 受控 Direct Code Lane`。默认仍然先走 `ModSpec` 和 generator。只有当 `ModSpec` 表达不了某些小范围源码补丁时，才进入 Direct Code Lane。

Direct Code Lane 当前只支持：

```text
write_file
= 写一个完整文件

replace_text
= 在已有文件里做一次精确匹配替换
```

它不支持：

```text
自由 diff
模糊多处替换
删除文件
移动文件
大规模重构
AST patch
跨文件自动合并
```

它会生成这些证据：

```text
.agent/direct-code-plan.json
.agent/direct-code-plan.md
.agent/direct-code-review.json
.agent/direct-code-diff.md
.agent/direct-code-report.json
.agent/direct-code-rollback-report.json
.agent/direct-code-snapshots/
```

`Controlled Java Extension` 和 `Direct Code Lane` 的区别：

```text
Controlled Java Extension
= 更窄、更安全
= 通过 ModSpec 的 java_extension feature 生成 extension 包下的受控 helper class

Direct Code Lane
= 更灵活
= 允许结构化 write_file / replace_text patch
= 但必须 review、snapshot、audit、build 和 rollback evidence
```

当前最大的 5 个不足：

1. Direct Code Lane 还是第一版，只支持简单 patch。
2. Direct Code 失败后没有自动二轮 LLM repair patch。
3. 安全检查不是完整 Java 静态分析器，也不是 OS 级沙箱。
4. audit/build 不等于真实 Minecraft runtime 测试。
5. 稳定 domain 只有 `minecraft.neoforge`，Spring / Unity 仍是 planned。

复述说法：

> Direct Code Lane 是为了解决 `ModSpec` 表达上限，但它不是自由 Coding Agent。LLM 不能直接任意改文件，只能提交结构化 `write_file` 或 `replace_text` patch。系统会检查路径、操作、危险 token、Java package、snapshot 覆盖，并强制 audit 和 Gradle build。失败时会写 rollback report。所以它增强了表达能力，但仍然保留受控边界。

不要这样说：

> 我的项目可以像通用 Coding Agent 一样改任意代码。

正确边界是：

> 它牺牲通用性，换来领域内更强的可复现、可审计、可修复和可展示证据链。

### 7 天总复述

如果只给你 1 分钟复述项目，可以这样讲：

> 这是一个面向 NeoForge Minecraft Mod 的 domain-bounded code generation agent。它不是让 LLM 直接写完整工程，而是把自然语言先转成 `ModSpec`、DSL、patch plan 或 direct-code plan。默认路径是 `ModSpec-first`：planner 负责结构化意图，reviewer 做 schema 和 validator 检查，executor 用确定性 generator 生成 Java、JSON、PNG 和资源文件，auditor/build 验证结果，repair 在失败后基于 `.agent/modspec.json` 和 RAG 做受控恢复。RAG 给 planner 和 repair 提供本地知识，tool manifest 把内部 CLI 能力整理成可调用契约，replay 和各种报告让每次运行可复盘。Direct Code Lane 解决 ModSpec 表达上限，但只接受结构化 patch，并有 review、snapshot、audit、build、rollback evidence，所以它不是无边界 Coding Agent。

## 源码阅读地图

按数据流读源码，比按文件名硬啃更容易。

| 阶段 | 解决什么问题 | 输入 | 输出 | 关键证据 | 推荐测试 |
| --- | --- | --- | --- | --- | --- |
| CLI | 把命令行参数转成内部调用 | 命令、参数、workspace name | runner 参数对象 | 命令 JSON 输出 | `tests/test_cli_parser.py` |
| Agent Runtime | 编排 planner/reviewer/executor/auditor/repair | request、runtime config | stage result、agent run | `.agent/agent-run.json` | `tests/test_agent_eval.py` |
| Planner / LLM Provider | 把自然语言变成结构化意图 | prompt、RAG context、provider config | `ModSpec` 或 intent contract | `.agent/prompt-trace.json` | `tests/test_llm_stability.py` |
| ModSpec / Validator | 校验规格是否可生成 | dict / JSON spec | validated `ModSpec` | validation errors / warnings | `tests/test_domain_spec.py` |
| Generator | 生成 Java / JSON / PNG / resources | `ModSpec` | workspace files | `.agent/generation-summary.json` | `tests/test_generation_audit.py` |
| Direct Code Lane | 安全应用结构化代码补丁 | direct-code plan | modified workspace files | `.agent/direct-code-*.json` | `tests/test_direct_code_agent.py` |
| Auditor / Builder / Repair | 检查、编译、修复生成结果 | workspace、reports | audit/build/repair result | `.agent/audit-report.json` | `tests/test_repair_loop.py` |
| Eval / Replay / Dashboard | 量化和复盘项目运行 | runs、reports、agent trace | HTML / Markdown / JSON report | replay / benchmark / dashboard | `tests/test_replay.py` |

## 自测问题

学完这 7 天后，不要先背术语，先用自己的话回答这些问题：

1. 从一句自然语言到生成 workspace，中间经过哪些阶段？
2. `.agent/` 目录里每类文件分别证明什么？
3. 为什么不用 LLM 直接写整个 Mod？
4. `ModSpec` 和 `DomainSpec` 有什么区别？
5. `agent generate` 和普通 `generate-from-spec` 有什么区别？
6. `audit` 能发现什么，不能发现什么？
7. `build` 通过为什么不等于 Minecraft runtime 一定通过？
8. Direct Code Lane 为什么既增强能力，又没有变成自由 coding agent？
9. mock LLM 和 real LLM 在项目里分别承担什么角色？
10. RAG 在 planner 和 repair 里怎么体现？
11. 如果生成失败，你会先看哪些报告和源码模块？
12. 项目当前最大的 5 个不足是什么？

## 最后验收

完成 7 天学习后，跑这三条命令做一次收尾：

```powershell
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli replay workspace/learning-ruby --json
py -3.11 -m agent.cli capabilities --run-name learning-capabilities --json
```

如果你能对着这些产物讲清“它们分别证明什么”，就说明你已经不是只知道项目名字，而是真的摸到项目骨架了。
