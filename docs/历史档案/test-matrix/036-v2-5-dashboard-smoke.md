## V2.5 Dashboard Smoke

```powershell
py -3.11 -m agent.cli dashboard --run-name v25-dashboard --json
```

Expected:

- command succeeds
- `workspace/dashboard-runs/v25-dashboard/index.html` exists
- `.agent/dashboard-data.json` exists
- `.agent/dashboard-report.md` exists
- dashboard data includes capabilities, RAG hits, and showcase summary
