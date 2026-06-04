## V2.4 NeoForge Knowledge Base / RAG

目标：为 LLM planner 增加一个本地、可审计、确定性的 NeoForge 知识检索层，让模型在生成 ModSpec 前能看到项目内已验证的约束和路径规则。

完成内容：

- 新增 `knowledge_base.py`。
- 新增 CLI 命令：
  - `knowledge query <query>`
- 内置 NeoForge 知识条目覆盖：
  - ModSpec 边界
  - NeoForge deferred register
  - assets / models / textures 路径
  - 程序化材质
  - texture audit
  - right click item behavior
  - food effects
  - sword ignite
  - recipes / loot tables / tags
  - overworld ore worldgen
  - pack.mcmeta
  - unsupported boundaries
- `knowledge query` 写出：
  - `workspace/knowledge-runs/<run-id>/.agent/rag-query.json`
  - `workspace/knowledge-runs/<run-id>/.agent/rag-query.md`
- `plan_with_llm` 和 `plan_modification_with_llm` 自动检索 RAG context，并注入 system prompt。
- LLM planner artifacts 写出：
  - `.agent/rag-context.json`
  - `.agent/rag-context.md`
- Agent prompt trace 增加：
  - `rag_query`
  - `rag_hits`
- capability matrix 增加：
  - `knowledge_query`
  - `rag_planner_context`
- package metadata 更新到 `2.4.0`。

价值：

- LLM 不再只依赖一个静态大 prompt，而是获得与请求相关的本地知识片段。
- RAG 检索结果可复现、可审计，适合简历和面试讲解。
- 继续保持核心边界：RAG 只辅助生成 ModSpec，不允许 LLM 直接生成 Java/JSON/PNG。
