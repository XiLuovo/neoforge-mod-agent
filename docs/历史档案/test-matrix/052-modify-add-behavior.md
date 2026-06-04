## Modify Add Behavior

```powershell
py -3.11 -m agent.cli generate --build "做一个红宝石模组，添加红宝石。" --workspace-name v10-modify-behavior --overwrite --json
py -3.11 -m agent.cli modify workspace/v10-modify-behavior "添加红宝石护符，右键回复4点生命值，冷却20秒。" --build --audit --json
```

Expected:

- modify succeeds
- build succeeds
- audit succeeds
- `ruby_charm` is added
