## V1.5 Local CI Equivalent

```powershell
py -3.11 -m agent.cli quality-gate --run-name ci-quality-gate-local --json
```

Expected:

- quality gate succeeds
- build smoke is skipped by default
- report is written under `workspace/quality-gate-runs/ci-quality-gate-local/.agent/`
- command matches the GitHub Actions workflow behavior except for the run name
