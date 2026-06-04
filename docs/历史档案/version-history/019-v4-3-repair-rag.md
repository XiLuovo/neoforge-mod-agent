## V4.3 Repair RAG 可视化增强

目标：把 V4.2 的 repair RAG 上下文从“藏在 JSON/MD artifact 里”升级成可展示、可回放、可讲述的证据链，方便解释 Agent 为什么选择某个修复动作。

完成内容：

- Dashboard 的 `Self-Healing Repair` 区域新增：
  - repair RAG query
  - repair RAG hit count
  - 命中的 knowledge id
  - root cause / repair action / knowledge 的确定性映射卡片
- `replay` 新增 `repair_rag` 回放事件。
- replay metrics 新增：
  - `repair_rag_events_count`
  - `repair_rag_hits_count`
- Web Demo 的 Self-Healing 页新增：
  - `Repair RAG` 摘要
  - RAG query
  - categories / capabilities
  - RAG hit 列表
  - root cause -> action -> knowledge 映射
- Capability Matrix 新增：
  - `dashboard_repair_rag`
  - `web_demo_repair_rag`
  - `replay_repair_rag`
- package metadata 更新到 `4.3.0`。

边界：

- 这版只增强可视化和回放，不改变 safe repair loop 的执行策略。
- RAG 仍然只提供证据和解释，不自动应用补丁。
- LLM 仍然不能直接写 Java / JSON / PNG / Gradle。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest tests.test_replay tests.test_web_demo tests.test_dashboard tests.test_capabilities -v
py -3.11 -m agent.cli dashboard --run-name v43-dashboard --json
py -3.11 -m agent.cli web-demo --smoke --json
```
