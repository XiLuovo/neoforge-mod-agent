## Audit Negative

```powershell
Remove-Item workspace\v10-ruby\src\main\resources\assets\ruby_mod\models\item\ruby.json
py -3.11 -m agent.cli audit workspace/v10-ruby --json
```

Expected:

- `success=false`
- errors mention missing item model
- command exits non-zero
