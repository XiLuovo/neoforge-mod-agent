## Food Effect Generate / Build

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石苹果，吃了给予生命恢复2，持续5秒。" --workspace-name v10-food-effect --overwrite --json
```

Expected:

- build succeeds
- audit succeeds
- food effect appears in generated Java
