## V1.6 Environment Doctor

```powershell
py -3.11 -m agent.cli doctor --run-name v16-doctor-smoke --json
```

Expected:

- doctor command succeeds unless a required local prerequisite is missing
- report is written under `workspace/doctor-runs/v16-doctor-smoke/.agent/`
- checks include Python, project layout, template files, workspace, docs, CI workflow, and Java diagnostics
- Java version lower than the configured target is reported as a warning, not a default failure
