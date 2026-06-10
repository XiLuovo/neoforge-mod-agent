# RAG Indexing Strategy

RC1 的 RAG index 服务 NeoForge 领域 agent，不追求泛化到全部代码知识。

## 索引内容

- NeoForge registry / data pack / resource 规则；
- 常见 item、block、ore、recipe、worldgen、entity、machine 模式；
- audit/build 常见失败原因；
- structured patch 安全边界；
- 项目能力和限制说明。

## 索引原则

- 每条知识应能被 citation；
- 知识粒度要小，便于 tool loop 精准引用；
- 不把旧版本宣传口径放进当前主知识；
- runtime 不确定内容标记为 limitation，而不是规则。

## 使用场景

- planner 生成 `ModSpec`；
- repair/refine 选择下一步工具；
- reviewer 判断 unsupported request；
- benchmark 统计 RAG 命中率。

## 维护边界

RAG index 不是联网文档同步器。NeoForge API 变化、Minecraft 版本变化和复杂 runtime 行为仍需要人工维护知识库。
