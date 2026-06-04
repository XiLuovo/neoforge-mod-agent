## V2.0 Unit Tests

```powershell
py -3.11 -m unittest tests.test_agent_eval tests.test_capabilities tests.test_cli_parser -v
```

Expected:

- agent generate writes decision and prompt trace artifacts
- capability catalog reports version `2.0.0`
- CLI parser still accepts existing commands
