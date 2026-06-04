## V1.1 Agent Modify

```powershell
py -3.11 -m agent.cli generate --build "Create a ruby mod with ruby and ruby ore." --workspace-name v11-agent-modify-base --overwrite --json
py -3.11 -m agent.cli agent modify workspace/v11-agent-modify-base "Make ruby ore generate underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk." --planner llm --llm-provider mock --build --json
```

Expected:

- agent run succeeds
- `ruby_ore` is updated
- build succeeds
- audit succeeds
- `.agent/agent-run.json` records planner, reviewer, executor, auditor, and repair roles
