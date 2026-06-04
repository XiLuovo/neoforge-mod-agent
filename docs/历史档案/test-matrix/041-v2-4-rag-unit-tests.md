## V2.4 RAG Unit Tests

```powershell
py -3.11 -m unittest tests.test_knowledge_base tests.test_cli_parser tests.test_capabilities -v
```

Expected:

- knowledge query returns relevant snippets
- RAG query reports are written
- LLM planner artifacts include RAG context
- CLI parser accepts `knowledge query`
- capability matrix includes `knowledge_query` and `rag_planner_context`
