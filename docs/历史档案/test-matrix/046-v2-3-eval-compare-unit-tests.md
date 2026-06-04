## V2.3 Eval Compare Unit Tests

```powershell
py -3.11 -m unittest tests.test_eval_compare tests.test_cli_parser tests.test_capabilities -v
```

Expected:

- identical reports compare successfully
- metric and case regressions are reported
- eval run names resolve to `workspace/eval-runs/<run-id>/.agent/eval-report.json`
- CLI parser accepts `eval-compare`
- capability matrix includes `eval_compare`

This matrix records the current smoke, regression, agent, evaluation, automated test, quality-gate, CI, doctor, showcase, capabilities, texture, and RAG commands for the V2.4 workflow.

All commands assume:

```powershell
Set-Location L:\projects\MinecraftMods\idea
$env:PYTHONPATH = (Resolve-Path .\src)
```
