## LLM Mock Worldgen

```powershell
py -3.11 -m agent.cli generate "做一个红宝石模组，红宝石矿石自然生成在主世界地下，Y -64 到 32，每矿脉6个，每区块4个。" --planner llm --llm-provider mock --build --audit --workspace-name v10-llm-worldgen --overwrite --json
```

Expected:

- mock planning succeeds
- build succeeds
- audit succeeds
