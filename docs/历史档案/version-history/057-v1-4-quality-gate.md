## V1.4 Quality Gate

Goal: provide a one-command reliability gate for demos, commits, and future feature work.

Completed:

- Added `quality_gate.py`.
- Added CLI command:
  - `quality-gate`
- The default quality gate runs:
  - Python `compileall`
  - `unittest discover`
  - `print-schema --json`
  - `test-examples --no-build --json`
  - `eval --planner llm --llm-provider mock --no-build --limit 2 --json`
- Added optional `--build-smoke` for slower Gradle compile verification.
- Added per-check stdout/stderr logs under:
  - `workspace/quality-gate-runs/<run-id>/.agent/logs/`
- Wrote quality gate artifacts:
  - `workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.json`
  - `workspace/quality-gate-runs/<run-id>/.agent/quality-gate-report.md`
- Added skip flags for development:
  - `--no-compile`
  - `--no-unittest`
  - `--no-schema`
  - `--no-examples`
  - `--no-eval`
- Added `docs/验证与可靠性/quality-gate.md`.
- Updated README and test matrix with V1.4 commands.
- Added tests for quality gate parser and schema-only runner behavior.

Value:

- Turned separate reliability commands into a single reproducible gate.
- Made the project easier to validate before demos or future feature work.
- Added a clean CI-style story without introducing external dependencies.
