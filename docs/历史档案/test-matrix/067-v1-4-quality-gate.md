## V1.4 Quality Gate

```powershell
py -3.11 -m agent.cli quality-gate --run-name v14-quality-gate-smoke --json
```

Expected:

- quality gate succeeds
- doctor environment preflight passes
- compileall passes
- unittest passes
- print-schema passes
- test-examples passes
- eval smoke passes
- build smoke is skipped by default
- `workspace/quality-gate-runs/v14-quality-gate-smoke/.agent/quality-gate-report.json` exists
- `workspace/quality-gate-runs/v14-quality-gate-smoke/.agent/quality-gate-report.md` exists
