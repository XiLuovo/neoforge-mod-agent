# Current Capability Matrix

> 这是当前能力矩阵。当前公开展示以 RC1 基础闭环和 RC2 Agentic RAG 为准。

| 能力 | 状态 | 当前说明 |
| --- | --- | --- |
| ModSpec-first planning | stable | 用户目标先收敛为 intent contract 和 `ModSpec`。 |
| Deterministic generator | stable | 生成 Java、JSON、PNG、resources 和 `.agent` baseline evidence。 |
| Real tool-calling loop | stable | LLM 在 planner 之外选择 `retrieve_rag`、`read_file`、`search_files`、`apply_structured_patch`、`run_audit`、`run_build`、`finish`。 |
| Structured patch safety | stable | patch 受 path safety、snapshot、diff、report 和 rollback evidence 约束。 |
| Agentic RAG policy | stable | audit/build failure、unsupported request、NeoForge 规则不确定、reviewer evidence insufficient 和敏感 patch 会触发 `rag_required`；禁用 RAG 时仍记录 skipped decision。 |
| Multi-hop RAG retrieval | stable | `retrieve_rag` 保持原 action 名称，但支持 reason/query/limit/max_hops、query rewrite、follow-up query、hit 去重和 citation trace。 |
| RAG-assisted repair/refine | stable | planner、develop、repair 和 reviewer context 可引用本地 NeoForge 知识，patch 可关联 citation ids。 |
| LLM reviewer | stable | 审查覆盖、unsupported request、patch risk、recommended checks 和 evidence sufficiency；不替代 audit/build gate。 |
| Audit/build gate | stable | deterministic gate 是最终验收依据。 |
| Trace-backed benchmark | stable | `agent bench` 运行真实 agent 流程，并从真实 trace 汇总指标。 |
| RAG ablation benchmark | stable | `--rag-ablation` 对同一批 repair case 跑 `rag_on` / `rag_off` paired runs，输出 success、audit、iterations、tool calls 和 citation coverage delta。 |
| Replayable evidence | stable | `.agent` 中保留 planner、tool calls、RAG decisions、reviewer、audit/build、patch 和 rollback 证据。 |
| Direct Code Lane | auxiliary | 旧主线的受控 workspace patch 通道，可作为辅助/兼容能力讲解。 |
| Minecraft runtime harness | not automated | 仍需人工进游戏或未来 dedicated harness。 |

## 推荐演示能力

1. `agent develop` 生成 baseline 并进入真实 tool-calling refine loop。
2. `agent repair` 基于 audit/build observation、RAG、文件内容和 reviewer observation 修复 workspace。
3. `agent bench` 输出 trace-backed metrics，并链接每个 case 的 evidence。
4. `agent bench --rag-ablation` 对比 RAG on/off，展示 citation coverage 和 paired metrics。

## 能力边界

- 不说“通用 coding agent”。
- 不说“LLM 可以任意改项目代码”。
- 不说“reviewer 决定最终成功”。
- 不说“RAG 命中就证明修复正确”。
- 不说“自动完成 Minecraft runtime 验收”。
