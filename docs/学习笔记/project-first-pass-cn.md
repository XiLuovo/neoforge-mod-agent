# NeoForge Mod Agent 第一遍学习笔记

> 文档定位：这是从零学习本项目后的第一遍复盘笔记。它不是架构真相源，正式口径仍以 `docs/总览/architecture.md` 和 `docs/总览/project-limitations.md` 为准。

## 项目一句话定位

NeoForge Mod Agent 是一个面向 Minecraft NeoForge 的受控代码生成 agent。

它不是让 LLM 直接自由写完整 Mod 工程，而是默认走：

```text
自然语言
-> ModSpec-first routing
-> deterministic generator
-> audit / build / repair
-> replay / evidence
```

当 `ModSpec` 表达不了小范围代码需求时，可以进入受控的 Direct Code Lane。更大的 generate gap 则先进入 Free-Code Lab 隔离实验，再考虑是否沉淀进稳定 generator。

## 总数据流

先记住这条主线：

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
-> planner 规划成 ModSpec
-> reviewer / validator 审查规格
-> executor 调用 generator 落盘文件
-> auditor 检查生成结果
-> repair 在失败时修复 managed files
-> trace / replay 留下可复盘证据
```

## Day 1：跑通项目后证明了什么

我们用 mock provider 生成了：

```text
workspace/codex-learning-ruby
```

核心证据文件：

- `.agent/modspec.json`
- `.agent/generation-summary.json`
- `.agent/audit-report.json`
- `.agent/agent-run-replay.md`

理解：

- `modspec.json`：系统最终决定要生成什么，是真相源。
- `generation-summary.json`：generator 实际写出了哪些文件。
- `audit-report.json`：检查生成结果和规格、生成清单是否一致。
- `agent-run-replay.md`：只读历史运行证据，复盘 agent 各阶段。

这次 audit 结果：

```text
checks: 121
errors: 0
warnings: 0
```

Day 1 结论：

```text
一次 agent generate 不只是写文件，还会留下 ModSpec、生成摘要、审计报告和 replay 证据。
```

## Day 2：为什么 ModSpec 是真相源

`DomainSpec` 是领域规格抽象，表示未来可以支持不同领域。

当前 domain 状态：

```text
stable: minecraft.neoforge
planned: spring.api
planned: unity.component
```

`ModSpec` 是当前 NeoForge 领域真正稳定落地的规格。

源码里：

```text
src/neoforge_agent/models.py
```

定义了 `class ModSpec`，其中包含：

- `mod_id`
- `display_name`
- `package_name`
- `items`
- `blocks`
- `ores`
- `foods`
- `swords`
- `recipes`

`validator.py` 检查的不是用户自然语言说得好不好，而是结构化 `ModSpec` 能不能被 generator 安全、稳定地处理。

Day 2 结论：

```text
自然语言先变成 ModSpec，后面的 generator / audit / repair 都围绕 ModSpec 工作。
```

## Day 3：生成层不是 LLM 自由写代码

两个入口的区别：

```text
agent generate
= 自然语言 -> planner/mock or real LLM -> ModSpec -> generator -> workspace

