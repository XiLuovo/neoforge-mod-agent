## V4.2 更强 RAG + Repair 联动

目标：让 `repair_agent` 在 audit/build 失败时，不只给出 root causes 和 safe repair loop，还能自动检索本地 NeoForge RAG 知识库，把相关规则、约束和排查提示写入 repair artifacts。

完成内容：

- 新增 `repair_rag.py`，提供 `RepairRAGAdvisor` 和 `RepairRAGResult`。
- `agent generate` / `agent modify` 的 repair payload 新增 `repair_rag`。
- audit/build 失败时生成：
  - `.agent/repair-rag-context.json`
  - `.agent/repair-rag-context.md`
- `.agent/agent-repair-plan.md` 新增 `Repair RAG Context` 区块。
- Dashboard 新增 repair RAG 指标和 artifact 链接。
- Capability Matrix 新增 `repair_rag`。
- package metadata 更新到 `4.2.0`。

边界：

- RAG 不调用真实 LLM。
- RAG 不自动修改 Java / JSON / PNG / Gradle 文件。
- RAG 不影响 repair 成败判定；即使没有命中知识，也不会掩盖原始失败。
- safe repair loop 仍然只会基于 `.agent/modspec.json` 重生成 managed files。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest tests.test_repair_rag tests.test_agent_eval tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli capabilities --run-name v42-capabilities --json
```
