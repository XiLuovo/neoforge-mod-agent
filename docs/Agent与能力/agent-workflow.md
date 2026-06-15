# Current Agent Workflow

> 这是当前 Agent 工作流真相源。旧版生成、Direct Code Lane 和 Free-Code Lab 只作为兼容或辅助能力存在；当前推荐主线是 `agent develop`、`agent repair`、`agent bench` 和 RC2 RAG ablation。

## 主线流程

```text
Natural language
-> planner / feature plan / ModSpec
-> deterministic generator baseline
-> real tool-calling repair/refine loop
-> Agentic RAG policy / multi-hop retrieve_rag / read files
-> structured patch with citation evidence
-> LLM reviewer evidence sufficiency check
-> audit/build gate
-> trace-backed benchmark / RAG ablation
-> replayable evidence
```

## `agent develop`

`agent develop` 用于从自然语言目标创建并完善一个 NeoForge workspace：

1. planner 把用户目标整理为 intent contract 和 `ModSpec`。
2. deterministic generator 生成 baseline workspace。
3. 初始 audit/build observation 进入 tool-calling loop。
4. LLM 只能选择受控工具：`retrieve_rag`、`read_file`、`search_files`、`apply_structured_patch`、`run_audit`、`run_build`、`finish`。
5. Agentic RAG policy 根据失败原因、敏感文件、unsupported request 或 reviewer observation 决定是否必须检索。
6. reviewer 审查覆盖、unsupported request、patch 风险、残余风险和 evidence sufficiency。
7. 最终成功仍由 audit/build gate 决定。

常用 smoke：

```powershell
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name rc1-develop-demo --no-build --json
```

Decomposed Planner v1 可用 `--planner decomposed` 走同一 workflow：planner 先输出 feature plan，再按 `item/ore/machine/tool/sword/recipe/progression` 生成小 JSON，组合为 `ModSpec` 后交给 deterministic generator。modify 请求在 v1 中仍复用现有受控 LLM patch planner。

## `agent repair`

`agent repair` 用于已有 workspace 的受控修复。它不让 LLM 自由写 diff，而是把 audit/build 失败、RAG policy、文件内容和 reviewer observation 交给同一个 tool-calling loop。

```powershell
py -3.11 -m agent.cli agent repair rc1-develop-demo --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
```

需要强制或关闭 RAG 时可以用 `--rag-mode auto|on|off`。RAG disabled 不代表不记录证据，RC2 会写 skipped decision 供 ablation 对比。

## `agent bench`

`agent bench` 运行真实 develop/repair/reviewer/tool-calling 流程，并从真实 trace 汇总：

- `success_rate`
- `build_success_rate`
- `audit_success_rate`
- `repair_success_rate`
- `avg_tool_calls`
- `avg_iterations`
- `rag_hit_rate`
- `rag_citation_coverage_rate`
- `patch_accept_rate`
- `rollback_count`
- `failed_cases`
- `trace_paths`

```powershell
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

RC2 RAG ablation：

```powershell
py -3.11 -m agent.cli agent bench --suite examples/agentic_rag_ablation.json --llm-provider mock --rag-ablation --audit --json
```

## 证据文件

一次当前 agent run 的核心证据在 `.agent/`：

```text
agent-run.json
prompt-trace.json
tool-call-trace.json
rag-context.json
repair-rag-context.json
rag-decision-trace.json
reviewer-report.json
audit-report.json
repair-loop-report.json
structured-patch-plan.json
structured-patch-report.json
structured-patch-rollback-report.json
structured-patch-snapshots/
decomposed-planner/feature-plan.json
decomposed-planner/feature-jsons.json
decomposed-planner/composed-modspec-raw.json
decomposed-planner/bad-raw-outputs.json
```

benchmark run 会在 `workspace/benchmark-runs/<run-id>/.agent/` 写出 `agent-benchmark-report.json`、`.md` 和 `.html`。

## 安全边界

- LLM 不能修改本工具项目源码。
- LLM 不能输出任意 diff，只能输出结构化 patch action。
- patch 路径必须限制在 generated workspace。
- patch 前必须 snapshot，失败时保留 rollback evidence。
- reviewer 可以要求继续修复或要求更多 RAG evidence，但不能把失败的 audit/build 改成成功。
- Minecraft runtime 仍不是自动化验收的一部分。

## 辅助能力

Direct Code Lane 是旧主线遗留的受控 workspace patch 通道，可用于解释项目如何从 ModSpec-only 演进到结构化补丁；Free-Code Lab 是隔离实验区，用于探索 generator 暂时表达不了的需求。它们都不是当前推荐 demo 主线。