generate-from-spec
= 已有 JSON ModSpec -> validator -> generator -> workspace
```

我们对比了：

```text
workspace/codex-learning-ruby
workspace/codex-spec-ruby
```

`codex-learning-ruby` 从自然语言开始，mock planner 规划出 item、block、ore、food、sword、recipes。

`codex-spec-ruby` 从 `examples/ruby_item.json` 开始，而这份 spec 只声明了一个 `ruby` item，所以生成内容明显更少。

关键源码：

- `project_generator.py`：总调度，创建 workspace，调用各类 generator。
- `code_generator.py`：生成 Java 注册代码，例如 `RubyMod.java`。
- `asset_generator.py`：生成资源 JSON、PNG、lang 等。

Day 3 结论：

```text
生成结果的丰富程度由输入 ModSpec 决定，不是 generator 临时发挥，也不是 LLM 裸写最终工程。
```

## Day 4：audit / build / repair 的区别

三层验证：

| 层 | 测什么 | 对象 |
| --- | --- | --- |
| `unittest` | Python 工具本身有没有坏 | `src/neoforge_agent/*.py` |
| `audit` | 生成 workspace 和 ModSpec 是否一致 | `workspace/<name>/` |
| `build` | 生成的 NeoForge 工程能不能编译 | 生成的 Mod 项目 |

repair-loop 不是让 LLM 随便改文件，而是：

```text
失败
-> 读取 audit/build 证据
-> 依赖 .agent/modspec.json
-> 在 managed files 范围内重新生成
-> 再 audit/build 验证
```

我们跑了故障注入 demo：

```text
delete_model
```

它故意删除了：

```text
src/main/resources/assets/ruby_mod/models/item/ruby.json
```

结果：

```text
initial audit: failed
initial errors: 2
repair RAG hits: 5
final audit: passed
```

Day 4 结论：

```text
audit 不能替代 build，build 不能替代 Minecraft runtime 测试，repair-loop 只能修 managed files 范围内的问题。
```

## Day 5：Agent 是固定阶段 workflow

这个项目不是多个 AI 自由聊天，而是固定阶段 workflow：

```text
planner
-> reviewer
-> executor
-> auditor
-> repair
-> trace / replay
```

源码骨架在：

```text
src/neoforge_agent/agent_runtime.py
```

`run_generate()` 按顺序调用：

- `plan_generate`
- `review`
- `execute_generate`
- `audit`
- `repair`
- `final_success`
- `trace_writer.write`

`AgentTraceWriter` 写出：

- `agent-run.json`
- `agent-run.md`
- `agent-decisions.md`
- `prompt-trace.json`
- `agent-trace-summary.json`
- `agent-trace-summary.md`

Day 5 结论：

```text
它更像 Plan-and-Execute 加验证闭环，不是开放式 ReAct，也不是多个自治 Agent 随意对话。
```

## Day 6：LLM / RAG / Tool 的边界

`mock LLM` 的价值：

```text
稳定、离线、可复现，用于学习、测试、CI、演示。
```

`real LLM` 的价值：

```text
验证真实模型规划能力，包括输出 JSON、schema 遵循、成本、延迟、失败率。
```

`fallback` 是备用路径或兜底方案。

```text
fallback 成功 != real LLM 成功
```

RAG 是本地知识库，主要辅助 planner 和 repair。它不替代 validator、audit、build。

tool manifest 是工具能力说明书，不是已经运行的 MCP server。

Day 6 结论：

```text
LLM 负责规划辅助，RAG 负责补充知识，最终正确性仍要靠 validator / audit / build / evidence。
```

## Day 7：Direct Code Lane 和 Free-Code Lab

Direct Code Lane 是为了解决 `ModSpec` 表达上限。

当前只支持：

```text
write_file
replace_text
```

它不支持：

- 自由 diff。
- 模糊替换。
- 删除文件。
- 移动文件。
- 大规模重构。
- 跨文件自动合并。
- AST 级 patch。

Direct Code Lane 会留下证据：

- `.agent/direct-code-plan.json`
- `.agent/direct-code-plan.md`
- `.agent/direct-code-review.json`
- `.agent/direct-code-diff.md`
- `.agent/direct-code-report.json`
- `.agent/direct-code-rollback-report.json`
- `.agent/direct-code-snapshots/`

Free-Code Lab 是隔离实验区。

它不是：

```text
实验成功 -> 自动改 generator 源码
```

而是：

```text
generate gap
-> lab 隔离实验
-> audit / build / manual runtime checklist
-> harvest candidate
-> 人工判断是否沉淀进 ModSpec / DSL / generator / audit / tests
```

Day 7 结论：

```text
Direct Code Lane 增强表达能力，但仍然受控；Free-Code Lab 负责探索，不自动进入稳定 generator。
```

## 常见误区

不要这样说：

```text
这个项目让 LLM 直接写完整 Mod。
```

更准确：

```text
LLM 主要产出结构化意图，最终文件主要由 deterministic generator 生成。
```

不要这样说：

```text
mock 跑通证明真实 LLM 没问题。
```

更准确：

```text
mock 证明工程链路稳定，real LLM 能力需要单独验证。
```

不要这样说：

```text
项目已经支持 Spring 和 Unity。
```

更准确：

```text
当前稳定 domain 只有 minecraft.neoforge，Spring 和 Unity 还是 planned registry entries。
```

不要这样说：

```text
Direct Code Lane 是通用 coding agent。
```

更准确：

```text
Direct Code Lane 只接受结构化 write_file / replace_text patch，并经过 review、snapshot、audit、build 和 rollback evidence。
```

## 当前印象最深的不足

本轮学习中印象最深的不足：

- 文档存在历史债务。
- 生成内容仍偏模板化。
- 真实 LLM 覆盖仍弱于 mock 基线。

还应该记住：

- Direct Code Lane 还是第一版，只支持简单 patch。
- audit/build 不等于真实 Minecraft runtime 测试。
- 稳定 domain 只有 `minecraft.neoforge`。

## 一分钟复述

这是一个面向 NeoForge Minecraft Mod 的受控代码生成 agent。它不是让 LLM 直接自由写完整工程，而是先把自然语言转成结构化 `ModSpec`，再由 deterministic generator 生成 Java、资源 JSON、PNG、配方、loot table 等文件。生成后通过 audit、build、repair、replay 留下可验证证据。mock LLM 用于稳定学习、测试、CI 和演示，real LLM 用于验证真实模型能力。RAG 给 planner 和 repair 提供本地知识，但不替代 validator、audit 和 build。Direct Code Lane 和 Free-Code Lab 用来处理 `ModSpec` 覆盖不了的需求，但都保持受控边界，所以项目不是无边界 coding agent。
