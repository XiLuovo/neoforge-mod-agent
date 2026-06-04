## V3.0 Dashboard Multi-Agent Trace

```powershell
py -3.11 -m agent.cli dashboard --run-name v30-dashboard --json
```

Expected:

- dashboard succeeds
- `workspace/dashboard-runs/v30-dashboard/index.html` exists
- dashboard HTML contains `Multi-Agent Trace`
- dashboard data includes `agent_traces`
- metrics include `agent_runs`, `agent_roles`, `agent_decisions`, and `prompt_traces`
