## V3.7 Repair Agent Safe Execution

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_agent_eval.AgentEvalTests.test_agent_repair_executes_safe_loop_after_audit_failure -v
py -3.11 -m unittest tests.test_agent_eval tests.test_repair_loop tests.test_capabilities -v
py -3.11 -m agent.cli capabilities --run-name v37-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v37-quality-gate --json
```

Expected:

- agent repair step detects audit/build failure.
- repair agent executes safe repair loop when repair is enabled.
- missing managed files are regenerated from `.agent/modspec.json`.
- repair payload includes `repair_executed=true`, `repair_success=true`, and embedded `repair_loop`.
- `.agent/agent-repair-plan.json` and `.agent/repair-loop-report.json` are written.
- existing repair-loop command still works independently.
