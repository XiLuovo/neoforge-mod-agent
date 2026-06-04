## V0.9 Project Audit

Goal: verify generated workspace structure beyond what Gradle build can catch.

Completed:

- Added `auditor.py`.
- Added `audit` CLI command.
- Read `.agent/modspec.json` and `.agent/generation-summary.json`.
- Checked base project files.
- Checked generated files listed in `generation-summary.json`.
- Checked item, block, ore, food, sword, recipe, behavior, and worldgen outputs.
- Wrote audit artifacts:
  - `.agent/audit-report.json`
  - `.agent/audit-report.md`
- Added negative audit testing by deleting a generated model file.

Value:

- Added deterministic structural validation of generated projects.
- Covered gaps that Gradle build alone cannot detect, such as missing models, missing lang keys, missing worldgen files, and stale generated-file records.
