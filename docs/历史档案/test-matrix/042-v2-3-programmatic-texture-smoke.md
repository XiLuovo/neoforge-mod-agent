## V2.3 Programmatic Texture Smoke

```powershell
py -3.11 -m agent.cli generate "做一个红宝石模组，添加红宝石和红宝石矿石。" --workspace-name v23-texture-ruby --overwrite --no-build --audit --json
```

Expected:

- generation succeeds
- audit succeeds
- `.agent/texture-manifest.json` exists
- `src/main/resources/assets/ruby_mod/textures/item/ruby.png` exists
- `src/main/resources/assets/ruby_mod/textures/block/ruby_ore.png` exists
- generated texture PNGs are `16x16 RGBA`
