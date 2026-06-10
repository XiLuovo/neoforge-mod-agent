# RC1 学习与面试入口

这份文档面向项目作者复习、简历包装和面试讲解。它不替代架构文档，而是告诉你如何把 RC1 讲清楚。

## 这个项目现在是什么

NeoForge Mod Agent 现在是一个面向 Minecraft NeoForge 的受控 Coding Agent。用户用自然语言描述 Mod 目标后，系统先生成 ModSpec 和 baseline workspace，再让 LLM 在受控 tool-calling loop 中选择工具读取 RAG、查看文件、应用结构化 patch、运行 audit/build，最后由 LLM reviewer 给出风险审查，但最终成功仍由确定性 audit/build gate 决定。

它不是普通一次性生成器，也不是无限制通用 coding agent。它的核心价值是把 LLM 放进 NeoForge 领域约束、确定性生成器、安全 patch、审计证据和可回放 trace 里。

## 为什么适合作为实习简历主项目

- 有真实工程闭环：CLI、planner、generator、repair、reviewer、benchmark、docs 和 tests。
- 有清晰安全边界：LLM 不能自由写任意 diff，只能调用受控工具和结构化 patch。
- 有可演示证据链：每次 agent run 会生成 `.agent` trace、prompt、audit、reviewer、rollback 和 benchmark report。
- 有领域复杂度：Minecraft NeoForge 需要 Java、资源 JSON、数据包、模型、贴图、Gradle 和 audit/build 协同。
- 有可量化评测：`agent bench` 的指标来自真实 trace，而不是静态报告拼装。

## 一句话架构

Natural language -> ModSpec-first planner -> deterministic generator -> real tool-calling repair/refine loop -> LLM reviewer -> audit/build gate -> trace-backed benchmark -> replayable `.agent` evidence.

## 10 分钟讲解版本

1. 项目目标：把自然语言变成可审计的 NeoForge Mod workspace。
2. 关键约束：LLM 不是随便写项目，而是在 ModSpec、tool calling、structured patch 和 workspace safety boundary 内工作。
3. 基线生成：planner 先产出 ModSpec，deterministic generator 负责生成 Java、资源、数据包和报告。
4. 修复/完善：tool-calling loop 让 LLM 根据 observation 选择 `retrieve_rag`、`read_file`、`apply_structured_patch`、`run_audit`、`run_build`、`finish`。
5. 审查：LLMReviewer 检查目标覆盖、unsupported 内容、patch 风险和残余风险。
6. 验收：reviewer 不能覆盖 audit/build，最终 gate 仍是确定性的 audit/build。
7. 评测：agent bench 运行真实 develop/repair/reviewer/tool loop，并从 trace 统计成功率、工具调用、patch 接受率和 rollback。
8. 证据：`.agent` 目录能复盘 planner、tool calls、prompt、RAG、reviewer、audit/build 和 benchmark。

## 30 分钟代码走读路线

1. 从 [cli.py](../../src/neoforge_agent/cli.py) 看 `agent develop`、`agent repair`、`agent bench` 参数如何进入系统。
2. 读 [agent_orchestrator.py](../../src/neoforge_agent/agent_orchestrator.py)，理解 planner、generator、audit/build、tool loop、reviewer 和 trace writer 如何串起来。
3. 读 [tool_calling_agent.py](../../src/neoforge_agent/tool_calling_agent.py)，重点看工具 schema、iteration loop、observation、路径安全、snapshot 和 rollback evidence。
4. 读 [llm_reviewer.py](../../src/neoforge_agent/llm_reviewer.py)，理解 reviewer 的输入、结构化 JSON 输出和为什么它不能成为最终 gate。
5. 读 [benchmark_report.py](../../src/neoforge_agent/benchmark_report.py)，看 benchmark case 如何跑真实 agent 行为并从 trace 统计指标。
6. 读 [llm_client.py](../../src/neoforge_agent/llm_client.py)，看 mock / OpenAI-compatible provider 如何统一成 `complete_json()`。
7. 读 [agent_runtime.py](../../src/neoforge_agent/agent_runtime.py)，理解 trace、prompt、payload 和 evidence 写入的通用模型。

## 必须掌握的核心文件

