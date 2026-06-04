## V1.1 Agent Generate

```powershell
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby charm item." --planner llm --llm-provider mock --build --workspace-name v11-agent-behavior --overwrite --json
```

Expected:

- agent run succeeds
- build succeeds
- audit succeeds
- `.agent/agent-run.json` exists
- `.agent/agent-run.md` exists
