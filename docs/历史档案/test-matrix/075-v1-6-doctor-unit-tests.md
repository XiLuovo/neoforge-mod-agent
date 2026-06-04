## V1.6 Doctor Unit Tests

```powershell
py -3.11 -m unittest tests.test_doctor -v
```

Expected:

- doctor runner writes JSON and Markdown reports
- core layout checks pass
- Java check can be skipped deterministically in tests
