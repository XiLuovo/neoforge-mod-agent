# V2.1 Repair Loop

> 文档定位：这是 repair-loop 专项材料，不是主学习入口。需要理解 managed files 如何安全重生成时再读。

## V3.7 Agent Integration

V3.7 keeps the standalone `repair-loop` command, and also lets `repair_agent` call it automatically from `agent generate` / `agent modify`.

When audit or build fails inside an agent run, the repair agent now:

```text
classifies root causes
  -> writes agent repair plan
  -> runs safe repair-loop once
  -> reruns the requested audit/build checks
  -> stores repair-loop result inside agent-run.json
```

The automatic action is still conservative: regenerate managed files from `.agent/modspec.json`. It does not let the LLM patch generated Java, JSON, PNG, or Gradle files directly.

Additional artifacts:

```text
.agent/agent-repair-plan.json
.agent/agent-repair-plan.md
.agent/repair-loop-report.json
.agent/repair-loop-report.md
```

V2.1 adds a safe automatic repair loop for generated workspaces.

## Goal

The repair loop is intentionally conservative:

```text
audit/build check
  -> if failed, regenerate managed files from .agent/modspec.json
  -> audit/build check again
  -> write repair-loop report
```

It does not ask an LLM to directly edit Java. The only automatic repair action in V2.1 is:

```text
regenerate_managed_files
```

That means the runner restores files controlled by the generator, such as Java sources, models, textures, language files, loot tables, tags, worldgen JSON, and `pack.mcmeta`.

## Command

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli repair-loop workspace\v21-repair-loop --max-attempts 1 --no-build --json
```

To include Gradle build verification in each check:

```powershell
py -3.11 -m agent.cli repair-loop workspace\v21-repair-loop --max-attempts 1 --build --json
```

## Artifacts

The command writes:

```text
.agent/repair-loop-report.json
.agent/repair-loop-report.md
```

If Gradle build fails, the existing repair artifacts may also be written:

```text
.agent/debug-context.md
.agent/fix-request.md
.agent/suspected-errors.json
```

## 中文说明

V2.1 的重点是“安全自动修复”，不是让 LLM 随便改源码。

当 audit 或 build 失败时，repair loop 会先做一件确定性、低风险的事：

```text
根据 .agent/modspec.json 重新生成受控文件
```

这可以修复很多常见问题，例如：

- 用户误删了生成的 item model。
- 用户误删了 lang 文件。
- 用户误删了 worldgen JSON。
- 生成产物和 `generation-summary.json` 不一致。

如果重新生成后仍然失败，系统会保留结构化报告，方便下一步人工修复或后续 V2.2/V2.3 接入更强的修复策略。
