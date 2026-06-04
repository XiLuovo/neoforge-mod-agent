## V1.2 Eval With Build

```powershell
py -3.11 -m agent.cli eval --planner llm --llm-provider mock --build --limit 2 --run-name v12-eval-build-smoke --json
```

Expected:

- eval command succeeds
- build is attempted for selected cases
- build success metrics are present
- this command is slower than `--no-build`
