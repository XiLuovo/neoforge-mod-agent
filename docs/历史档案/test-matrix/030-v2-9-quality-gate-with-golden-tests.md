## V2.9 Quality Gate With Golden Tests

```powershell
py -3.11 -m agent.cli quality-gate --run-name v29-quality-gate --json
```

Expected:

- quality gate runs doctor, compileall, unittest, print-schema, test-examples, eval smoke, and golden tests
- default eval smoke covers V2.6 tool/armor and V2.8 block variants
- build smoke remains skipped unless `--build-smoke` is passed

Fast variant:

```powershell
py -3.11 -m agent.cli quality-gate --run-name v29-quality-gate-fast --no-golden --json
```

Expected:

- `golden_tests` check is skipped
- other enabled quality-gate checks still run
