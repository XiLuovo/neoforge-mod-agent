## V1.3 Automated Regression Tests

Goal: turn core smoke coverage into a fast, repeatable test suite.

Completed:

- Added `tests/`.
- Added standard-library `unittest` coverage with no third-party test dependency.
- Added generation and audit tests:
  - basic ruby generation succeeds
  - generated project passes audit
  - `pack.mcmeta` is generated and recorded
- Added negative audit test:
  - deleting a generated item model makes audit fail
- Added Agent workflow test:
  - mock LLM `agent generate` succeeds and writes `agent-run.json`
- Added Eval workflow tests:
  - default eval subset reports feature metrics
  - missing expected feature makes eval fail
- Added CLI parser tests:
  - top-level help includes `eval` and `agent`
  - `eval` options parse correctly
  - `generate --audit` parses correctly
- Exported `ModProjectPlanner` from package top-level API.
- Added `docs/验证与可靠性/testing.md`.
- Updated README and test matrix with V1.3 test commands.

Value:

- Made the project easier to regression-test before future feature work.
- Kept the default test suite fast by skipping Gradle builds.
- Added a stronger engineering reliability story for resumes and interviews.
