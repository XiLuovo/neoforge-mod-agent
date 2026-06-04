## V1.6 Doctor Without Java

```powershell
py -3.11 -m agent.cli doctor --run-name v16-doctor-no-java --no-java --json
```

Expected:

- doctor command succeeds on machines where Java should not be checked
- `java.version` check is skipped
- doctor reports are still written
