## V2.2 Eval Coverage Smoke

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --audit --run-name v22-eval-smoke --json
```

Expected:

- eval command succeeds
- default cases cover basic item, behavior item, speed effect, food effect, sword ignite, ore worldgen, modify add behavior, and modify add worldgen
- metrics include `expected_category_match_rate`
- metrics include `agent_artifacts_complete_rate`
- metrics include `repeat_modify_success_rate`
- repeat modify cases do not report unexpected added/updated features
- `workspace/eval-runs/v22-eval-smoke/.agent/eval-report.json` exists
- `workspace/eval-runs/v22-eval-smoke/.agent/eval-report.md` exists
