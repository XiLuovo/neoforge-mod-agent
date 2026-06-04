# V1.3 Automated Tests

> 文档定位：这是自动化测试专项材料，不是主学习入口。需要理解 unittest、schema、example 和 smoke 覆盖时再读。

V1.3 adds a standard-library test suite for the core generation, audit, agent, eval, and CLI parsing paths. The suite uses `unittest`, so it does not require installing `pytest` or any other third-party dependency.

## Run Tests

From the project root:

```powershell
Set-Location L:\projects\MinecraftMods\idea
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest discover -s tests -v
```

Expected result:

```text
Ran 8 tests
OK
```

## What The Suite Covers

- Basic ruby generation without Gradle build.
- Workspace audit success for generated projects.
- `pack.mcmeta` generation and `generation-summary.json` tracking.
- Negative audit behavior when a generated item model is missing.
- V1.1 agent generate workflow with mock LLM.
- V1.2 benchmark evaluator metrics and report writing.
- Eval failure when `expected_features` are not found in the final `ModSpec`.
- CLI parser coverage for `eval`, `generate --audit`, and top-level help.

## Why Builds Are Disabled

The automated test suite intentionally skips Gradle build by default. Build checks are slower and depend more heavily on the local Java/Gradle environment. They are still covered by smoke commands in `docs/历史档案/test-matrix.md`.

The intended layering is:

```text
unittest suite
  -> fast deterministic Python regression checks

eval --no-build
  -> benchmark-level agent checks

eval --build / generate --build
  -> slower compile smoke checks

manual in-game tests
  -> gameplay confirmation
```

## Test Isolation

Tests create temporary workspaces under `.tmp` and clean them up automatically. They do not depend on existing generated folders under `workspace/`.

## 中文说明

V1.3 的目标是把之前靠手动命令验证的关键链路，沉淀成可以一键运行的自动化回归测试。

运行命令：

```powershell
Set-Location L:\projects\MinecraftMods\idea
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest discover -s tests -v
```

这套测试默认不跑 Gradle build，因为 build 比较慢，也更依赖本机 Java/Gradle 环境。它主要负责快速验证 Python 侧的确定性链路：

- 生成是否成功
- audit 是否能发现问题
- Agent 编排是否能跑通
- Eval 指标是否正确
- CLI 参数是否能解析

如果要做更强的验证，再运行 `docs/历史档案/test-matrix.md` 里的 build smoke 命令。
