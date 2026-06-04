## V1.5 CI Quality Gate

Goal: make the project GitHub-ready by connecting the local quality gate to CI.

Completed:

- Added GitHub Actions workflow:
  - `.github/workflows/quality-gate.yml`
- Configured CI to run on:
  - push to `main`
  - pull request
  - manual `workflow_dispatch`
- Configured CI with Python `3.11` and `PYTHONPATH=src`.
- Reused the existing V1.4 command:
  - `python -m agent.cli quality-gate --run-name ci-quality-gate --json`
- Uploaded quality gate artifacts from:
  - `workspace/quality-gate-runs/ci-quality-gate/.agent/**`
- Kept Gradle build smoke out of the default CI path so hosted runs remain fast and stable.
- Added `docs/验证与可靠性/ci.md`.
- Added workflow static tests under `tests/test_ci_workflow.py`.
- Updated README and test matrix with V1.5 CI instructions.
- Updated package metadata to version `1.5.0`.

Value:

- Turned the local reliability gate into an automated GitHub workflow.
- Made the project easier to present as a real engineering project, not just a local demo.
- Preserved the fast default CI path while keeping stronger local validation available through `quality-gate --build-smoke`.
