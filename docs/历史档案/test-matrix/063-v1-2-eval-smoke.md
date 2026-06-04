## V1.2 Eval Smoke

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --limit 2 --run-name v12-eval-smoke --json
```

Expected:

- eval command succeeds
- `workspace/eval-runs/v12-eval-smoke/.agent/eval-cases.json` exists
- `workspace/eval-runs/v12-eval-smoke/.agent/eval-report.json` exists
- `workspace/eval-runs/v12-eval-smoke/.agent/eval-report.md` exists
- metrics include success rate and expected feature match rate
