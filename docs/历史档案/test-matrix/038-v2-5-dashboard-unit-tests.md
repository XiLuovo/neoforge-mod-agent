## V2.5 Dashboard Unit Tests

```powershell
py -3.11 -m unittest tests.test_dashboard tests.test_cli_parser tests.test_capabilities -v
```

Expected:

- dashboard runner writes static HTML, JSON data, and Markdown report
- CLI parser accepts `dashboard`
- capability matrix includes `web_dashboard`
