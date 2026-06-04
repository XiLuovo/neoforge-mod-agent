# Capability Harvest Loop

> 文档定位：这是 Capability Harvest Loop / Free-Code Lab 机制真相源。实验通道、manual checklist、harvest candidate 和固化闭环以本文为准。

## Summary

Capability Harvest Loop 是 V8.5 之后的后续主线：当稳定 `generate` 覆盖不了需求时，不急着把 LLM 变成无边界 coding agent，而是先让它在隔离 workspace 里实验；实验通过自动检查和人工 runtime checklist 后，再把成功模式整理成稳定的 `ModSpec` / DSL / generator / audit / repair / test 能力。

```text
generate gap
  -> Free-Code Lab experimental workspace
  -> audit / optional build / manual runtime checklist
  -> harvest candidate
  -> reviewed generator upgrade
  -> regression tests
  -> stable generate capability
```

## Free-Code Lab

实验命令：

```powershell
py -3.11 -m agent.cli agent lab-generate "<request>" --from-workspace <workspace> --run-name <name> --build --json
```

行为边界：

- 复制已有 generated workspace 到 `workspace/free-code-lab-runs/<run-name>/workspace`。
- 只在复制出来的 lab workspace 内应用实验补丁。
- 不修改原 workspace。
- 不修改 `neoforge-mod-agent` 工具源码。
- 不把成功样本自动写回 generator。
- 第一版仍使用结构化 `write_file` / `replace_text` 操作，便于审计和回放。

输出证据：

```text
workspace/free-code-lab-runs/<run-name>/.agent/free-code-plan.json
workspace/free-code-lab-runs/<run-name>/.agent/free-code-plan.md
workspace/free-code-lab-runs/<run-name>/.agent/free-code-diff.md
workspace/free-code-lab-runs/<run-name>/.agent/free-code-report.json
workspace/free-code-lab-runs/<run-name>/.agent/manual-runtime-checklist.md
workspace/free-code-lab-runs/<run-name>/.agent/harvest-candidate.json
```

## Manual Runtime Checklist

`manual-runtime-checklist.md` 用来把人工游戏内测试结构化。至少要确认：

- 游戏能否启动。
- 能否创建或进入世界。
- 创造物品栏是否出现目标物品或方块。
- 方块能否放置、破坏、掉落。
- GUI 能否打开。
- 配方是否可用。
- 服务端和客户端是否无崩溃。
- 日志是否有明显 error。

没有人工 runtime 通过证据的实验样本，不能直接标记为 `harvest_into_generator`。

## Harvest Candidate

`harvest-candidate.json` 记录这次实验解决了哪个 generate gap，以及建议沉淀方向：

- `modspec_field`
- `dsl`
- `java_generator_template`
- `json_resource_template`
- `audit_rule`
- `repair_rule`

推荐状态：

- `reject`：自动 gate 失败，或缺少关键证据。
- `keep_as_lab_sample`：实验样本可保留，但还不能进入 generator。
- `harvest_into_generator`：人工审查后可进入稳定能力固化流程。

当前实现默认不会自动给出 `harvest_into_generator`，因为真正固化必须有人工 runtime 结论、设计整理和回归测试。

## Harvest Report

汇总命令：

```powershell
py -3.11 -m agent.cli harvest-report --run-name <name> --json
```

输出位置：

```text
workspace/harvest-runs/<run-name>/.agent/harvest-report.json
workspace/harvest-runs/<run-name>/.agent/harvest-report.md
```

它会聚合所有 `workspace/free-code-lab-runs/*/.agent/harvest-candidate.json`，统计候选数量、推荐状态、固化方向和 ready-to-harvest 数量。

## First Harvest Target

第一批固化目标是高级机器 GUI / BlockEntity 能力增强。

原因：

- 项目已有 machine 基础，增量边界清楚。
- 它覆盖 Java、BlockEntity、Menu、Screen、client init、资源 JSON 和 audit。
- 人工 runtime 路径明确：放置机器、打开 GUI、放入物品、观察进度、拿到输出。
- 现有稳定 generator 已经有 `examples/machine_ruby_compressor.json` 和 machine GUI audit 回归测试，可作为第一批固化样本的基准。

后续如果 Free-Code Lab 产出新的机器 GUI 模式，不能直接复制 LLM 代码进主项目；必须整理成确定性 generator 模板，并补 example spec、unit test、audit test、generate smoke test。

## Safety Boundaries

Free-Code Lab 允许实验，但不是自由改仓库：

- 禁止绝对路径和 `..` 路径穿越。
- 禁止 `.git`、`gradle/wrapper`、`build`、`.gradle`。
- 禁止 `.jar`、`.class` 等二进制产物。
- 禁止修改工具项目源码。
- 禁止危险 Java token，例如进程、反射、网络、文件 API。
- 失败样本只写报告和候选，不会进入稳定 generator。

## Learning Value

这条路线能证明项目不是“每次靠 LLM 临时发挥”，而是有能力从实验中学习：

```text
LLM explores
  -> system records evidence
  -> human validates runtime
  -> engineer abstracts pattern
  -> generator reproduces deterministically
  -> tests protect regression
```
