## V1.4 Quality Gate With Build Smoke

```powershell
py -3.11 -m agent.cli quality-gate --run-name v14-quality-gate-build --build-smoke --json
```

Expected:

- all fast checks pass
- build smoke generates a ruby workspace with `--build --audit`
- command is slower than the default quality gate
