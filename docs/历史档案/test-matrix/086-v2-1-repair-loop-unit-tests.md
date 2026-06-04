## V2.1 Repair Loop Unit Tests

```powershell
py -3.11 -m unittest tests.test_repair_loop -v
```

Expected:

- healthy workspace is a no-op
- missing generated item model is restored
