## V1.8 Showcase Smoke

```powershell
py -3.11 -m agent.cli showcase --run-name v18-showcase-smoke --json
```

Expected:

- showcase succeeds
- doctor step passes
- agent generate step passes
- agent modify step passes
- eval smoke step passes
- quality gate step is skipped by default
- `workspace/showcase-runs/v18-showcase-smoke/.agent/showcase-report.json` exists
- `workspace/showcase-runs/v18-showcase-smoke/.agent/showcase-report.md` exists
