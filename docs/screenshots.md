# 项目截图清单

> 文档定位：这是截图素材清单，不是主学习入口。需要准备 README、作品集或视频截图时再读。

截图目标是证明项目“可演示、可解释、可验证”，而不是只展示代码目录。

## 已纳入公开版的截图

```text
docs/assets/v50-dashboard-overview.png
docs/assets/v81-agent-replay-viewer.png
docs/assets/v82-benchmark-report.png
```

- `v50-dashboard-overview.png`：静态 dashboard 首屏，适合展示能力矩阵、RAG、Agent trace、repair 和 eval。
- `v81-agent-replay-viewer.png`：session replay / trace viewer，适合展示一次 Agent run 的 planner、executor、auditor、repair 和 provider metadata。
- `v82-benchmark-report.png`：benchmark 页面，适合展示 mock/real provider、模型 A/B、失败类型、修复率和通过率。

## 对应 HTML 证据

```text
workspace/v81-provider-layer-smoke-20260514/.agent/agent-run-replay.html
workspace/benchmark-runs/v82-benchmark-page-offline-20260514/.agent/benchmark-report.html
workspace/portfolio-runs/v80-portfolio-showcase/runs/dashboard-runs/v80-portfolio-showcase-dashboard/index.html
```

公开发布包会把精选 HTML / JSON / Markdown 证据复制到：

```text
release-artifacts/evidence/
```

完整 `workspace/` 不进入公开发布包。

## 推荐补充截图

如果要录视频或做简历图集，可以继续补：

```text
docs/assets/public-release-manifest.png
docs/assets/failure-repair-report.png
docs/assets/real-vs-mock-report.png
```

推荐截图顺序：

1. README 首页：展示项目定位和架构图。
2. Dashboard：展示能力覆盖和 demo 入口。
3. Replay viewer：展示可回放的 Agent 决策链。
4. Benchmark report：展示模型对比和修复指标。
5. Failure repair report：展示失败注入、audit、repair、再次通过。
6. Release manifest：展示公开版如何排除 `workspace/` 和本地缓存。
