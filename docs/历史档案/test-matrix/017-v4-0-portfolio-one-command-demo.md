## V4.0 Portfolio One-Command Demo

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_portfolio_demo tests.test_cli_parser tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli portfolio-demo --run-name v40-portfolio --eval-limit 1 --json
py -3.11 -m agent.cli capabilities --run-name v40-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v40-quality-gate --json
```

Expected:

- `portfolio-demo` succeeds offline with mock LLM by default.
- Report exists at `workspace/portfolio-runs/<run-id>/.agent/portfolio-demo-report.json`.
- Markdown report exists at `workspace/portfolio-runs/<run-id>/.agent/portfolio-demo-report.md`.
- Steps include `doctor`, `showcase`, `dashboard`, `llm_eval_report`, `web_demo_smoke`, and `capabilities`.
- Dashboard `index.html` is generated under the portfolio run's nested dashboard directory.
- Capability Matrix includes `portfolio_demo`.
- Project version reports `4.0.0`.
