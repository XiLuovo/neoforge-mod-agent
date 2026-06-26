# 架构候选状态

本文用于同步架构扫描后的候选状态，避免继续按旧报告惯性拆任务。当前架构真相源仍是 `architecture.md`、`agent-workflow.md`、`agent-rules.md` 和 ADR；本文只记录候选队列、处理状态和推荐下一步。

## 当前主线

项目主线保持不变：

```text
Natural language
-> ModSpec-first planner
-> deterministic generator
-> real tool-calling repair/refine loop
-> structured patch + evidence
-> LLM reviewer
-> audit/build gate
-> trace-backed showcase / benchmark
-> replayable .agent evidence
```

RAG、reviewer、repair、decomposed planner 和 Direct Code Lane 都服务于这条主线，不能替代它。公开叙事应继续强调 `minecraft.neoforge` 受控 Coding Agent，而不是通用 RAG、聊天机器人或无限制自由 Coding Agent。

## 已处理候选

| 候选 | 当前结果 |
| --- | --- |
| ModSpec Feature Catalog | 已完成。Feature kind catalog 已命名，保持 ModSpec JSON shape 不变。见 `docs/adr/0001-adopt-feature-kind-catalog-without-changing-modspec-shape.md`。 |
| Planner Normalization | 已完成。`PlannerResolution` 已覆盖 generate/develop、CLI prompt resolve、modify planning。见 `docs/adr/0002-name-generate-planner-resolution.md`。 |
| Workspace Materializer | 已完成。workspace materialization 与 managed-file cleanup 已有独立模块和测试入口；`workspace/` 仍只作为生成产物和 evidence 区。 |
| Evidence Writer | 已完成。agent/planner/repair/reviewer/patch evidence 写入边界已收口，报告口径改为 trace-backed evidence。 |
| Agent Runtime Boundary | 已完成。NeoForge runtime plugin ports 与 workflow ports 已拆开，旧 runtime port 模块保留兼容 re-export。 |
| LLM Output Normalization | 已完成。`LLMNormalizationResult` 已命名；decomposed planner 通过 `DECOMPOSED_PLANNER_NORMALIZATION` 门面依赖 normalizer。见 `docs/adr/0003-name-llm-normalization-result.md`。 |
| Benchmark / Evidence Scope | 已完成。benchmark 与 evidence-chain 报告已写入 evidence boundary，避免把 workspace audit/build 写成 Minecraft runtime 自动验收。 |
| Direct Code Lane Boundary | 已完成。capability matrix、tool manifest、Web Demo 首屏已把 Direct Code Lane 收回为 experimental opt-in，而不是推荐主线。 |
| 公开文档编码清理 | 已完成。公开 benchmark、evidence-chain、showcase 与 runtime manual validation 文档已清理为可读口径。 |
| Current Architecture 真相源重写 | 已完成。`docs/总览/architecture.md` 已重写为可读中文版架构入口。 |
| Capability / Tool Manifest 口径一致性 | 已完成。新增 contract 测试，锁定 stable / experimental / auxiliary 与 runtime evidence 边界。 |
| Runtime Evidence 分层 | 已完成。新增 `manual-runtime-evidence/v1` schema，benchmark、evidence-chain 和 real-llm-stability 共用同一 runtime evidence loader。 |
| Free-Code Lab 公开表面移除 | 已完成。README、架构入口、能力矩阵、tool manifest、Agent 文档索引和 Web Demo 首屏不再推荐 Free-Code Lab / harvest。源码和兼容 CLI 暂时保留为 legacy。 |

## 剩余候选

| 优先级 | 候选 | 为什么还值得做 | 建议范围 |
| --- | --- | --- | --- |
| P2 | Free-Code Lab legacy 源码/CLI 去留评估 | 公开表面已收口，但 `free_code_lab.py`、`agent lab-generate`、`harvest-report` 和相关测试仍保留为兼容代码。是否删除会影响 CLI、历史 evidence 和测试面。 | 单独评估依赖后再决定：保留为 hidden legacy，或分阶段删除 CLI、runner、测试和 Web Demo harvest summary。 |

## 暂不继续拆的方向

- 不继续拆 Agent Runtime Boundary 的细碎 phase，除非出现真实依赖回流或测试痛点。
- 不把 Direct Code Lane 做成更强的自由 coding agent；它只保留为 experimental opt-in 和受控 workspace patch evidence。
- 不把 RAG、reviewer、benchmark 或 runtime evidence 提升为主线替代品；它们继续作为可靠性、上下文和证据增强。
- 不把 Free-Code Lab 的 harvest 流程继续强化为新主线；如果保留，也只能作为 legacy/internal 历史能力。

## 推荐下一步

下一步不建议马上大删源码。更稳的是先跑一轮 Free-Code Lab legacy 依赖审计，确认 `agent lab-generate`、`harvest-report`、Web Demo harvest summary 和 `tests/test_free_code_lab.py` 是否还有保留价值，再决定是否分阶段删除。
