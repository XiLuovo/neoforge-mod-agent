# Failure -> Audit -> Repair -> Pass Demo

> 文档定位：这是失败修复演示专项材料，不是主学习入口。需要准备 failure -> audit -> repair -> pass 的演示时再读。

这是自修复 demo 专项材料。它不是普通 happy path，而是主动破坏生成产物，再证明系统能发现、解释、修复并重新通过。

推荐证据结构见 [failure-repair-evidence-summary.md](failure-repair-evidence-summary.md)。那里整理了 `break_recipe_reference` 和 `pack.mcmeta structured patch` 两条展示 case。

## 一键运行

```powershell
.\scripts\failure_repair_demo.ps1
```

默认 case 是 `delete_model`：

```text
生成一个干净 ruby workspace
  -> 删除生成的 assets/<modid>/models/item/ruby.json
  -> audit 发现 item model 缺失
  -> repair RAG 检索 assets / models / textures 相关知识
  -> repair-loop 根据 .agent/modspec.json 重新生成托管文件
  -> final audit 再次通过
```

如果要换故障类型：

```powershell
.\scripts\failure_repair_demo.ps1 -Case delete_texture
.\scripts\failure_repair_demo.ps1 -Case delete_worldgen_json
.\scripts\failure_repair_demo.ps1 -Case delete_behavior_java
.\scripts\failure_repair_demo.ps1 -Case break_recipe_reference
```

如果想把 Gradle build 也放进 repair-loop 验收：

```powershell
.\scripts\failure_repair_demo.ps1 -Build
```

## 当前推荐展示 case

```powershell
.\scripts\failure_repair_demo.ps1 -RunName repair-recipe-failure-demo -Case break_recipe_reference
```

这条 case 展示 recipe 引用错误如何被 audit 检出，并通过 RAG + managed-file regeneration 修复。关键产物：

```text
workspace/failure-repair-demos/repair-recipe-failure-demo/.agent/failure-repair-demo-report.md
workspace/failure-repair-demos/repair-recipe-failure-demo/.agent/failure-repair-demo-report.json
workspace/failure-lab-runs/repair-recipe-failure-demo/.agent/failure-lab-report.md
workspace/failure-lab-runs/repair-recipe-failure-demo/workspaces/break_recipe_reference/.agent/audit-report.json
workspace/failure-lab-runs/repair-recipe-failure-demo/workspaces/break_recipe_reference/.agent/repair-rag-context.md
workspace/failure-lab-runs/repair-recipe-failure-demo/workspaces/break_recipe_reference/.agent/repair-loop-report.md
```

第二条推荐展示的 tool-calling structured patch case：

```powershell
py -3.11 -m agent.cli agent repair workspace\packformat-tool-demo --goal "Fix pack.mcmeta audit failure using safe structured patches, then rerun audit." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
```

这条 case 展示 `pack.mcmeta` 类型错误如何通过 `retrieve_rag -> read_file -> apply_structured_patch -> run_audit -> finish` 修复，并留下 snapshot / rollback evidence。关键产物：

```text
workspace/packformat-tool-demo/.agent/agent-run.md
workspace/packformat-tool-demo/.agent/tool-call-trace.json
workspace/packformat-tool-demo/.agent/structured-patch-diff.md
workspace/packformat-tool-demo/.agent/structured-patch-report.json
workspace/packformat-tool-demo/.agent/structured-patch-rollback-report.json
workspace/packformat-tool-demo/.agent/audit-report.json
```

## 证据讲解顺序

1. 先打开 [failure-repair-evidence-summary.md](failure-repair-evidence-summary.md)，说明两个 case 的差异：一个是 managed-file regeneration，一个是 structured patch。
2. 展示 recipe case：`initial_audit_success = false`、detected issue 为 `recipe:ruby_axe:json_key:R`、repair RAG 命中 5 条上下文、`final_audit_success = true`。
3. 展示 pack metadata case：tool trace 包含 `retrieve_rag`、`read_file`、`apply_structured_patch`、`run_audit`、`finish`。
4. 打开 `structured-patch-diff.md`，说明 patch 只把 `"pack_format": "BROKEN"` 改回 `"pack_format": 61`。
5. 打开 rollback report，说明修复不是不可追踪的直接覆盖。
6. 收束到边界：默认不跑 Gradle build，也不等价于 Minecraft 客户端内 runtime 自动化测试。

## 项目讲解口径

> 这两条失败注入 demo 不只覆盖成功样例。第一个把 recipe JSON 的材料引用改坏，audit 能定位到 `recipe:ruby_axe:json_key:R`，repair RAG 给出相关知识，repair-loop 再根据 `.agent/modspec.json` 重生成 managed files，最后 audit 通过。第二个把 `pack.mcmeta` 的 `pack_format` 改成字符串，tool-calling repair loop 依次检索 RAG、读文件、应用 structured patch、复跑 audit，并留下 snapshot 和 rollback evidence。这能证明系统有观察、诊断、受控修复和可追溯验收闭环。

## 边界

- 默认只修复 generator 管理的文件，不让 LLM 随便 patch Java。
- demo workspace 只写在 `workspace/failure-lab-runs/<run-id>/` 和 `workspace/failure-repair-demos/<run-id>/`。
- 默认不跑 Gradle build；需要更强验收时使用 `-Build`。
