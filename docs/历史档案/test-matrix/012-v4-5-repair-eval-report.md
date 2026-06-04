## V4.5 Repair Eval Report

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_repair_eval tests.test_failure_lab tests.test_cli_parser tests.test_quality_gate tests.test_capabilities -v
py -3.11 -m agent.cli repair-eval --run-name v45-repair-eval --json
py -3.11 -m agent.cli repair-eval --run-name v45-recipe-repair-eval --case break_recipe_reference --json
py -3.11 -m agent.cli quality-gate --run-name v45-quality-gate --json
```

Expected:

- `repair-eval` succeeds.
- Report exists at `workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.json`.
- Markdown report exists at `workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.md`.
- Metrics include `audit_detected_rate`, `repair_rag_relevant_rate`, `repair_loop_repaired_rate`, `audit_recovered_rate`, and `full_success_rate`.
- Default five cases report `5/5` audit detected, `5/5` relevant repair RAG, `5/5` repair-loop repaired, and `5/5` audit recovered.
- Recipe reference case requires a relevant `recipes_loot_tags` RAG capability.
- `quality-gate` includes a `repair_eval` check by default.
- Project version reports `4.5.0`.
