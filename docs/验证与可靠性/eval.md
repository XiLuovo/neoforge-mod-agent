# Eval 与 RC1 Benchmark

旧 eval 命令仍有价值：它们提供固定 prompt、固定期望和基础回归指标。RC1 之后，公开展示时应把它们解释为 benchmark 的底层材料，而不是最终主线。

## 当前关系

```text
legacy eval cases
-> selected develop / repair benchmark cases
-> real tool-calling loop
-> reviewer
-> audit/build gate
-> trace-backed agent metrics
```

## 推荐主命令

```powershell
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

## 旧 eval 还能说明什么

- deterministic planner/generator 是否稳定；
- audit 是否能发现结构问题；
- mock provider 是否适合 CI；
- 固定 prompt 的回归是否退步；
- benchmark case 的来源和覆盖范围。

## 不再作为主证据的内容

- 只读静态 eval report 聚合；
- 只比较 provider A/B 而不运行真实 repair/refine loop；
- 没有 `.agent/tool-call-trace.json` 的成功率。

公开讲解时可以说：旧 eval 是地基，RC1 `agent bench` 是当前验收视图。
