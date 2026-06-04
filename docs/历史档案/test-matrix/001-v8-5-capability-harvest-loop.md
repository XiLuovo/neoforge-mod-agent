## V8.5 Capability Harvest Loop

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_free_code_lab tests.test_cli_parser tests.test_capabilities tests.test_tool_manifest -v
py -3.11 -m unittest discover -s tests -v
```

Expected:

- `agent lab-generate` parses `--from-workspace`, `--run-name`, `--llm-provider`, `--build/--no-build`, and `--json`.
- `harvest-report` parses `--run-name` and `--json`.
- Free-Code Lab copies the source workspace into `workspace/free-code-lab-runs/<run-id>/workspace`.
- Free-Code Lab writes `free-code-plan.json`, `free-code-diff.md`, `free-code-report.json`, `manual-runtime-checklist.md`, and `harvest-candidate.json`.
- Unsafe paths are rejected: traversal, absolute paths, `.git`, `gradle/wrapper`, build outputs, binary artifacts, and tool source paths outside allowed workspace roots.
- `replace_text` fails on zero or multiple matches and succeeds on exactly one match.
- Build failure marks the harvest candidate as `reject`.
- Missing manual runtime checklist prevents harvest readiness.
- Existing lab run names are not overwritten.
- `harvest-report` aggregates candidates from `workspace/free-code-lab-runs/*/.agent/harvest-candidate.json`.
- Full unittest discovery passes: 163 test cases.
