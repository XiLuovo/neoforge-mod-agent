# Failure Lab / 故障注入测试

> 文档定位：这是 failure lab 专项材料，不是主学习入口。需要理解如何主动制造坏 workspace 并验证修复能力时再读。

Failure Lab 用来证明 NeoForge Mod Agent 不只是 happy path demo。它会自动生成干净项目、制造典型坏项目、运行 audit、生成 repair RAG 证据，并用 repair-loop 验证 managed files 可以被安全恢复。

## 运行命令

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli failure-lab --run-name v44-failure-lab --json
```

专项演示推荐使用更聚焦的一键脚本，它会只跑一个 case，并额外生成 compact report：

```powershell
.\scripts\failure_repair_demo.ps1 -RunName v80-failure-repair-demo -Case delete_model
```

只跑单个 case：

```powershell
py -3.11 -m agent.cli failure-lab --case delete_texture --json
py -3.11 -m agent.cli failure-lab --case break_recipe_reference --json
```

## 默认故障

- `delete_texture`：删除 `textures/item/ruby.png`。
- `delete_model`：删除 `models/item/ruby.json`。
- `delete_worldgen_json`：删除 `worldgen/configured_feature/ruby_ore.json`。
- `delete_behavior_java`：删除 `RubyCharmItem.java`。
- `break_recipe_reference`：把实际 recipe JSON 里的引用改成不存在的 `<modid>:missing_failure_lab_material`。

## 每个 case 的闭环

```text
generate clean workspace
  -> inject one fault
  -> audit detects expected failure
  -> repair RAG retrieves relevant knowledge
  -> repair-loop regenerates managed files from .agent/modspec.json
  -> final audit passes
```

## 产物路径

```text
workspace/failure-lab-runs/<run-id>/.agent/failure-lab-report.json
workspace/failure-lab-runs/<run-id>/.agent/failure-lab-report.md
workspace/failure-lab-runs/<run-id>/workspaces/<case-id>/.agent/audit-report.json
workspace/failure-lab-runs/<run-id>/workspaces/<case-id>/.agent/repair-rag-context.json
workspace/failure-lab-runs/<run-id>/workspaces/<case-id>/.agent/repair-rag-context.md
workspace/failure-lab-runs/<run-id>/workspaces/<case-id>/.agent/repair-loop-report.json
workspace/failure-lab-runs/<run-id>/workspaces/<case-id>/.agent/repair-loop-report.md
```

## 边界

- Failure Lab 的坏项目只生成在 `workspace/failure-lab-runs/<run-id>/workspaces` 下。
- RAG 只负责解释和提供证据，不直接修改文件。
- repair-loop 只重生成 generator 管理的文件，不扫描 Java 反推状态。
- 默认不跑 Gradle build；需要时可加 `--build`，但会更慢。
