## V2.6 Tool And Armor Smoke

```powershell
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加红宝石镐。" --workspace-name v26-ruby-pickaxe --overwrite --json
py -3.11 -m agent.cli generate --build --audit "做一个红宝石模组，添加一套红宝石护甲。" --workspace-name v26-ruby-armor --overwrite --json
```

Expected:

- tool generation succeeds and build succeeds
- armor set generation succeeds and build succeeds
- audit checks item models, textures, lang keys, Java registration, tool method calls, and armor `ArmorType` usage
- `.agent/texture-manifest.json` records `tool_*` and `armor_*` templates
