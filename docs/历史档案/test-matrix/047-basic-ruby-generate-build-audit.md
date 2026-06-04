## Basic Ruby Generate / Build / Audit

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石。" --workspace-name v10-ruby --overwrite --json
```

Expected:

- generation succeeds
- build succeeds
- audit succeeds
- `workspace/v10-ruby/src/main/resources/pack.mcmeta` exists
