## V1.7 Integrated Doctor Quality Gate

Goal: make environment diagnostics part of the normal reliability path instead of a standalone-only command.

Completed:

- Integrated doctor into `quality-gate` as the first default check:
  - `doctor_environment`
- Default quality gate now runs:
  - `doctor --no-java --json`
  - Python `compileall`
  - `unittest discover`
  - `print-schema --json`
  - `test-examples --no-build --json`
  - mock LLM eval smoke
  - optional build smoke
- Added quality gate flags:
  - `--no-doctor`
  - `--doctor-java`
  - `--doctor-strict`
- Updated GitHub Actions artifact upload to include:
  - `workspace/quality-gate-runs/ci-quality-gate/.agent/**`
  - `workspace/doctor-runs/ci-quality-gate-doctor/.agent/**`
- Updated CI workflow tests to ensure doctor is not disabled.
- Updated quality gate tests for doctor pass/skip behavior.
- Updated README, CI docs, doctor docs, quality gate docs, and test matrix.
- Updated package metadata to version `1.7.0`.

Value:

- Makes local and CI reliability checks more self-explanatory: failures can now show environment problems before deeper generator checks.
- Keeps CI fast by skipping Java diagnostics in the default gate.
- Preserves stronger local validation through `quality-gate --doctor-java --build-smoke`.
