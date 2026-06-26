# Agent与能力

这一层解释真实 agent 行为：planner 生成 ModSpec，tool-calling loop 读取 RAG 和文件并执行受控工具，LLM reviewer 审查风险，最终仍由 audit/build gate 验收。RC2 之后，RAG 还包含检索策略、query rewrite、多跳检索、citation trace 和 reviewer evidence sufficiency。

Decomposed Planner v1 属于 planner 层增强：自然语言先拆成 feature plan，再按 feature 类型生成小 JSON 并组合回 ModSpec；它不改变 generator/audit/build 的确定性边界，也不把 RAG/Milvus 作为当前主线。

> 这里放 workflow、Direct Code Lane、LLM、RAG 和工具契约。它们解释“系统怎么工作”。

## 推荐顺序

1. [agent-workflow.md](agent-workflow.md)
2. [tool-calling-contract.md](tool-calling-contract.md)
3. [rag.md](rag.md)
4. [repair-rag.md](repair-rag.md)
5. [agent-run-replay.md](agent-run-replay.md)
6. [direct-code-lane.md](direct-code-lane.md)
7. [agent-design-report-cn.md](agent-design-report-cn.md)
8. [llm-capability-layers-cn.md](llm-capability-layers-cn.md)
9. [rag-citation-chain.md](rag-citation-chain.md)
10. [rag-indexing-strategy-cn.md](rag-indexing-strategy-cn.md)
11. [real-vs-mock-llm-report.md](real-vs-mock-llm-report.md)
12. [real-llm-stability.md](real-llm-stability.md)
13. [real-llm-evidence-summary.md](real-llm-evidence-summary.md)
14. [real-llm-case-study.md](real-llm-case-study.md)
15. [llm-engineering-report.md](llm-engineering-report.md)

## 文档职责

- [agent-workflow.md](agent-workflow.md)：Agent 阶段真相源。
- [direct-code-lane.md](direct-code-lane.md)：受控补丁通道。
- [agent-design-report-cn.md](agent-design-report-cn.md)：设计取舍。
- [llm-capability-layers-cn.md](llm-capability-layers-cn.md)：LLM 能力分层。
- [tool-calling-contract.md](tool-calling-contract.md)：工具契约。
- [rag.md](rag.md)：本地 RAG 和 RC2 Agentic RAG。
- [repair-rag.md](repair-rag.md)：repair 中的 RAG。
- [real-vs-mock-llm-report.md](real-vs-mock-llm-report.md)：真实 LLM 和 mock 的边界。
- [real-llm-stability.md](real-llm-stability.md)：真实 provider 稳定性。
- [real-llm-evidence-summary.md](real-llm-evidence-summary.md)：真实 LLM 实验结果总览和项目讲解口径。
- [real-llm-case-study.md](real-llm-case-study.md)：真实 LLM 案例。
- [llm-engineering-report.md](llm-engineering-report.md)：LLM 工程报告。
- [agent-run-replay.md](agent-run-replay.md)：离线 replay。

## 继续阅读

- [../总览/README.md](../总览/README.md)
- [../验证与可靠性/README.md](../验证与可靠性/README.md)
