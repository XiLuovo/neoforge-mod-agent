# Agent RC1 Showcase

RC1 的展示主线是三段可直接运行的 Coding Agent 入口：`agent develop`、`agent repair`、`agent bench`。这三段分别展示从自然语言到 baseline workspace、基于 observation 的受控修复，以及从真实 trace 汇总 benchmark 指标。

## 一键演示入口

推荐先跑脚本，脚本默认使用 mock LLM，不依赖外部 API，也默认跳过 Gradle build：

```powershell
.\scripts\portfolio_showcase.ps1
```

兼容保留的快速入口也已经切到同一条 RC1 主线：

```powershell
.\scripts\v5_portfolio_demo.ps1
```

常用参数：

```powershell
.\scripts\portfolio_showcase.ps1 -RunName rc1-showcase-local
.\scripts\portfolio_showcase.ps1 -Build
.\scripts\portfolio_showcase.ps1 -UseRealLlm
.\scripts\portfolio_showcase.ps1 -BenchEvalLimit 2 -BenchRepairLimit 2
```

脚本会顺序执行：

1. `agent develop` 生成并完善 NeoForge workspace。
2. `agent repair` 对同一 workspace 运行 observe/retrieve/patch/check loop。
3. `agent bench` 运行真实 develop/repair/reviewer/tool loop，并输出 trace-backed metrics。

默认产物位置：

```text
workspace/<run-name>-develop/.agent/agent-run.md
workspace/<run-name>-develop/.agent/tool-call-trace.json
workspace/<run-name>-develop/.agent/reviewer-report.json
workspace/<run-name>-develop/.agent/audit-report.json
workspace/<run-name>-develop/.agent/structured-patch-report.json
workspace/<run-name>-develop/.agent/structured-patch-rollback-report.json
workspace/benchmark-runs/<run-name>-bench/.agent/agent-benchmark-report.md
workspace/benchmark-runs/<run-name>-bench/.agent/agent-benchmark-report.html
```

## 单步命令

演示或代码讲解时，可以把脚本拆成三条命令逐段展示：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)

py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name rc1-demo-develop --no-build --max-iterations 5 --json

py -3.11 -m agent.cli agent repair rc1-demo-develop --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json

py -3.11 -m agent.cli agent bench --run-name rc1-demo-bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

## RC1 能力摘要

- Natural language goal 先收敛到 planner / ModSpec。
- Deterministic generator 生成 baseline workspace。
- Tool-calling loop 根据 observation 调用 `retrieve_rag`、`read_file`、`search_files`、`apply_structured_patch`、`run_audit`、`run_build`、`finish`。
- Structured patch 限制在 workspace 安全边界内，写前 snapshot，写后生成 rollback evidence。
- LLMReviewer 输出覆盖、缺失需求、unsupported/risky request、patch risk、recommended checks 和 decision。
- Audit/build gate 仍然是最终验收标准。
- `agent bench` 运行真实 develop/repair/reviewer/tool loop，并从 trace 统计指标。
- `.agent` evidence 可用于 replay、debug、展示和技术讲解。

## Agent Flow

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

## Evidence 文件说明

- `.agent/agent-run.json`：一次 agent run 的主 payload，包含 mode、planner、runtime、repair/reviewer/audit/build 摘要。
- `.agent/tool-call-trace.json`：真实 LLM tool action 序列，不是从 step 派生的假 trace。
- `.agent/prompt-trace.json`：planner、repair agent、reviewer 的 prompt/response 摘要，不保存长 chain-of-thought。
- `.agent/rag-context.json`：planner / baseline 阶段使用的 RAG context。
- `.agent/repair-rag-context.json`：repair/refine loop 中检索到的 RAG context。
- `.agent/reviewer-report.json`：真实 LLMReviewer 的结构化审查输出。
- `.agent/audit-report.json`：确定性 workspace audit 结果。
- `.agent/structured-patch-report.json`：结构化 patch 执行报告。
- `.agent/structured-patch-rollback-report.json`：snapshot 和 rollback evidence。
- `workspace/benchmark-runs/<run-id>/.agent/agent-benchmark-report.json`：真实 agent benchmark 指标汇总。

## Benchmark 指标说明

- `success_rate`：case 最终通过 deterministic gate 的比例。
- `build_success_rate` / `audit_success_rate`：build/audit gate 通过比例。
- `repair_success_rate`：repair/refine loop 成功比例。
- `avg_tool_calls`：真实 tool trace 的平均工具调用数。
- `avg_iterations`：真实 loop iteration 平均值。
- `rag_hit_rate`：真实 RAG observation 命中比例。
- `patch_accept_rate`：结构化 patch 被接受的比例。
- `rollback_count`：写入 rollback evidence 的次数。
- `failed_cases`：失败 case 列表。
- `trace_paths`：可回放 evidence 路径。

## 普通生成器 vs 当前 Coding Agent

| 维度 | 普通一次性生成器 | RC1 受控 Coding Agent |
| --- | --- | --- |
| 输入处理 | 直接按 prompt 生成文件 | 先收敛到 planner / ModSpec |
| 文件生成 | 一次性输出 | deterministic baseline + 受控 patch |
| LLM 权限 | 容易变成自由 diff | 只能选择结构化工具 |
| 修复方式 | 重新生成或人工修 | 基于 audit/build observation 的 tool loop |
| 安全边界 | 难审计 | workspace path safety、snapshot、rollback evidence |
| 审查 | 靠人工看结果 | LLMReviewer 审查覆盖和风险 |
| 最终验收 | 模糊 | deterministic audit/build gate |
| 评测 | 静态报告 | 真实 trace-backed benchmark |
| 展示材料 | 生成物截图 | `.agent` evidence 可 replay |

## 展示顺序

1. 打开 `workspace/<run-name>-develop/.agent/agent-run.md`，说明 develop 的阶段拆分和最终 gate。
2. 打开 `tool-call-trace.json`，说明 LLM 只能选择受控工具。
3. 打开 `reviewer-report.json`，说明 reviewer 是风险审查，不替代 audit/build。
4. 打开 `structured-patch-report.json` 和 `structured-patch-rollback-report.json`，说明 patch、snapshot 和 rollback evidence。
5. 打开 `workspace/benchmark-runs/<run-name>-bench/.agent/agent-benchmark-report.html`，讲 `success_rate`、`avg_tool_calls`、`patch_accept_rate` 和 `trace_paths`。

## 边界

- 当前不是通用 coding agent。
- 当前稳定 domain 是 NeoForge Minecraft Mod。
- Reviewer 不能替代 audit/build gate。
- Audit/build 不能替代真实 Minecraft runtime 自动化测试。
- 真实 LLM provider 需要额外管理成本、延迟和稳定性。

## 继续阅读

- [../总览/rc1-learning-guide.md](../总览/rc1-learning-guide.md)
- [../Agent与能力/tool-calling-contract.md](../Agent与能力/tool-calling-contract.md)
- [../验证与可靠性/benchmark-report.md](../验证与可靠性/benchmark-report.md)
