## CLI Help

```powershell
py -3.11 -m agent.cli --help
py -3.11 -m agent.cli capabilities --help
py -3.11 -m agent.cli showcase --help
py -3.11 -m agent.cli doctor --help
py -3.11 -m agent.cli quality-gate --help
py -3.11 -m agent.cli eval --help
py -3.11 -m agent.cli agent --help
py -3.11 -m agent.cli agent generate --help
py -3.11 -m agent.cli agent modify --help
py -3.11 -m agent.cli generate --help
py -3.11 -m agent.cli modify --help
py -3.11 -m agent.cli audit --help
py -3.11 -m agent.cli repair --help
py -3.11 -m agent.cli print-schema --help
py -3.11 -m agent.cli test-examples --help
```

Expected:

- help output renders successfully
- `--audit` appears for `generate`, `generate-from-spec`, and `modify`
- `doctor` help includes `--no-java`, `--strict`, and `--run-name`
- `quality-gate` help includes `--no-doctor`, `--doctor-java`, and `--doctor-strict`
- `showcase` help includes `--quality-gate`, `--eval-limit`, and `--run-name`
- `capabilities` help includes `--run-name`
