## Schema Regression

```powershell
py -3.11 -m agent.cli print-schema --json
```

Expected:

- JSON schema prints successfully
- includes behavior and ore worldgen fields
