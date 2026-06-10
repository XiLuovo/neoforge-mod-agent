# RC1 Agent Workflow

> 这是当前 Agent 工作流真相源。旧版生成、Direct Code Lane 和 Free-Code Lab 只作为兼容或辅助能力存在；RC1 推荐主线是 `agent develop`、`agent repair` 和 `agent bench`。

## 主线流程

```text
Natural language
-> planner / ModSpec
-> deterministic generator baseline
-> real tool-calling repair/refine loop
-> RAG / read files / structured patch / audit
-> LLM reviewer
-> audit/build gate
-> trace-backed benchmark
-> replayable evidence
```

## `agent develop`

`agent develop` 用于从自然语言目标创建并完善一个 NeoForge workspace：

1. planner 把用户目标整理为 intent contract 和 `ModSpec`。
2. deterministic generator 生成 baseline workspace。
3. 初始 audit/build observation 进入 tool-calling loop。
4. LLM 只能选择受控工具：`retrieve_rag`、`read_file`、`search_files`、`apply_structured_patch`、`run_audit`、`run_build`、`finish`。
5. reviewer 审查覆盖、unsupported request、patch 风险和残余风险。
6. 最终成功仍由 audit/build gate 决定。

常用 smoke：

```powershell
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name rc1-develop-demo --no-build --json
```

## `agent repair`

`agent repair` 用于已有 workspace 的受控修复。它不让 LLM 自由写 diff，而是把 audit/build 失败、RAG、文件内容和 reviewer observation 交给同一个 tool-calling loop。

```powershell
py -3.11 -m agent.cli agent repair rc1-develop-demo --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
```

## `agent bench`

`agent bench` 运行真实 develop/repair/reviewer/tool-calling 流程，并从真实 trace 汇总：

- `success_rate`
- `build_success_rate`
- `audit_success_rate`
- `repair_success_rate`
- `avg_tool_calls`
- `avg_iterations`
- `rag_hit_rate`
- `patch_accept_rate`
- `rollback_count`
- `failed_cases`
- `trace_paths`

```powershell
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

## 证据文件

一次 RC1 agent run 的核心证据在 `.agent/`：

```text
agent-run.json
prompt-trace.json
tool-call-trace.json
rag-context.json
repair-rag-context.json
reviewer-report.json
audit-report.json
repair-loop-report.json
structured-patch-plan.json
structured-patch-report.json
structured-patch-rollback-report.json
structured-patch-snapshots/
```

benchmark run 会在 `workspace/agent-benchmark-runs/<run-id>/.agent/` 写出 `agent-benchmark-report.json`、`.md` 和 `.html`。

## 安全边界

- LLM 不能修改本工具项目源码。
- LLM 不能输出任意 diff，只能输出结构化 patch action。
- patch 路径必须限制在 generated workspace。
- patch 前必须 snapshot，失败时保留 rollback evidence。
- reviewer 可以要求继续修复，但不能把失败的 audit/build 改成成功。
- Minecraft runtime 仍不是自动化验收的一部分。

## 辅助能力

Direct Code Lane 是旧主线遗留的受控 workspace patch 通道，可用于解释项目如何从 ModSpec-only 演进到结构化补丁；Free-Code Lab 是隔离实验区，用于探索 generator 暂时表达不了的需求。它们都不是 RC1 推荐 demo 主线。
