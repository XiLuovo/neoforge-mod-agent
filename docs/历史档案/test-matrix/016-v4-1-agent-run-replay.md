## V4.1 Agent Run Replay

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_replay tests.test_cli_parser tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli agent generate "Create a ruby mod with ruby." --planner llm --llm-provider mock --workspace-name v41-replay-source --overwrite --no-build --json
py -3.11 -m agent.cli replay workspace/v41-replay-source --json
py -3.11 -m agent.cli replay workspace/v41-replay-source/.agent/agent-run.json --json
py -3.11 -m agent.cli capabilities --run-name v41-capabilities --json
py -3.11 -m agent.cli quality-gate --run-name v41-quality-gate --json
```

Expected:

- `replay` succeeds without rerunning LLMs, generators, audit, build, or repair.
- `.agent/agent-run-replay.json` exists.
- `.agent/agent-run-replay.md` exists.
- `.agent/agent-run-replay.html` exists and renders the static session trace viewer.
- Replay events include `run_start`, `role_step`, `decision`, `prompt_trace`, and `artifacts`.
- Metrics include step counts, decision count, prompt trace count, RAG hit count, JSON repair count, retry count, LLM usage totals, and artifact count.
- Capability Matrix includes `agent_replay` and `session_trace_viewer`.
- Project version reports `4.1.0`.
