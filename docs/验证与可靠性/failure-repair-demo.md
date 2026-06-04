# Failure -> Audit -> Repair -> Pass Demo

> 文档定位：这是失败修复演示专项材料，不是主学习入口。需要准备 failure -> audit -> repair -> pass 的演示时再读。

这是一条专门给面试展示用的自修复 demo case。它不是普通 happy path，而是主动破坏生成产物，再证明系统能发现、解释、修复并重新通过。

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
.\scripts\failure_repair_demo.ps1 -RunName v80-failure-repair-demo -Case delete_model
```

关键产物：

```text
workspace/failure-repair-demos/v80-failure-repair-demo/.agent/failure-repair-demo-report.md
workspace/failure-repair-demos/v80-failure-repair-demo/.agent/failure-repair-demo-report.json
workspace/failure-lab-runs/v80-failure-repair-demo/.agent/failure-lab-report.md
workspace/failure-lab-runs/v80-failure-repair-demo/workspaces/delete_model/.agent/audit-report.json
workspace/failure-lab-runs/v80-failure-repair-demo/workspaces/delete_model/.agent/repair-rag-context.md
workspace/failure-lab-runs/v80-failure-repair-demo/workspaces/delete_model/.agent/repair-loop-report.md
```

## 面试讲解顺序

1. 打开 compact report，先看六个阶段是否都通过。
2. 打开 initial audit report，说明系统不是靠人工肉眼发现问题，而是结构化检测到缺失的 model 引用。
3. 打开 repair RAG report，说明系统能把错误映射到相关知识，不只是盲目重跑。
4. 打开 repair-loop report，说明修复动作是保守的：从 `.agent/modspec.json` 重生成 managed files。
5. 回到 compact report，看 `final_audit_success = true`，完成闭环。

## 面试可用说法

> 我准备了一个失败注入 demo：系统先生成干净项目，然后故意删除一个 item model。audit 会检测到模型资源缺失，repair RAG 会检索相关资源生成知识，repair-loop 再根据 `ModSpec` 重新生成受控文件，最后 audit 重新通过。这个 case 用来证明项目不是只能跑成功样例，而是有故障诊断和自修复闭环。

## 边界

- 默认只修复 generator 管理的文件，不让 LLM 随便 patch Java。
- demo workspace 只写在 `workspace/failure-lab-runs/<run-id>/` 和 `workspace/failure-repair-demos/<run-id>/`。
- 默认不跑 Gradle build；需要更强验收时使用 `-Build`。
