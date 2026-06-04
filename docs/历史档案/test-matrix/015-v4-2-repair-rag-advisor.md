## V4.2 Repair RAG Advisor

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_repair_rag tests.test_agent_eval tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli capabilities --run-name v42-capabilities --json
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli quality-gate --run-name v42-quality-gate --json
```

Expected:

- `RepairRAGAdvisor` retrieves bundled NeoForge knowledge for audit/build repair failures.
- Missing texture or texture-manifest failures retrieve texture/audit knowledge.
- Agent repair payload contains `repair_rag`.
- `.agent/repair-rag-context.json` exists when repair analysis sees a failing check.
- `.agent/repair-rag-context.md` exists when repair analysis sees a failing check.
- `.agent/agent-repair-plan.md` includes a `Repair RAG Context` section.
- Dashboard data includes `repair_rag_runs` and `repair_rag_hits`.
- Capability Matrix includes `repair_rag`.
- Project version reports `4.2.0`.
