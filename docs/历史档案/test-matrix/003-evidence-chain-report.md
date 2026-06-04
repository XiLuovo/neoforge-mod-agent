## Evidence Chain Report

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_evidence_chain_report tests.test_cli_parser tests.test_capabilities tests.test_portfolio_demo -v
py -3.11 -m agent.cli evidence-chain-report --run-name local-evidence-chain --eval-limit 1 --repair-limit 1 --json
```

Expected:

- `workspace/evidence-chain-runs/local-evidence-chain/.agent/evidence-chain-report.json` exists.
- `workspace/evidence-chain-runs/local-evidence-chain/.agent/evidence-chain-report.md` exists.
- Report layers include `stable`, `behavior`, and `patch_agent`.
- Metrics include `layers_passed = 3`, `acceptance_success_rate = 1.0`, `recovery_rate = 1.0`, `failure_samples_total = 3`, and `runtime_validation_pass_rate = 1.0`.
- Stable layer includes mock eval success plus injected failure repair evidence.
- Behavior layer includes shared Behavior DSL generation, validator failure sample, and corrected recovery sample.
- Patch-agent layer includes managed-file patch plan evidence, an initial simulated build failure sample, rollback recommendation, and repair-loop recovery evidence.
