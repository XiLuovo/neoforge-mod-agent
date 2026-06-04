## V0.4 Build Repair Loop

Goal: make failures diagnosable and repairable instead of opaque.

Completed:

- Added Gradle build execution through the CLI.
- Captured build logs under `.agent/logs`.
- Classified common build errors such as missing symbols, bad imports, constructor mismatches, resource JSON errors, and dependency issues.
- Generated repair artifacts:
  - `.agent/debug-context.md`
  - `.agent/fix-request.md`
  - `.agent/suspected-errors.json`
- Added `repair` command and build repair integration.

Value:

- Built the first reliability loop around generation.
- Made build failures easier to hand to a human or future repair agent.