- [src/neoforge_agent/cli.py](../../src/neoforge_agent/cli.py)
- [src/neoforge_agent/agent_orchestrator.py](../../src/neoforge_agent/agent_orchestrator.py)
- [src/neoforge_agent/tool_calling_agent.py](../../src/neoforge_agent/tool_calling_agent.py)
- [src/neoforge_agent/llm_reviewer.py](../../src/neoforge_agent/llm_reviewer.py)
- [src/neoforge_agent/benchmark_report.py](../../src/neoforge_agent/benchmark_report.py)
- [src/neoforge_agent/llm_client.py](../../src/neoforge_agent/llm_client.py)
- [src/neoforge_agent/agent_runtime.py](../../src/neoforge_agent/agent_runtime.py)

## 必须能解释的问题

- 为什么不是普通生成器？
  因为 RC1 不只生成 baseline，还会让 LLM 根据真实 observation 调工具、读文件、检索 RAG、应用结构化 patch、复跑 audit/build，并写可回放 evidence。

- 为什么不让 LLM 直接写整个 Mod？
  NeoForge workspace 涉及 Java、资源、数据包、Gradle 和版本约束。自由 diff 风险高、难审计、难回滚；受控工具和结构化 patch 更容易验证。

- ModSpec-first 的价值是什么？
  它把自然语言先收敛成领域结构，让 deterministic generator 成为主路径，降低 LLM 幻觉对文件系统的直接影响。

- tool-calling loop 怎么工作？
  每轮 LLM 读取上一轮 observation，输出一个结构化 action；系统执行工具，把 observation 放回下一轮，直到 `finish` 或达到 `max_iterations`。

- structured patch 为什么安全？
  patch 只能写 workspace 内允许路径，写前会 snapshot，写后会生成 patch report 和 rollback evidence，不能自由操作任意文件。

- reviewer 为什么不能替代 audit/build？
  reviewer 是 LLM 风险审查，适合发现覆盖和残余风险；audit/build 是确定性 gate，不能被 reviewer approve 绕过。

- benchmark 为什么要读真实 trace？
  因为 `avg_tool_calls`、`avg_iterations`、`patch_accept_rate` 和 rollback count 只有来自真实 agent run 才能反映行为质量。

## 建议 demo 命令

PowerShell：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)

py -3.11 -m agent.cli agent develop "Create a ruby mod with ruby ore, ruby item and recipes." --planner llm --llm-provider mock --workspace-name rc1-demo --no-build --json

py -3.11 -m agent.cli agent repair rc1-demo --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json

py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

演示时重点打开 workspace 的 `.agent` 目录，展示 `agent-run.json`、`tool-call-trace.json`、`prompt-trace.json`、`repair-rag-context.json`、`reviewer-report.json`、`audit-report.json`、`structured-patch-rollback-report.json` 和 benchmark report。

## 简历 bullet 示例

- Built a controlled NeoForge Minecraft Mod Coding Agent that turns natural language goals into audited ModSpec-first workspaces with deterministic generation and trace-backed evidence.
- Implemented a real LLM tool-calling repair/refine loop with RAG retrieval, safe file reads, structured patch execution, audit/build observations, snapshots and rollback reports.
- Added an LLM reviewer and benchmark runner that evaluate coverage, patch risk, gate results and real trace metrics such as tool calls, iterations and patch acceptance rate.

## 面试讲解话术

“这个项目一开始像一个 Minecraft Mod 生成器，但 RC1 后我把它收束成了领域 Coding Agent。LLM 不直接无边界改文件，而是先通过 ModSpec-first 生成 baseline，再在 repair/refine loop 中按结构化 tool action 工作。每个 patch 都限制在 workspace 内并写 snapshot 和 rollback evidence。Reviewer 会做需求覆盖和风险审查，但最后是否成功仍由 deterministic audit/build gate 决定。为了证明 agent 行为真实，我让 benchmark 直接跑 develop/repair/reviewer/tool loop，并从 `.agent` trace 统计指标。”

## 项目边界和不足

- 当前稳定 domain 是 `minecraft.neoforge`，不是通用软件工程 agent。
- mock LLM 适合 CI 和本地演示，真实 provider 仍需要成本、稳定性和 prompt 预算管理。
- audit/build 能发现静态和构建问题，但不能替代真实 Minecraft runtime 自动化测试。
- ModSpec 和 DSL 覆盖面仍有限，复杂玩法仍需要后续领域能力沉淀。
- Reviewer 是辅助审查，不是安全或正确性的最终来源。

## 继续阅读

- [../Agent与能力/tool-calling-contract.md](../Agent与能力/tool-calling-contract.md)
- [../验证与可靠性/benchmark-report.md](../验证与可靠性/benchmark-report.md)
- [../发布与展示/agent-rc1-showcase.md](../发布与展示/agent-rc1-showcase.md)
