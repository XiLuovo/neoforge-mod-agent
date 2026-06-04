## V2.5 Dashboard Fast Smoke

```powershell
py -3.11 -m agent.cli dashboard --run-name v25-dashboard-fast --no-showcase --json
```

Expected:

- command succeeds
- HTML dashboard exists
- showcase step is marked `skip`
- capabilities and RAG sections still render
