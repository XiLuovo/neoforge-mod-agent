## V3.5 Web Demo RAG Knowledge Browser

```powershell
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli web-demo --help
```

Manual demo:

```powershell
py -3.11 -m agent.cli web-demo --host 127.0.0.1 --port 8765
```

Expected:

- smoke succeeds without starting a blocking server
- HTML shell contains `RAG Knowledge` tab and `/api/knowledge` API wiring
- knowledge API returns bundled entries, category options, capability options, and tag options
- query `worldgen ore` returns `worldgen.overworld_ore`
- category / capability / tag filters narrow the displayed knowledge entries
- knowledge browser remains read-only and does not alter planner or generator behavior
