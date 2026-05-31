# RAG 引用链 / Explainable RAG Citations

> 文档定位：这是 RAG 引用链专项材料，不是主学习入口。需要追踪 planner / repair 引用了哪些知识条目时再读。

V4.6 的目标是让 RAG 不只是“参与过”，而是能解释清楚每个关键决策用了哪些知识条目。

## 覆盖范围

- planner decision：记录规划 ModSpec 或 patch 时引用的知识条目。
- repair decision：记录 repair RAG 为修复决策命中的知识条目。
- agent decision artifact：在 `.agent/agent-run.json` 和 `.agent/agent-decisions.md` 中展示 knowledge id。
- dashboard：在静态 dashboard 中展示 `RAG Citation Chain`，把 decision 和 knowledge id 连接起来。

## 决策字段

`agent-run.json` 的 `decisions[]` 现在包含：

```json
{
  "knowledge_ids": ["behavior.right_click_item"],
  "knowledge_refs": [
    {
      "id": "behavior.right_click_item",
      "title": "Right click item behavior",
      "category": "behavior",
      "capability": "right_click_behavior",
      "score": 120,
      "source": "bundled:v2.4",
      "reason": "Planner retrieved this knowledge before producing the ModSpec decision."
    }
  ]
}
```

## 快速验证

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent generate "做一个红宝石模组，添加红宝石护符，右键回复4点生命值，冷却20秒。" --planner llm --llm-provider mock --workspace-name v46-rag-citations --overwrite --json
py -3.11 -m agent.cli dashboard --run-name v46-dashboard --json
```

检查：

- `.agent/agent-run.json` 的 planner decision 有 `knowledge_ids`。
- `.agent/agent-decisions.md` 显示 `knowledge ids`。
- dashboard HTML 包含 `RAG Citation Chain`。
- `dashboard-data.json` 包含 `rag_reference_chains`。

## 边界

RAG 引用链只提供解释和证据。它不会让 LLM 直接生成 Java、JSON、PNG 或 Gradle 文件；代码和资源仍由确定性 generator 输出。
