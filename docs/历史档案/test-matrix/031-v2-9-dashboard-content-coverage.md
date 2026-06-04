## V2.9 Dashboard Content Coverage

```powershell
py -3.11 -m agent.cli dashboard --run-name v29-dashboard --no-showcase --json
```

Expected:

- dashboard succeeds
- `workspace/dashboard-runs/v29-dashboard/index.html` exists
- dashboard data includes `content_coverage`
- metrics include `content_capabilities_total`, `content_capabilities_covered`, and `content_coverage_rate`
