## Audit Success

```powershell
py -3.11 -m agent.cli audit workspace/v10-worldgen --json
```

Expected:

- `success=true`
- `.agent/audit-report.json` exists
- `.agent/audit-report.md` exists
