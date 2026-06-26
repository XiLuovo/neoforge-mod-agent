# Agent Rules

本文件承接根目录 `AGENTS.md` 的详细架构规则。根文件只保留高优先级约束；需要深入理解项目时阅读本文件。

## 项目价值

本项目的核心价值不是“接了一个大模型 API”，而是展示一个可解释、可复现、可验证的领域 Agent 工程：

- 自然语言需求先进入规划与规格化流程。
- 以 `ModSpec-first`、确定性 generator、受控 patch、audit/build gate 为主线。
- 通过 trace、report、benchmark、showcase 和测试产物证明能力。
- RAG、repair、reviewer、decomposed planner 等能力服务于主线，不能取代主线。

任何改动都应提升项目的工程展示质量：更清晰的工程边界、更可靠的自动化验证、更好的可展示成果、更容易讲清楚的技术取舍。

## 当前主线

优先维护和增强下面这条架构主线：

```text
Natural language
-> planner / feature plan / ModSpec
-> deterministic generator baseline
-> Java / JSON / resource artifacts
-> real tool-calling repair/refine loop
-> Agentic RAG policy / read_file / search_files when needed
-> structured patch with citation or file evidence
-> LLM reviewer coverage/risk/evidence check
-> audit/build gate
-> trace-backed eval / showcase report
-> replayable evidence
```

公开展示时，当前推荐主线仍应先讲 development e2e showcase / eval，再把 RAG ablation、18-case repair suite 和 seeded holdout 作为可靠性补充。

## 核心代码地图

- `src/agent/cli.py`：兼容入口，转发到 `neoforge_agent.cli`。
- `src/neoforge_agent/cli.py`：所有 CLI 参数和命令分发入口。
- `src/neoforge_agent/agent_orchestrator.py`：把 planner、reviewer、generator、audit/build、repair 和 trace 串起来。
- `src/neoforge_agent/agent_runtime.py`：领域无关的 agent stage 骨架和 `.agent` evidence writer。
- `src/neoforge_agent/tool_calling_agent.py`：真实 tool-calling loop、structured patch、路径安全、snapshot 和 rollback evidence。
- `src/neoforge_agent/agentic_rag.py`：RAG policy、query rewrite、多跳检索、citation trace 和 RAG ablation 所需决策记录。
- `src/neoforge_agent/llm_reviewer.py`：需求覆盖、风险和 evidence sufficiency 审查；不能覆盖 audit/build gate。
- `src/neoforge_agent/models.py`、`schema.py`、`domain_spec.py`：ModSpec / DomainSpec 数据契约。
- `src/neoforge_agent/project_generator.py`、`code_generator.py` 和各类 `*_generator.py`：确定性生成核心。
- `src/neoforge_agent/auditor.py`、`builder.py`、`quality_gate.py`：确定性验证层。
- `src/neoforge_agent/benchmark_report.py`、`evaluator.py`、`repair_eval.py`：评测、benchmark 和可展示指标。
- `templates/neoforge-26.1/`：生成 workspace 的 NeoForge 模板。
- `examples/`：稳定示例和 benchmark case。
- `tests/`：回归、安全边界、文档链接、CLI 和 agent 行为测试。

新增能力要放回这张地图中，而不是随手新建平行体系。

## 源码、生成产物与实验边界

长期维护的项目资产主要是 `src/`、`tests/`、`examples/`、`docs/`、`templates/`、`scripts/`、`.github/workflows/` 和根目录项目说明。

`workspace/`、`dist/`、`.tmp/`、`.gradle-user-home/` 是生成产物、临时运行目录或发布产物目录，默认不应作为源码长期编辑或提交。需要演示 evidence 时，优先用唯一的 workspace/run 名生成；不要随意 `--overwrite` 旧 evidence，除非用户明确要重建。

`.env`、`.env.local` 和其它密钥文件不能写入文档、测试或 trace；需要说明配置时只改 `.env.example` 或文档中的占位示例。

Direct Code Lane 是辅助或实验通道。它可以帮助处理少量 ModSpec 暂时无法表达的 workspace patch，但成功模式必须沉淀为 `ModSpec` / DSL / generator / audit / tests 后，才能成为稳定能力。

## RAG 与 Agentic 能力边界

RAG 是 planner / repair / reviewer 的上下文增强和证据补充，不是项目主线。

允许：

- 增加 RAG 检索、引用、trace、ablation、benchmark 或配置能力。
- 让 RAG 帮助 planner / repair 做更可靠的决策。
- 把 RAG 作为可选能力、可关闭能力或评测维度。
- 在文档中说明 RAG 的作用、限制和实验结果。

不允许，除非用户明确要求：

- 将默认流程改成“所有能力都围绕 RAG 运转”。
- 用 RAG 替代 `ModSpec-first`、generator、audit、build 或测试。
- 为了 RAG 引入重型服务端架构作为默认依赖。
- 把 README 或文档叙述改成“RAG 项目”。
- 因为新增 RAG 功能而重写核心 agent 生命周期。

判断标准：如果一个改动会让别人第一眼觉得“这是一个 RAG 系统”，而不是“这是一个 Minecraft Mod 领域受控 Coding Agent”，就需要暂停并向用户确认。

## Tool-Calling 与 Patch 安全边界

LLM 只能通过受控 action 参与 workspace 修复或完善。当前允许的核心工具语义是 `retrieve_rag`、`read_file`、`search_files`、`regenerate_managed_files`、`apply_structured_patch`、`run_audit`、`run_build` 和 `finish`。

必须保持：

- `.agent/tool-call-trace.json` 来自真实工具 action，而不是事后编造的 step 摘要。
- `apply_structured_patch` 只接受结构化 JSON patch，不接受自由 diff。
- patch 路径必须限制在 generated workspace 的允许根目录内。
- patch 前保留 snapshot，patch 后写 structured patch report 和 rollback report。
- reviewer 可以要求继续修复或更多证据，但不能把失败的 audit/build 改成成功。
- real provider 的连接、鉴权、SSL、限流或 HTTP 错误要归类为 provider error，不能说成 agent repair logic failure。

## 工程展示价值优先级

做功能时按下面顺序取舍：

1. 可验证性：是否有测试、audit、benchmark、trace 或可复现命令。
2. 可解释性：是否能讲清楚为什么这样设计，以及它解决了什么失败模式。
3. 领域性：是否体现 Minecraft / NeoForge / Mod 生成与修复的专业边界。
4. 工程性：是否有清晰模块、配置、错误处理、日志和文档。
5. 展示性：是否能沉淀为 README、showcase、报告、截图或项目摘要。

不要为了“看起来很 AI”而牺牲稳定性和可讲性。项目最重要的是能被追问、能解释、能复现。
