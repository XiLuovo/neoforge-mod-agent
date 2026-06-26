# Golden Tests

Golden tests 用固定 prompt/spec 生成标准 workspace，并检查 deterministic generator 的稳定输出。它们是 RC1 的基础回归，不是新的 agent 主线。

## Command

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli golden-test --json
```

## 检查内容

- 生成文件数量；
- 关键路径是否存在；
- `ModSpec` feature id；
- 关键 JSON 字段；
- audit result；
- deterministic output 是否稳定。

## 与 RC1 Benchmark 的关系

```text
golden tests
-> protect deterministic generator
-> agent develop baseline remains stable
-> tool-calling loop can refine/repair on known foundation
```

`agent bench` 衡量真实 agent 行为；golden tests 保护 deterministic generator 的底座。
