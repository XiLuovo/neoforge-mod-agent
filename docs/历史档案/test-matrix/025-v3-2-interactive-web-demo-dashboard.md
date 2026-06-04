## V3.2 Interactive Web Demo Dashboard

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
- HTML shell contains prompt input, planner selection, generate API, and eval API
- mock LLM generate returns a `ModSpec`
- generated file list is returned
- audit result is returned
- build result is shown as skipped unless build is enabled
- agent trace includes steps, decisions, and prompt traces
- browser page can run generate and eval from `http://127.0.0.1:8765/`
