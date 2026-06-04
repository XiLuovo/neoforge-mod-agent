## V1.9 Capability Matrix

Goal: export a structured source of truth for the current project capabilities.

Completed:

- Added `capabilities.py`.
- Added CLI command:
  - `capabilities`
- Capability matrix includes:
  - project metadata
  - core workflows
  - generated content types
  - behavior templates
  - worldgen support
  - planner and LLM boundaries
  - reliability and verification layers
  - current limitations
- Capability artifacts are written to:
  - `workspace/capability-runs/<run-id>/.agent/capabilities.json`
  - `workspace/capability-runs/<run-id>/.agent/capabilities.md`
- Added `docs/总览/capabilities.md`.
- Added capability catalog tests and CLI parser coverage.
- Updated README and test matrix.
- Updated package metadata to version `1.9.0`.

Value:

- Gives README, showcase, resumes, and interview walkthroughs a single structured capability source.
- Makes it easier to explain the project as a complete system rather than a list of scattered commands.
- Keeps capability documentation machine-readable for future automation.
