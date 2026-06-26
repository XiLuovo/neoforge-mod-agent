# RC1 Demo Cases

这些 demo 用来展示当前主线：受控 NeoForge Minecraft Mod Coding Agent，而不是普通一次性生成器。

## Demo 1: Develop

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name rc1-demo-ruby --no-build --json
```

讲解重点：

- planner 生成 `ModSpec`；
- deterministic generator 生成 baseline workspace；
- tool-calling loop 真实读取 RAG/文件并可执行受控 patch；
- `.agent/tool-call-trace.json` 来自真实 LLM action；
- reviewer report 是真实 reviewer 输出；
- audit/build gate 决定最终成功。

## Demo 2: Repair

先制造或保留一个 audit/build observation，再运行：

```powershell
py -3.11 -m agent.cli agent repair rc1-demo-ruby --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
```

讲解重点：

- repair 复用 develop 的同一个 tool-calling loop；
- patch 只能走 `apply_structured_patch`；
- snapshot 和 rollback evidence 必须存在；
- reviewer 可以要求继续修复，但不能绕过 gate。

## Demo 3: Bench

```powershell
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

讲解重点：

- benchmark 运行真实 agent 行为；
- `avg_tool_calls`、`avg_iterations`、`patch_accept_rate` 来自 trace；
- failed cases 能对应到具体 workspace 和 `.agent` evidence。

## Demo Evidence Checklist

```text
.agent/agent-run.json
.agent/tool-call-trace.json
.agent/prompt-trace.json
.agent/rag-context.json
.agent/reviewer-report.json
.agent/audit-report.json
.agent/repair-loop-report.json
.agent/structured-patch-rollback-report.json
```
