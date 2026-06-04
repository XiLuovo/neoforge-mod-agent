## V1.5 GitHub Actions Workflow Static Check

```powershell
Test-Path .github\workflows\quality-gate.yml
Select-String .github\workflows\quality-gate.yml -Pattern "quality-gate","actions/setup-python","upload-artifact","PYTHONPATH"
py -3.11 -m unittest tests.test_ci_workflow -v
```

Expected:

- workflow file exists
- workflow uses Python `3.11`
- workflow sets `PYTHONPATH=src`
- workflow runs `python -m agent.cli quality-gate --run-name ci-quality-gate --json`
- workflow uploads `.agent` quality gate artifacts
- workflow uploads `.agent` doctor artifacts
- default CI command does not include `--build-smoke`
- default CI command does not include `--no-doctor`
