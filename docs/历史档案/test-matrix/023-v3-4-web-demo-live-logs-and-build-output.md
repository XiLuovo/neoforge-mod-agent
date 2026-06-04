## V3.4 Web Demo Live Logs And Build Output

```powershell
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli web-demo --help
```

Manual demo:

```powershell
py -3.11 -m agent.cli web-demo --host 127.0.0.1 --port 8765
```

Expected:

- smoke succeeds without starting a blocking server
- HTML shell contains async job API wiring for `/api/jobs/generate`, `/api/jobs/modify`, and `/api/job`
- HTML shell contains `Run Log` and `Build Output` tabs
- generate / modify buttons start background jobs and poll job status
- job payload includes queued/running/completed log events
- build output preview is available when Gradle log files exist
- original synchronous `/api/generate` and `/api/modify` APIs remain available
