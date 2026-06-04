## V1.2 Evaluation And Benchmark

Goal: add a measurable benchmark layer for the Agent workflow.

Completed:

- Added `evaluator.py`.
- Added CLI command:
  - `eval`
- Added default offline benchmark cases for:
  - basic ruby generation
  - behavior item generation
  - right-click effect item generation
  - food effect generation
  - ore worldgen generation
  - modify existing ore to add worldgen
- Reused V1.1 `AgentOrchestrator` instead of creating a separate generation path.
- Added expected feature checks against final `.agent/modspec.json`.
- Added aggregate metrics:
  - success rate
  - feature expectation match rate
  - planning success rate
  - audit success rate
  - optional build success rate
  - generated file counts
  - modify added / updated / skipped totals
- Wrote eval artifacts:
  - `workspace/eval-runs/<run-id>/.agent/eval-cases.json`
  - `workspace/eval-runs/<run-id>/.agent/eval-report.json`
  - `workspace/eval-runs/<run-id>/.agent/eval-report.md`
- Added `docs/验证与可靠性/eval.md`.
- Updated README and test matrix with V1.2 eval commands.

Value:

- Moved the project from one-off smoke tests toward repeatable benchmark evaluation.
- Made the Agent system easier to compare across future planner, LLM, and generator changes.
- Added a stronger portfolio story: the project has not only LLM planning and multi-agent orchestration, but also deterministic evaluation metrics.
