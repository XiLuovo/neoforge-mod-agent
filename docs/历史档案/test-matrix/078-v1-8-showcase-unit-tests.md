## V1.8 Showcase Unit Tests

```powershell
py -3.11 -m unittest tests.test_showcase -v
```

Expected:

- showcase runner writes JSON and Markdown reports
- core showcase steps pass
- quality gate step can be skipped for fast tests
