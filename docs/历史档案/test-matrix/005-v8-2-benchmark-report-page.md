## V8.2 Benchmark Report Page

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_benchmark_report tests.test_cli_parser tests.test_capabilities -v
py -3.11 -m agent.cli benchmark-report --run-name v82-benchmark-page-offline-20260514 --eval-limit 2 --repair-limit 2 --baseline-provider mock --candidate-provider openai-compatible --no-build --audit
py -3.11 -m unittest discover -s tests -v
```

Expected:

- `workspace/benchmark-runs/v82-benchmark-page-offline-20260514/.agent/benchmark-report.json` exists.
- `workspace/benchmark-runs/v82-benchmark-page-offline-20260514/.agent/benchmark-report.md` exists.
- `workspace/benchmark-runs/v82-benchmark-page-offline-20260514/.agent/benchmark-report.html` exists.
- Model A runs `mock`; Model B preflights `openai-compatible` and skips real calls unless `--run-real` or `--require-real` is passed.
- Benchmark metrics include model run counts, repair rate, build pass rate, and runtime pass rate.
- HTML page renders Model A/B, Failure Types, Runtime Evidence, and artifact paths.
- Full unittest discovery passes: 163 test cases.
