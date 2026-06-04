## V1.3 Automated Unit Regression

```powershell
py -3.11 -m unittest discover -s tests -v
```

Expected:

- all tests pass
- generation/audit tests pass
- negative audit test catches a missing item model
- agent mock LLM test passes
- eval metric tests pass
- CLI parser tests pass
