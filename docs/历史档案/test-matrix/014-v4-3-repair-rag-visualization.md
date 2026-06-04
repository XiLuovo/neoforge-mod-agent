## V4.3 Repair RAG Visualization

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_replay tests.test_web_demo tests.test_dashboard tests.test_capabilities -v
py -3.11 -m agent.cli dashboard --run-name v43-dashboard --json
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli capabilities --run-name v43-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v43-quality-gate --json
```

Expected:

- Dashboard HTML contains `Repair RAG Advice`.
- Dashboard repair cards show RAG query and knowledge hit ids.
- Dashboard data includes `repair_rag_links` for root-cause/action/knowledge mapping.
- Replay output includes a `repair_rag` event.
- Replay metrics include `repair_rag_events_count` and `repair_rag_hits_count`.
- Web Demo HTML contains `Repair RAG`.
- Web Demo self-healing payload includes `repair_rag_hits_count`, `repair_rag_hits`, and `repair_rag_links`.
- Capability Matrix includes `dashboard_repair_rag`, `web_demo_repair_rag`, and `replay_repair_rag`.
- Project version reports `4.3.0`.
