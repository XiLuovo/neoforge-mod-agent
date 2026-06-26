# Web Demo Dashboard

`web-demo` 和 `dashboard` 是展示辅助入口。当前推荐 demo 仍是命令行跑 `agent develop`、`agent repair`、`agent bench` 和 RC2 `--rag-ablation`，再展示 `.agent` evidence；Dashboard 用来把这些 evidence 可视化。

## Web Demo

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli web-demo --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765/
```

Web Demo 是本地开发演示服务，默认绑定 localhost。它可以展示 workspace、RAG、audit/build、repair 和 trace evidence，但不开放任意文件编辑。

## Static Dashboard

```powershell
py -3.11 -m agent.cli dashboard --run-name rc1-dashboard --json
```

输出：

```text
workspace/dashboard-runs/rc1-dashboard/index.html
workspace/dashboard-runs/rc1-dashboard/.agent/dashboard-data.json
workspace/dashboard-runs/rc1-dashboard/.agent/dashboard-report.md
```

## 展示重点

- `.agent/agent-run.json`
- `.agent/tool-call-trace.json`
- `.agent/rag-decision-trace.json`
- `.agent/reviewer-report.json`
- `.agent/audit-report.json`
- `.agent/structured-patch-rollback-report.json`
- `agent-benchmark-report.html`

## 边界

- Dashboard 是展示层，不是最终验收 gate。
- Dashboard 不证明 Minecraft runtime 行为。
- Web Demo 不把项目变成通用 coding agent。
