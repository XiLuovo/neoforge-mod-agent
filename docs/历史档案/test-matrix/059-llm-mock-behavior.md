## LLM Mock Behavior

```powershell
py -3.11 -m agent.cli generate "做一个红宝石模组，添加红宝石护符，右键回血。" --planner llm --llm-provider mock --build --audit --workspace-name v10-llm-behavior --overwrite --json
```

Expected:

- mock planning succeeds
- build succeeds
- audit succeeds
