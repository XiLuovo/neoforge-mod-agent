## V2.3 Behavior Texture Smoke

```powershell
py -3.11 -m agent.cli generate "做一个红宝石模组，添加红宝石护符，右键回复4点生命值，冷却20秒。" --planner llm --llm-provider mock --workspace-name v23-texture-charm --overwrite --no-build --audit --json
```

Expected:

- generation succeeds
- audit succeeds
- `ruby_charm.png` exists under item textures
- `.agent/texture-manifest.json` records template `heal_badge`
