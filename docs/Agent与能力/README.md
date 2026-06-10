# Agent与能力

RC1 主线中，这一层解释真实 agent 行为：planner 生成 ModSpec，tool-calling loop 读取 RAG 和文件并执行受控工具，LLM reviewer 审查风险，最终仍由 audit/build gate 验收。

> 这里放 workflow、Direct Code Lane、LLM、RAG 和工具契约。它们解释“系统怎么工作”。

## 推荐顺序

1. [agent-workflow.md](agent-workflow.md)
2. [tool-calling-contract.md](tool-calling-contract.md)
3. [repair-rag.md](repair-rag.md)
4. [agent-run-replay.md](agent-run-replay.md)
5. [direct-code-lane.md](direct-code-lane.md)
6. [capability-harvest-loop.md](capability-harvest-loop.md)
7. [agent-design-report-cn.md](agent-design-report-cn.md)
8. [llm-capability-layers-cn.md](llm-capability-layers-cn.md)
9. [rag.md](rag.md)
10. [rag-citation-chain.md](rag-citation-chain.md)
11. [rag-indexing-strategy-cn.md](rag-indexing-strategy-cn.md)
12. [real-vs-mock-llm-report.md](real-vs-mock-llm-report.md)
13. [real-llm-stability.md](real-llm-stability.md)
14. [real-llm-evidence-summary.md](real-llm-evidence-summary.md)
15. [real-llm-case-study.md](real-llm-case-study.md)
16. [llm-engineering-report.md](llm-engineering-report.md)

## 文档职责

- [agent-workflow.md](agent-workflow.md)：Agent 阶段真相源。
- [direct-code-lane.md](direct-code-lane.md)：受控补丁通道。
- [capability-harvest-loop.md](capability-harvest-loop.md)：实验采集闭环。
- [agent-design-report-cn.md](agent-design-report-cn.md)：设计取舍。
- [llm-capability-layers-cn.md](llm-capability-layers-cn.md)：LLM 能力分层。
- [tool-calling-contract.md](tool-calling-contract.md)：工具契约。
- [rag.md](rag.md)：本地 RAG。
- [repair-rag.md](repair-rag.md)：repair 中的 RAG。
- [real-vs-mock-llm-report.md](real-vs-mock-llm-report.md)：真实 LLM 和 mock 的边界。
- [real-llm-stability.md](real-llm-stability.md)：真实 provider 稳定性。
- [real-llm-evidence-summary.md](real-llm-evidence-summary.md)：真实 LLM 实验结果总览和面试说法。
- [real-llm-case-study.md](real-llm-case-study.md)：真实 LLM 案例。
- [llm-engineering-report.md](llm-engineering-report.md)：LLM 工程报告。
- [agent-run-replay.md](agent-run-replay.md)：离线 replay。

## 继续阅读

- [../总览/README.md](../总览/README.md)
- [../验证与可靠性/README.md](../验证与可靠性/README.md)
