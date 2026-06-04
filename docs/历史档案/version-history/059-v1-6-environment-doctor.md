## V1.6 Environment Doctor

Goal: add a local preflight diagnostic command so new checkouts are easier to debug.

Completed:

- Added `doctor.py`.
- Added CLI command:
  - `doctor`
- Doctor checks:
  - Python version
  - project layout
  - compatibility CLI entrypoint
  - NeoForge template directory
  - template Gradle wrapper files
  - template Java toolchain version
  - workspace root and parent writability
  - `PYTHONPATH`
  - important docs
  - GitHub Actions workflow
  - `java -version`
- Added `--no-java` to skip Java diagnostics.
- Added `--strict` to treat warnings as failures.
- Wrote doctor artifacts:
  - `workspace/doctor-runs/<run-id>/.agent/doctor-report.json`
  - `workspace/doctor-runs/<run-id>/.agent/doctor-report.md`
- Added `docs/验证与可靠性/doctor.md`.
- Added doctor tests and CLI parser coverage.
- Updated README and test matrix with V1.6 commands.
- Updated package metadata to version `1.6.0`.

Value:

- Helps users quickly understand why local setup may not run.
- Adds another portfolio-friendly reliability layer alongside audit, eval, tests, quality gate, and CI.
- Keeps diagnostics deterministic and read-only, so it is safe to run before generation.
