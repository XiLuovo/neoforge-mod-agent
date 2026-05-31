# Capability Matrix

> 文档定位：这是能力矩阵查证文件，不建议从头读。学习主线见 [project-learning-plan-cn.md](project-learning-plan-cn.md)，需要确认当前能力边界时再查本文。历史版本流水账见 [version-history.md](version-history.md)。

## Current Stable Capabilities

| Capability | Status | Notes |
| --- | --- | --- |
| `minecraft.neoforge` domain | stable | 当前唯一完整落地 domain。 |
| `ModSpec` | stable | 结构化真相源，驱动 generator / audit / repair。 |
| item / block / ore | stable | 基础内容、资源、模型、掉落和 worldgen。 |
| food / sword / tool / armor | stable | 常见装备、材料和配方生成。 |
| recipe / loot / tag | stable | 受控 JSON 资源生成。 |
| Behavior DSL | stable | 事件-条件-动作行为模板。 |
| Machine DSL | stable | 基础 BlockEntity / Menu / Screen / machine GUI 模板。 |
| Entity DSL | stable | 受控 entity / mob 骨架。 |
| Progression / Quest DSL | stable | 玩法线、任务、advancement 和 guidebook 结构。 |
| World / Structure DSL | stable | 受控 world/structure 资源和预览。 |
| Programmatic textures | stable | 确定性 PNG、atlas、资源质量报告。 |
| Agent workflow | stable | planner / reviewer / executor / auditor / repair / trace。 |
| RAG knowledge base | stable | 本地 NeoForge 知识检索，服务 planner 和 repair。 |
| mock LLM provider | stable | 离线稳定回归和学习。 |
| real LLM provider | experimental | OpenAI-compatible provider、health check、retry、fallback。 |
| audit / build / repair | stable | 静态审计、Gradle build、managed-file repair-loop。 |
| eval / benchmark / replay | stable | 能力评测、模型/版本对比、历史 run 回放。 |
| dashboard / showcase | stable | 本地演示和静态报告入口。 |
| tool manifest | stable contract | 内部工具契约；不是完整 MCP server。 |

## Controlled Extension Capabilities

| Capability | Status | Boundary |
| --- | --- | --- |
| Controlled Java Extension | stable controlled path | 通过 ModSpec 字段生成 extension package 下的受控 helper class。 |
| Controlled patch-agent | stable controlled path | modify 场景的 managed-file patch/report/rollback evidence。 |
| Direct Code Lane | V8.4 production lane | `agent generate` / `agent modify` 的结构化 workspace 补丁通道。 |
| Free-Code Lab | V8.5 experimental lane | generate gap 的隔离实验通道，不改原 workspace，不自动改 generator。 |
| Capability Harvest Loop | V8.5 process | 从实验样本到 generator/audit/test 固化的能力采集闭环。 |

Direct Code Lane 细节见 [direct-code-lane.md](direct-code-lane.md)。Free-Code Lab 和 harvest candidate 细节见 [capability-harvest-loop.md](capability-harvest-loop.md)。

## Current Non-Goals

- 不承诺任意 Java / Gradle / datapack 自由生成。
- 不承诺复杂多方块结构、复杂网络同步、完整 runtime 自动化测试。
- 不把 mock LLM 成功当成真实 LLM 成功。
- 不把 tool manifest 宣称为完整 MCP server。
- 不把 Free-Code Lab 的实验代码自动合并进稳定 generator。

更完整限制见 [project-limitations.md](project-limitations.md)。

## Useful Commands

```powershell
py -3.11 -m agent.cli capabilities --run-name local-capabilities --json
py -3.11 -m agent.cli tools-manifest --run-name local-tools --json
py -3.11 -m unittest discover -s tests -v
```

## Evidence Files

常见证据入口：

- `.agent/modspec.json`
- `.agent/generation-summary.json`
- `.agent/audit-report.json`
- `.agent/agent-run.json`
- `.agent/prompt-trace.json`
- `.agent/direct-code-*.json`
- `.agent/free-code-report.json`
- `.agent/harvest-candidate.json`
- benchmark / replay / evidence-chain HTML 或 Markdown 报告

## Planned Or Limited Areas

| Area | Status |
| --- | --- |
| `spring.api` domain | planned registry entry, not implemented domain. |
| `unity.component` domain | planned registry entry, not implemented domain. |
| AST-aware direct-code patching | not implemented. |
| automatic Direct Code repair-loop | not implemented. |
| Minecraft runtime smoke automation | not implemented. |
| first harvested generator upgrade | next focus, likely advanced machine GUI / BlockEntity. |
