## V1.2 Eval Full Offline Suite

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --no-build --run-name v12-eval-full --json
```

Expected:

- default eval cases run with mock LLM
- audit succeeds for generated workspaces
- expected feature checks pass
- report records planning, audit, feature, and modify metrics
