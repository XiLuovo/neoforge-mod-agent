## V3.1 RAG Knowledge Enhancement

```powershell
py -3.11 -m agent.cli knowledge query "right click heal ruby charm item cooldown" --run-name v31-rag-behavior --json
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby charm item." --planner llm --llm-provider mock --workspace-name v31-agent-rag --overwrite --json
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --limit 3 --run-name v31-rag-eval --json
py -3.11 -m agent.cli dashboard --run-name v31-dashboard --json
```

Expected:

- knowledge query succeeds and returns behavior/right-click related hits
- `rag-query.json` includes `query_expansions`, `categories`, and `capabilities`
- agent workspace includes `.agent/llm-used-knowledge.json`
- `prompt-trace.json` includes `used_knowledge`, `rag_categories`, and `rag_capabilities`
- eval metrics include `rag_hit_rate`, `rag_hits_total`, `rag_categories_covered`, and `rag_capabilities_covered`
- dashboard data includes `rag_summary`
- dashboard HTML contains `RAG Hit Summary`
