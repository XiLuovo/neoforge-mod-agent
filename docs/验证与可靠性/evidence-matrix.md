# 项目评测与证据总览

这份表把项目已有的评测结果按验证层级归档。它不新增实验，也不把不同来源的成功率相加。

## 证据矩阵

| 评测 | 规模/结果 | Provider 与 gate | 能证明什么 | 不能证明什么 |
|---|---:|---|---|---|
| Full-schema vs decomposed prompt A/B | 2026-07-18 post-fix：full-schema strict `5/5`、semantic `4/5`；decomposed strict `5/5`、semantic `3/5` | real provider；audit；无 build/runtime | raw evidence 显示 total tokens `253,819 → 6,917`（约降 `97.3%`）、平均延迟 `46.0s → 10.9s`，并把流程成功与语义覆盖分开 | Minecraft runtime 行为；semantic/audit 都不等于 runtime 已验收 |
| Real LLM stability smoke | 2026-07-19：13 个 case；`12/13` strict；audit `12/12`；semantic `7/13`；feature `15/33`；category `22/37` | real provider；audit；`--no-build` | 当前 raw evidence 证明真实模型进入 ModSpec/generator/audit 流程的稳定性，并量化 unsupported capability 与语义缺口 | Gradle build 或 Minecraft runtime |
| Repair benchmark | 18 个 repair case | mock/可选 real provider；tool loop；structured patch；audit | 受控 repair、tool-calling、patch 和 failure handling | 真实游戏行为 |
| RAG ablation | RAG-on `3/3`，RAG-off `0/3` | mock benchmark；audit；无 runtime | RAG 上下文对指定 repair case 的行为差异 | 通用 RAG 能力或 runtime 验收 |
| Mock development E2E | 2 个 case；audit/build 通过 | mock；decomposed planner；audit；Gradle build | 离线可复现的 planner → generator → audit/build 主链路 | 真实 provider 稳定性、Minecraft runtime |
| Minecraft runtime evidence | 4 个 case；`4/4` passed | 实际 NeoForge 客户端；人工 checklist；截图/hash | 物品、行为、worldgen 和 Deepslate 负高度场景的实际游戏内观察 | 所有 ModSpec 能力均已 runtime 覆盖 |

## 关键来源

- Prompt A/B 与 13-case real-provider：[`real-llm-evidence-summary.md`](../Agent与能力/real-llm-evidence-summary.md)
- Real provider 统计口径：[`real-llm-stability.md`](../Agent与能力/real-llm-stability.md)
- Repair benchmark：[`benchmark-report.md`](benchmark-report.md)
- Minecraft runtime：[`evidence/runtime/README.md`](../../evidence/runtime/README.md)
- Mock development E2E：[`evidence/portfolio/mock-development-e2e-20260627/eval-report.md`](../../evidence/portfolio/mock-development-e2e-20260627/eval-report.md)

## 对外表述边界

- `mock` 结果只能说明离线流程可复现。
- `real provider` 结果必须绑定具体 run、模型、planner 和失败分类。
- `audit/build` 不等于 Minecraft runtime 验收。
- 只有 `evidence/runtime/` 中明确记录并附带截图或日志的 case，才能写成已完成人工 runtime 验证。
- 历史 13-case 与当前 runtime 4-case 属于不同证据层，不能合并成一个总成功率。
