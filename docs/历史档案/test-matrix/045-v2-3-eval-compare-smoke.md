## V2.3 Eval Compare Smoke

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --run-name v23-baseline --json
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --run-name v23-candidate --json
py -3.11 -m agent.cli eval-compare v23-baseline v23-candidate --run-name v23-compare --json
```

Expected:

- both eval runs succeed
- compare command succeeds
- `regressions_count = 0`
- `workspace/eval-comparisons/v23-compare/.agent/eval-compare-report.json` exists
- `workspace/eval-comparisons/v23-compare/.agent/eval-compare-report.md` exists
