## V1.8 Showcase Reports

Goal: provide a one-command, portfolio-friendly demo flow that summarizes the current Agent system.

Completed:

- Added `showcase.py`.
- Added CLI command:
  - `showcase`
- The default showcase flow runs:
  - environment doctor preflight without Java diagnostics
  - mock LLM multi-role `agent generate`
  - mock LLM multi-role `agent modify`
  - offline eval smoke benchmark
  - optional quality gate when `--quality-gate` is passed
- Showcase workspaces are isolated under:
  - `workspace/showcase-runs/<run-id>/workspaces/`
- Showcase artifacts are written to:
  - `workspace/showcase-runs/<run-id>/.agent/showcase-report.json`
  - `workspace/showcase-runs/<run-id>/.agent/showcase-report.md`
- Added flags:
  - `--run-name`
  - `--planner`
  - `--llm-provider`
  - `--eval-limit`
  - `--build`
  - `--quality-gate`
- Added `docs/发布与展示/showcase.md`.
- Added showcase runner tests and CLI parser coverage.
- Updated README and test matrix.
- Updated package metadata to version `1.8.0`.

Value:

- Creates a concise report suitable for GitHub, resumes, and interview walkthroughs.
- Demonstrates the project as a complete Agent system: doctor, LLM planner, multi-agent orchestration, modify, audit, eval, and optional quality gate.
- Keeps the default showcase fast by avoiding Gradle builds unless explicitly requested.
