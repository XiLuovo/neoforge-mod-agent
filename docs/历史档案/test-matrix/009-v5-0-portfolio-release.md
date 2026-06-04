## V5.0 Portfolio Release

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_capabilities tests.test_dashboard -v
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli capabilities --run-name v50-capabilities --json
.\scripts\v5_portfolio_demo.ps1
py -3.11 -m agent.cli quality-gate --run-name v50-quality-gate --json
```

Expected:

- Project version reports `5.0.0`.
- Capability Matrix includes `portfolio_release_package`.
- README contains the V5.0 Chinese portfolio entry.
- `scripts/v5_portfolio_demo.ps1` runs `portfolio-demo` with mock LLM by default.
- `docs/portfolio-release.md`, `docs/interview-script.md`, `docs/总览/architecture.md`, `docs/发布与展示/demo-cases.md`, and `docs/发布与展示/screenshots.md` exist.
- Portfolio report is written under `workspace/portfolio-runs/v50-portfolio/.agent/portfolio-demo-report.md`.
- Dashboard HTML is written under `workspace/portfolio-runs/v50-portfolio/runs/dashboard-runs/v50-portfolio-dashboard/index.html`.
- Quality gate passes with build smoke skipped by default.
