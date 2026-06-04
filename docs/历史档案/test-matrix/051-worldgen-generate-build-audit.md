## Worldgen Generate / Build / Audit

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石和红宝石矿石，红宝石矿石挖掉掉落红宝石，并自然生成在主世界地下，Y -64 到 32，每矿脉6个，每区块4个。" --workspace-name v10-worldgen --overwrite --json
```

Expected:

- build succeeds
- audit succeeds
- configured feature JSON is generated
- placed feature JSON is generated
- biome modifier JSON is generated
