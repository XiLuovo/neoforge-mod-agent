## Behavior Item Generate / Build / Audit

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石护符，右键回复4点生命值，冷却20秒。" --workspace-name v10-behavior --overwrite --json
```

Expected:

- build succeeds
- audit succeeds
- custom `RubyCharmItem.java` is generated
