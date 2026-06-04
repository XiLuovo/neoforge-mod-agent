## V8.4 ModSpec-First + Direct Code Lane

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_direct_code_agent tests.test_cli_parser tests.test_capabilities -v
py -3.11 -m unittest discover -s tests -v
```

Expected:

- `agent generate` and `agent modify` accept `--code-lane {hybrid,modspec,direct}`.
- Hybrid mode keeps the ModSpec path for normal mock cases.
- Direct Code Lane writes plan, review, diff, report, rollback report, and affected-file snapshots under `.agent/`.
- Direct Code changes are scoped to the generated workspace and reject absolute paths, path traversal, `.git`, Gradle wrapper jars, and build outputs.
- Full unittest discovery passes: 163 test cases.
