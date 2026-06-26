# Real LLM Stability

这份文档说明如何把真实 provider 的表现和 mock 基线分开统计。

核心口径：

- `mock` 用于 CI、离线回归和现场稳定演示。
- `openai-compatible` 用于验证真实模型是否能遵守 ModSpec / JSON / gate 契约。
- fallback 成功不能算 real LLM 成功；它必须单独记为 `fallback_success`。
- 最终正确性仍由 audit/build/runtime evidence 分层决定，不能只看模型输出。
- Minecraft runtime 不会被默认自动假装通过；没有显式证据时记为 `runtime_unverified`。

## 一键统计

配置好 `NEOFORGE_AGENT_LLM_*` 或 `OPENAI_*` 后运行：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli real-llm-stability --run-name real-llm-13case --cases examples\real_llm_stability_cases.json --llm-provider openai-compatible --limit 13 --no-build --audit --json
```

更严格的发布前版本：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli real-llm-stability --run-name real-llm-13case-build --cases examples\real_llm_stability_cases.json --llm-provider openai-compatible --limit 13 --build --audit --require-real --json
```

如果要把已有 Minecraft runtime 手工验证证据也纳入同一份报告：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli real-llm-stability --run-name real-llm-runtime-linked --cases examples\real_llm_stability_cases.json --llm-provider openai-compatible --limit 13 --build --audit --runtime-evidence path\to\manual-runtime-evidence.md --json
```

runtime evidence 的格式见 [../验证与可靠性/runtime-manual-validation.md](../验证与可靠性/runtime-manual-validation.md)。公开包不依赖本地旧验证表；需要 runtime evidence 时必须显式传入。

输出目录：

```text
workspace/real-llm-stability-runs/<run-name>/.agent/real-llm-stability.json
workspace/real-llm-stability-runs/<run-name>/.agent/real-llm-stability.md
```

## 最近一次真实跑批

2026-06-05 的 `real-llm-13case-runtime-upgrade` 用真实 `openai-compatible` provider 跑了 13 个 case：

- total cases: `13`
- strict success: `12`
- real LLM success: `12`
- strict / real LLM success rate: `92.31%`
- provider failure: `0`
- schema failure: `1`
- audit failure: `0`
- build failure: `0`（本轮使用 `--no-build`，不是 build 通过声明）
- runtime checked: `0`
- runtime success: `0`
- runtime unverified: `13`
- fallback success: `0`

唯一失败 case 是 `ruby_realm_world_structure`，失败类型为 `schema_failure`，原因是 LLM planner 多次返回 invalid JSON。这说明失败被归到结构化输出/schema 契约层，而不是 provider 连接、audit、build 或 fallback 层。

本轮没有传入 `--runtime-evidence`，所以所有 case 都必须记为 `runtime_unverified`，不能写成 Minecraft runtime 验证通过。

原始报告：

- `workspace/real-llm-stability-runs/real-llm-13case-runtime-upgrade/.agent/real-llm-stability.json`
- `workspace/real-llm-stability-runs/real-llm-13case-runtime-upgrade/.agent/real-llm-stability.md`

## 统计字段

报告会单独统计：

- `provider_failure_count`：API key、模型权限、HTTP 错误、超时等 provider 问题。
- `schema_failure_count`：真实模型返回 JSON 或 ModSpec schema 不合格。
- `audit_failure_count`：生成完成，但 workspace audit 不通过。
- `build_failure_count`：生成完成，但 Gradle build 不通过。
- `runtime_failure_count`：本次 strict case 有显式 runtime evidence，且 runtime 证据失败。
- `runtime_checked_count`：本次 strict case 成功生成 workspace，并匹配到 runtime evidence。
- `runtime_success_count`：匹配到 runtime evidence 且通过的 case 数。
- `runtime_unverified_count`：没有匹配到 runtime evidence 的 case 数。
- `fallback_success_count`：严格 real LLM 失败后，非严格 fallback 路径成功。
- `real_llm_success_count`：真实 provider 严格成功，且没有 fallback。

`--require-runtime` 只适合在每个 strict case 都有显式 runtime evidence 时使用；否则报告会失败。这个设计是为了避免把 no-build / no-runtime case 表述成完整 Minecraft runtime 验收。

## 当前 smoke 口径

本地 smoke 命令：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli real-llm-stability --run-name smoke-real-llm-stability --llm-provider openai-compatible --limit 1 --no-build --audit --json
```

如果 provider 返回 `HTTP 403`、timeout 或其他请求错误，报告应显示：

- strict real LLM case 归为 `provider_failure`；
- fallback probe 可以成功，但只记为 `fallback_success`；
- `real_llm_success_count` 仍然是 `0`。
- 没有传入 `--runtime-evidence` 时，case 记为 `runtime_unverified`，不计入 runtime success。

这个结果可以这样说明：

> mock 证明工程链路可复现；真实 provider 需要单独看 provider、schema、audit、build、runtime 和 fallback 分类。当前统计不会把 fallback 成功算成真实模型成功，也不会把缺失 runtime 证据的 case 说成游戏内验证通过。
