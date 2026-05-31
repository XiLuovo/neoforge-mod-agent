# NeoForge Mod Agent 文档索引

> 文档定位：这是 `docs/` 的总入口。它只负责告诉你先读什么、哪里查细节；架构和机制细节不要在这里展开。

## 只读 4 篇

如果目标是自己学懂项目，按这个顺序读：

1. [project-limitations.md](project-limitations.md)：当前边界、不足和后续方向。
2. [architecture.md](architecture.md)：整体架构和数据流。
3. [agent-workflow.md](agent-workflow.md)：agent runtime 阶段、角色和证据文件。
4. [readme-glossary-cn.md](readme-glossary-cn.md)：术语词典，不懂再查。

Direct Code Lane 机制见 [direct-code-lane.md](direct-code-lane.md)，Capability Harvest Loop / Free-Code Lab 机制见 [capability-harvest-loop.md](capability-harvest-loop.md)。

## 文档职责表

| 分层 | 文档 | 什么时候看 |
| --- | --- | --- |
| 项目边界 | [project-limitations.md](project-limitations.md) | 确认项目能做什么、不能做什么。 |
| 学习补充 | [learning-notes/engineering-basics-cn.md](learning-notes/engineering-basics-cn.md) | 查 fallback、工程稳定性、可复现、CI 等基础概念。 |
| 学习补充 | [learning-notes/project-first-pass-cn.md](learning-notes/project-first-pass-cn.md) | 第一遍学完后的整体复盘笔记。 |
| 术语入口 | [readme-glossary-cn.md](readme-glossary-cn.md) | 查 `ModSpec`、RAG、Direct Code Lane 等词。 |
| 架构真相源 | [architecture.md](architecture.md) | 查整体分层、数据流和 domain plugin 边界。 |
| Agent 真相源 | [agent-workflow.md](agent-workflow.md) | 查 planner/reviewer/executor/auditor/repair/replay。 |
| 机制真相源 | [direct-code-lane.md](direct-code-lane.md) | 查结构化代码补丁、review、snapshot、rollback。 |
| 机制真相源 | [capability-harvest-loop.md](capability-harvest-loop.md) | 查 Free-Code Lab、manual checklist、harvest candidate。 |
| 规格/生成 | [domain-spec.md](domain-spec.md), [modspec.md](modspec.md), DSL 文档 | 查规格层和 generator 输入。 |
| 验证/报告 | testing、repair、eval、benchmark、replay、dashboard 文档 | 查如何证明结果可验证、可复盘。 |
| 发布/展示 | showcase、demo、发布说明、历史材料 | 学懂后再看外部叙事和演示材料。 |
| 历史查证 | [version-history.md](version-history.md), [test-matrix.md](test-matrix.md) | 查版本演进或测试覆盖，不建议从头读。 |

## 规格与生成

- [domain-spec.md](domain-spec.md)：DomainSpec 抽象和 planned domain registry。
- [modspec.md](modspec.md)：NeoForge `ModSpec` 参考。
- [behavior-dsl.md](behavior-dsl.md)：事件-条件-动作行为 DSL。
- [machine-dsl.md](machine-dsl.md)：机器方块 / BlockEntity / GUI 模板。
- [entity-dsl.md](entity-dsl.md)：实体和 mob 模板。
- [progression-dsl.md](progression-dsl.md)：玩法线和阶段组织。
- [quest-guide-dsl.md](quest-guide-dsl.md)：任务、advancement 和指南结构。
- [world-structure-dsl.md](world-structure-dsl.md)：world / structure 资源生成。
- [controlled-java-extension.md](controlled-java-extension.md)：受控 Java extension。
- [balance-planner.md](balance-planner.md)：平衡规划。
- [textures.md](textures.md)：程序化贴图。
- [resource-quality-upgrade.md](resource-quality-upgrade.md)：资源质量和预览升级。

## Agent / LLM / RAG / Tool

- [agent-design-report-cn.md](agent-design-report-cn.md)：Agent 设计取舍，适合学完 workflow 后补充。
- [agent-run-replay.md](agent-run-replay.md)：离线 replay viewer。
- [real-vs-mock-llm-report.md](real-vs-mock-llm-report.md)：mock 与真实 LLM 的边界。
- [real-llm-stability.md](real-llm-stability.md)：真实 provider 稳定性。
- [llm-engineering-report.md](llm-engineering-report.md)：prompt/provider/retry/usage 报告。
- [llm-capability-layers-cn.md](llm-capability-layers-cn.md)：LLM 能力分层说明。
- [rag.md](rag.md)：本地 NeoForge 知识库。
- [repair-rag.md](repair-rag.md)：repair 中的 RAG advisor。
- [rag-citation-chain.md](rag-citation-chain.md)：RAG 引用链。
- [rag-indexing-strategy-cn.md](rag-indexing-strategy-cn.md)：RAG chunk 和索引策略。
- [tool-calling-contract.md](tool-calling-contract.md)：工具契约，不等于已经实现 MCP server。

## 验证、修复与报告

- [testing.md](testing.md)：自动化测试入口。
- [test-matrix.md](test-matrix.md)：测试覆盖查证。
- [doctor.md](doctor.md)：环境诊断。
- [quality-gate.md](quality-gate.md)：质量门禁。
- [failure-lab.md](failure-lab.md)：故障注入。
- [failure-repair-demo.md](failure-repair-demo.md)：失败 -> audit -> repair 演示。
- [repair-loop.md](repair-loop.md)：受控修复循环。
- [repair-eval.md](repair-eval.md)：自修复量化。
- [golden-tests.md](golden-tests.md)：黄金快照测试。
- [ci.md](ci.md)：CI / GitHub Actions。
- [eval.md](eval.md)：评测和 benchmark 基础。
- [benchmark-report.md](benchmark-report.md)：benchmark 页面。
- [evidence-chain-report.md](evidence-chain-report.md)：证据链报告。
- [dashboard.md](dashboard.md)：Web Demo / dashboard。
- [showcase.md](showcase.md)：showcase 报告。

## 发布与展示

这些不是主学习入口。先学懂项目，再按需要查：

- [demo-cases.md](demo-cases.md)：典型 demo case。
- [screenshots.md](screenshots.md)：截图清单。
- [public-release-checklist.md](public-release-checklist.md)：公开发布检查。

## 历史和旧学习材料

- [version-history.md](version-history.md)：历史版本查证，不用从头读。
- [project-evaluation-deep-dive-cn.md](project-evaluation-deep-dive-cn.md)：深度评价补充，适合学完主线后看。
