## V1.9 Capabilities Smoke

```powershell
py -3.11 -m agent.cli capabilities --run-name v19-capabilities --json
```

Expected:

- command succeeds
- version is `1.9.0`
- sections include workflows, content, behaviors, worldgen, planning, and reliability
- `workspace/capability-runs/v19-capabilities/.agent/capabilities.json` exists
- `workspace/capability-runs/v19-capabilities/.agent/capabilities.md` exists
