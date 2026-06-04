## V2.0 Agent Workflow Trace Smoke

```powershell
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby charm item." --planner llm --llm-provider mock --workspace-name v20-agent-trace --overwrite --no-build --json
```

Expected:

- command succeeds
- `.agent/agent-run.json` exists
- `.agent/agent-run.md` exists
- `.agent/agent-decisions.md` exists
- `.agent/prompt-trace.json` exists
- decisions include planner, reviewer, executor, auditor, and repair roles
- prompt trace includes normalized ModSpec
