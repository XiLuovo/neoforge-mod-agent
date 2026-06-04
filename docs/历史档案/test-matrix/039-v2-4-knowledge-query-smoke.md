## V2.4 Knowledge Query Smoke

```powershell
py -3.11 -m agent.cli knowledge query "红宝石矿石自然生成在主世界地下" --run-name v24-rag-worldgen --json
```

Expected:

- command succeeds
- at least one hit is returned
- top hit is related to overworld ore worldgen
- `workspace/knowledge-runs/v24-rag-worldgen/.agent/rag-query.json` exists
- `workspace/knowledge-runs/v24-rag-worldgen/.agent/rag-query.md` exists
