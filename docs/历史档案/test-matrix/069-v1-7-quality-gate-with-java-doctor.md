## V1.7 Quality Gate With Java Doctor

```powershell
py -3.11 -m agent.cli quality-gate --run-name v17-quality-gate-java --doctor-java --json
```

Expected:

- quality gate runs doctor with `java -version` diagnostics enabled
- Java lower than template target may be reported by doctor
- command succeeds unless doctor fails or another gate check fails
