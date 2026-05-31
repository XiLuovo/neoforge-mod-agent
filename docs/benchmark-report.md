# Benchmark Report Page

> 文档定位：这是 benchmark 报告专项材料，不是主学习入口。需要比较 provider、失败类型和修复指标时再读。

`benchmark-report` 把原来分散的 eval、real provider preflight、failure repair eval 和 runtime validation evidence 聚合成一个静态 benchmark 页面。

## Command

Fast offline mode:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli benchmark-report --run-name v82-benchmark-page-offline --eval-limit 2 --repair-limit 2 --no-build --audit
```

默认行为：

- Model A 使用 `mock` 并真实运行 eval。
- Model B 默认是 `openai-compatible`，但只做 config preflight，不会调用真实 provider。
- failure benchmark 运行 `repair-eval`，统计失败类型、audit detection、repair-loop recovery。
- runtime pass rate 从 `docs/test-matrix.md` 中的人工 Minecraft runtime validation evidence 读取。

要真实调用 Model B：

```powershell
py -3.11 -m agent.cli benchmark-report --run-name real-benchmark --run-real --candidate-provider openai-compatible --eval-limit 2 --repair-limit 2 --no-build --audit
```

`--require-real` 会在 real provider 缺失或不可用时让命令失败。

## Outputs

```text
workspace/benchmark-runs/<run-id>/.agent/benchmark-report.json
workspace/benchmark-runs/<run-id>/.agent/benchmark-report.md
workspace/benchmark-runs/<run-id>/.agent/benchmark-report.html
```

HTML 页面包含：

- Model A/B：provider、model、mock/real、success/audit/build rate。
- Failure Types：失败注入类型、audit 是否发现、repair 是否修复、最终 audit 是否恢复。
- Build Pass Rate：来自 eval/repair 中实际执行的 build；未执行时显示 `not run`。
- Runtime Pass Rate：来自已记录的 Minecraft runtime validation evidence。
- Artifacts：指向聚合 JSON、Markdown 和 repair-eval report。

## Boundary

这不是替代真实 Minecraft runtime 测试的自动化 harness。当前页面把已存在的 runtime validation evidence 纳入统一 benchmark 视图；后续可以把 dedicated runtime smoke harness 接进同一个 `runtime_cases` schema。
