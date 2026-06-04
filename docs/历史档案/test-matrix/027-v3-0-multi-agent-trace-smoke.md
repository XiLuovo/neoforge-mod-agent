## V3.0 Multi-Agent Trace Smoke

```powershell
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby charm item." --planner llm --llm-provider mock --workspace-name v30-agent-ruby-charm --overwrite --json
```

Expected:

- command succeeds
- generated workspace has `.agent/agent-run.json`
- generated workspace has `.agent/agent-decisions.md`
- generated workspace has `.agent/prompt-trace.json`
- generated workspace has `.agent/agent-trace-summary.json`
- generated workspace has `.agent/agent-trace-summary.md`
- roles include `planner_agent`, `reviewer_agent`, `executor_agent`, `auditor_agent`, and `repair_agent`
- reviewer step includes `review_checks`
- LLM output is normalized into ModSpec, not Java or JSON assets
