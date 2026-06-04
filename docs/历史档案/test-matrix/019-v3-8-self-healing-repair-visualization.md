## V3.8 Self-Healing Repair Visualization

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_web_demo tests.test_dashboard tests.test_capabilities -v
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli dashboard --run-name v38-dashboard --json
py -3.11 -m agent.cli dashboard --run-name v38-dashboard-fast --no-showcase --json
py -3.11 -m agent.cli capabilities --run-name v38-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v38-quality-gate --json
```

Expected:

- Web Demo HTML contains `V3.8 Self-Healing Agent Demo`, `repairView`, `repairStatus`, `Repair Agent`, and `Repair Loop`.
- Web Demo generate / modify payload contains `repair` and `self_healing`.
- Workspace detail API returns `repair_plan`, `repair_loop`, and `self_healing`.
- Dashboard HTML contains `Self-Healing Repair`.
- Dashboard data contains `repair_summary` and repair metrics such as `repair_runs`, `repair_executed`, and `repair_attempts`.
- Capability Matrix includes `web_demo_self_healing`, `dashboard_repair_summary`, and `self_healing_demo`.
- Existing V3.7 repair-agent safe execution tests still pass.
