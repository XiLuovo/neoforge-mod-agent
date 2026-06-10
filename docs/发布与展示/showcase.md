# RC1 Showcase

RC1 showcase 的目标是让项目展示为一个可验证、可回放、可评测的领域 Coding Agent。

## 展示顺序

1. 打开 [../总览/rc1-learning-guide.md](../总览/rc1-learning-guide.md)，用 1 分钟说明项目定位。
2. 运行 `agent develop`，展示 baseline generation 和 tool-call trace。
3. 运行 `agent repair`，展示 structured patch、snapshot、rollback evidence。
4. 打开 `.agent/reviewer-report.json`，说明 reviewer 只审查风险，不替代 gate。
5. 运行 `agent bench`，展示 trace-backed metrics。
6. 打开 [agent-rc1-showcase.md](agent-rc1-showcase.md)，对比普通 generator 和当前 agent。

## 推荐命令

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name rc1-showcase --no-build --json
py -3.11 -m agent.cli agent repair rc1-showcase --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

## 讲解重点

- 不是让 LLM 一次性写完整 Mod；
- planner、generator、tool loop、reviewer、audit/build 各司其职；
- tool call 和 reviewer 都有真实 JSON evidence；
- benchmark 读真实 trace，而不是静态报告；
- Minecraft runtime 仍是边界，不要夸大成自动游戏内验收。

## RC2 Agentic RAG Demo

RC2 adds a focused demo path for proving that the project is an agentic repair system, not a one-shot generator.

Run the offline RAG ablation benchmark:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench `
  --suite examples/agentic_rag_ablation.json `
  --llm-provider mock `
  --rag-ablation `
  --audit `
  --json
```

For each repair case, the benchmark runs paired `rag_on` and `rag_off` versions. The report highlights `rag_success_delta`, `rag_on_success_rate`, `rag_off_success_rate`, and `rag_citation_coverage_rate`.

Best evidence to show:

- one `tool-call-trace.json`
- one `rag-decision-trace.json`
- one `reviewer-report.json`
- `workspace/benchmark-runs/<run-id>/.agent/agent-benchmark-report.json`

The demo story is: the agent observes an audit failure, decides RAG is required, rewrites the query, retrieves multi-hop citations, applies a structured patch with citation ids, reruns audit, and compares the result against a RAG-off control run.

### RC2 Real-Provider Talking Points

For portfolio or interview demos, present RC2 in two layers:

- Controlled mock ablation: proves RAG policy changes behavior and produces stable RAG-on/RAG-off metrics.
- Real-provider acceptance: proves the same tool-calling loop runs with an OpenAI-compatible provider and produces replayable evidence.

Current complete real-provider evidence:

```text
workspace/benchmark-runs/rc2-real-ablation-accepted/.agent/agent-benchmark-report.json
workspace/benchmark-runs/rc2-real-ablation-accepted/.agent/agent-benchmark-report.md
workspace/benchmark-runs/rc2-real-ablation-accepted/.agent/agent-benchmark-report.html
```

Headline result:

```text
6 / 6 paired real-provider cases succeeded
audit_success_rate = 1.0
repair_success_rate = 1.0
rag_citation_coverage_rate = 0.5833
```

Important nuance: in this real-provider run, `rag_off` also succeeded because the model could repair the simple injected failures without retrieval. Do not oversell this as "RAG always improves success rate." The stronger claim is that the project now measures the difference, records why retrieval happened, links patches to citations, and can compare RAG-on against RAG-off under the same suite.
