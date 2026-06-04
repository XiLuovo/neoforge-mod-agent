## V3.9 Real LLM Eval And Compare Report

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_llm_eval_report tests.test_cli_parser tests.test_capabilities -v
py -3.11 -m agent.cli llm-eval-report --candidate-provider mock --limit 2 --run-name v39-llm-eval-mock --json
py -3.11 -m agent.cli llm-eval-report --candidate-provider openai-compatible --limit 1 --run-name v39-llm-eval-preflight --json
py -3.11 -m agent.cli capabilities --run-name v39-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v39-quality-gate --json
```

Expected:

- `llm-eval-report --candidate-provider mock` runs baseline eval, candidate eval, and eval-compare offline.
- Report exists at `workspace/llm-eval-runs/<run-id>/.agent/llm-eval-report.json`.
- Missing real provider config does not call the network and is recorded as a safe candidate skip unless `--require-real` is passed.
- Provider config summary does not expose API keys.
- Capability Matrix includes `llm_eval_report`, `real_llm_eval_compare`, and `llm_eval_preflight`.
