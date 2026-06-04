## Sword Ignite Generate / Build

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石剑，击中敌人点燃5秒。" --workspace-name v10-sword-ignite --overwrite --json
```

Expected:

- build succeeds
- audit succeeds
- custom `RubySwordItem.java` is generated
