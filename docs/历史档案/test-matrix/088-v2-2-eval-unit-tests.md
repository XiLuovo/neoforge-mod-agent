## V2.2 Eval Unit Tests

```powershell
py -3.11 -m unittest tests.test_agent_eval tests.test_capabilities -v
```

Expected:

- eval reports expected feature and category metrics
- agent trace artifacts are checked
- repeat modify idempotency is reported
- capability catalog reports version `2.2.0`
