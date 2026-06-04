## V2.1 Repair Loop Smoke

Generate a simple workspace:

```powershell
py -3.11 -m agent.cli generate "Create a ruby mod with ruby." --workspace-name v21-repair-loop --overwrite --no-build --audit --json
```

Delete a generated item model:

```powershell
Remove-Item workspace\v21-repair-loop\src\main\resources\assets\ruby_mod\models\item\ruby.json
```

Run the repair loop:

```powershell
py -3.11 -m agent.cli repair-loop workspace\v21-repair-loop --max-attempts 1 --no-build --json
```

Expected:

- initial audit fails inside the repair-loop report
- managed files are regenerated
- final audit succeeds
- deleted item model exists again
- `.agent/repair-loop-report.json` exists
- `.agent/repair-loop-report.md` exists
