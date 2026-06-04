## V3.3 Web Demo Workspace Manage And Modify

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
- HTML shell contains workspace selector, workspace refresh/load controls, modify request input, and modify API wiring
- smoke creates a base workspace through the generate flow
- workspace list includes the generated smoke workspace
- workspace load returns current `ModSpec`, generated files, and existing audit/trace summary
- modify adds `ruby_charm` through the existing `AgentOrchestrator.run_modify` path
- merge summary reports `ruby_charm` as added, updated, or skipped according to existing workspace state
- `ModSpec diff` includes the changed feature ids
- audit result is returned after modify
- agent trace remains visible after generate and modify
