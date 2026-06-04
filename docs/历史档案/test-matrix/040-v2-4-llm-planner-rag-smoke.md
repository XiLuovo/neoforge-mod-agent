## V2.4 LLM Planner RAG Smoke

```powershell
py -3.11 -m agent.cli generate "Create a ruby mod with ruby ore worldgen in the overworld." --planner llm --llm-provider mock --workspace-name v24-rag-llm-worldgen --overwrite --no-build --audit --json
```

Expected:

- generation succeeds
- audit succeeds
- `.agent/rag-context.json` exists
- `.agent/rag-context.md` exists
- `.agent/planner-system-prompt.txt` contains `NeoForge RAG Context`
- RAG hits include `worldgen.overworld_ore`
