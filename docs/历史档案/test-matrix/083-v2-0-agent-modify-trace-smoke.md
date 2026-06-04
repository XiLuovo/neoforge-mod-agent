## V2.0 Agent Modify Trace Smoke

```powershell
py -3.11 -m agent.cli agent modify workspace\v20-agent-trace "Add ruby ore that generates underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk." --planner llm --llm-provider mock --no-build --json
```

Expected:

- command succeeds
- added includes `ruby` and `ruby_ore` when the base project does not already contain ruby
- audit succeeds
- `.agent/agent-decisions.md` is updated
- `.agent/prompt-trace.json` records the modify patch prompt and normalized patch
