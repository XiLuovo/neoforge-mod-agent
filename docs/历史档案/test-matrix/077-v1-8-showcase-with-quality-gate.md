## V1.8 Showcase With Quality Gate

```powershell
py -3.11 -m agent.cli showcase --run-name v18-showcase-full --quality-gate --json
```

Expected:

- showcase succeeds
- quality gate step passes
- nested quality gate report is written under the showcase workspace area
