## V1.7 Quality Gate Without Doctor

```powershell
py -3.11 -m agent.cli quality-gate --run-name v17-quality-gate-no-doctor --no-doctor --json
```

Expected:

- `doctor_environment` is skipped
- other default fast checks still run
- command succeeds if compile, unittest, schema, examples, and eval smoke pass
