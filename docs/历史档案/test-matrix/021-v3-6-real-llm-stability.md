## V3.6 Real LLM Stability

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_llm_stability -v
py -3.11 -m agent.cli doctor --run-name v36-doctor --no-java --json
py -3.11 -m agent.cli capabilities --run-name v36-capabilities --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby." --planner llm --llm-provider mock --workspace-name v36-llm-stability --overwrite --no-build --audit --json
```

Expected:

- JSON repair handles Markdown-fenced/prose-wrapped model output.
- planner retries after malformed JSON and records retry count.
- provider configuration inspection is secret-safe and does not call the network.
- `doctor` includes `llm.openai_compatible` as pass or warning.
- `.agent/llm-stability.json` records provider config summary, parse attempts, retries, and repair status.
- mock LLM smoke remains offline and deterministic.
