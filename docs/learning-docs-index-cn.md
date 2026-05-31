# 学习文档分类索引

> 文档定位：这是学习资料的轻量索引，不是主学习路线。主路线只看 [project-learning-plan-cn.md](project-learning-plan-cn.md)。

## 最短路线

```text
README.md
-> docs/README.md
-> project-learning-plan-cn.md
-> project-limitations.md
-> architecture.md / agent-workflow.md
-> direct-code-lane.md / capability-harvest-loop.md
```

## 必读

1. [project-learning-plan-cn.md](project-learning-plan-cn.md)：7 天学习主线。
2. [project-limitations.md](project-limitations.md)：项目边界、不足和后续路线。
3. [architecture.md](architecture.md)：整体架构、数据流和 domain plugin。
4. [agent-workflow.md](agent-workflow.md)：agent runtime 的阶段、角色和证据。
5. [readme-glossary-cn.md](readme-glossary-cn.md)：术语词典。

## 按主题查

| 主题 | 先看 | 再查 |
| --- | --- | --- |
| 规格层 | [domain-spec.md](domain-spec.md) | [modspec.md](modspec.md) |
| 生成层 | [modspec.md](modspec.md) | behavior / machine / entity / progression / quest / world DSL 文档 |
| Direct Code Lane | [direct-code-lane.md](direct-code-lane.md) | [controlled-java-extension.md](controlled-java-extension.md) |
| Capability Harvest Loop | [capability-harvest-loop.md](capability-harvest-loop.md) | [project-limitations.md](project-limitations.md) |
| Agent workflow | [agent-workflow.md](agent-workflow.md) | [agent-design-report-cn.md](agent-design-report-cn.md), [agent-run-replay.md](agent-run-replay.md) |
| LLM / RAG / Tool | [llm-engineering-report.md](llm-engineering-report.md) | real-vs-mock、real-llm-stability、rag、tool-calling-contract |
| 验证和修复 | [testing.md](testing.md) | audit/build/repair/eval/quality/failure 相关文档 |
| 展示和面试 | [interview-script.md](interview-script.md) | resume、portfolio、demo、xiaolin 系列 |
| 历史查证 | [version-history.md](version-history.md) | [test-matrix.md](test-matrix.md) |

## 学完后要能回答

- 从一句自然语言到生成 workspace，中间经过哪些阶段？
- `.agent/` 目录里的主要证据文件分别证明什么？
- 为什么 `ModSpec-first` 比 LLM 直接写完整 Mod 更稳定？
- Direct Code Lane 为什么不是无边界 Coding Agent？
- Free-Code Lab 如何把 generate gap 转成可沉淀的能力候选？
- 项目当前最大的不足是什么，失败时先看哪些报告？

## 口径提示

- 当前主架构是 `ModSpec-first + Direct Code Lane`。
- 后续升级主线是 `Capability Harvest Loop`。
- `minecraft.neoforge` 是唯一稳定 domain，其他 domain 仍是 planned。
- `tool manifest` 是工具契约基础，不是已运行的 MCP server。
- `mock` LLM 用于稳定学习和回归，不代表真实 LLM 成功。
- `audit` / `build` 不能替代 Minecraft runtime 测试。
