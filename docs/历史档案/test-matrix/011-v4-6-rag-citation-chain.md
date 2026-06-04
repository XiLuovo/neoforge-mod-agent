## V4.6 RAG Citation Chain

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_agent_eval tests.test_dashboard tests.test_capabilities tests.test_replay -v
py -3.11 -m agent.cli agent generate "做一个红宝石模组，添加红宝石护符，右键回复4点生命值，冷却20秒。" --planner llm --llm-provider mock --workspace-name v46-rag-citations --overwrite --json
py -3.11 -m agent.cli dashboard --run-name v46-dashboard --json
py -3.11 -m agent.cli capabilities --run-name v46-capabilities --json
```

Expected:

- `agent-run.json` decisions contain `knowledge_ids` and `knowledge_refs`.
- `agent-decisions.md` displays `knowledge ids`.
- planner decisions include RAG references from `used_knowledge`.
- repair decisions include references from `repair_rag.hits` when repair is needed.
- dashboard HTML contains `RAG Citation Chain`.
- dashboard data contains `rag_reference_chains`.
- Capability Matrix includes `explainable_rag_citations` and `dashboard_rag_citation_chain`.
- Project version reports `4.6.0`.
