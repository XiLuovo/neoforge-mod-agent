## Modify Add Worldgen

```powershell
py -3.11 -m agent.cli generate --build "做一个红宝石模组，添加红宝石和红宝石矿石，红宝石矿石挖掉掉落红宝石。" --workspace-name v10-modify-worldgen --overwrite --json
py -3.11 -m agent.cli modify workspace/v10-modify-worldgen "让红宝石矿石自然生成在主世界地下，Y -64 到 32，每矿脉6个，每区块4个。" --build --audit --json
```

Expected:

- modify succeeds
- build succeeds
- audit succeeds
- `ruby_ore` worldgen files are generated
