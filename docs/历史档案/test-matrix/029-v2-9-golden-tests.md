## V2.9 Golden Tests

```powershell
py -3.11 -m agent.cli golden-test --run-name v29-golden --json
```

Expected:

- command succeeds
- `workspace/golden-runs/v29-golden/.agent/golden-report.json` exists
- golden cases cover item, block, behavior item, food effect, sword ignite, ore worldgen, tool set, armor set, and block variants
- each case checks generated file count, expected paths, expected feature ids, key JSON fields, and audit success
