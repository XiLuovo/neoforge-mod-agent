# 失败修复证据总览

这页汇总失败注入和自修复演示的推荐证据结构，用于项目说明和展示复盘。实际 `.agent` 报告应以本地重新运行后的 `workspace/` 产物为准；本页只做可读整理，不替代原始 JSON。

## 一句话结论

项目已经准备好两个可复现失败案例：一个展示 recipe 引用错误如何被 audit 检出并通过 managed-file regeneration 恢复；另一个展示 tool-calling repair loop 如何检索 RAG、读取文件、执行 structured patch、复跑 audit，并留下 rollback evidence。建议使用下方中性 run name 重新生成本地 evidence。

## 证据清单

| Case | 故障 | 检出 | 修复方式 | 最终结果 |
| --- | --- | --- | --- | --- |
| `repair-recipe-failure-demo` | 将 `ruby_axe.json` 的 recipe key 引用改成不存在的 `ruby_mod:missing_failure_lab_material` | audit 报 `recipe:ruby_axe:json_key:R` | repair RAG + repair-loop 从 `.agent/modspec.json` 重生成 managed files | final audit success: `true` |
| `packformat-tool-demo` | 将 `pack.mcmeta` 的 `pack_format` 从整数 `61` 改成字符串 `"BROKEN"` | audit 报 `project:pack_mcmeta:pack_format` | tool-calling loop 执行 `retrieve_rag -> read_file -> apply_structured_patch -> run_audit -> finish` | final audit success: `true` |

## Recipe 引用错误 Case

运行命令：

```powershell
.\scripts\failure_repair_demo.ps1 -RunName repair-recipe-failure-demo -Case break_recipe_reference
```

故障注入：

```text
src/main/resources/data/ruby_mod/recipe/ruby_axe.json
```

被改成引用不存在的材料：

```text
ruby_mod:missing_failure_lab_material
```

关键结果：

- generation success: `true`
- fault injected: `true`
- initial audit success: `false`
- detected issue: `recipe:ruby_axe:json_key:R`
- repair RAG hits: `5`
- repair RAG relevant: `true`
- repair success: `true`
- repair attempts: `2`
- regenerated managed file entries: `31`
- final audit success: `true`

参考证据路径（按上述命令运行后）：

```text
L:/projects/MinecraftMods/idea-copy-copy/workspace/failure-repair-demos/repair-recipe-failure-demo/.agent/failure-repair-demo-report.md
L:/projects/MinecraftMods/idea-copy-copy/workspace/failure-lab-runs/repair-recipe-failure-demo/.agent/failure-lab-report.md
L:/projects/MinecraftMods/idea-copy-copy/workspace/failure-lab-runs/repair-recipe-failure-demo/workspaces/break_recipe_reference/.agent/audit-report.json
L:/projects/MinecraftMods/idea-copy-copy/workspace/failure-lab-runs/repair-recipe-failure-demo/workspaces/break_recipe_reference/.agent/repair-rag-context.md
L:/projects/MinecraftMods/idea-copy-copy/workspace/failure-lab-runs/repair-recipe-failure-demo/workspaces/break_recipe_reference/.agent/repair-loop-report.md
```

这条 case 适合说明：项目不是只能跑 happy path。它能主动制造坏 workspace，用 deterministic audit 检出引用错误，再通过 RAG 和 managed-file regeneration 恢复。

## Tool-calling Structured Patch Case

生成干净 workspace：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent generate "Create a ruby mod with ruby." --planner llm --llm-provider mock --workspace-name packformat-tool-demo --overwrite --no-build --json
```

故障注入：

```json
{
  "pack": {
    "description": "ruby_mod resources",
    "pack_format": "BROKEN"
  }
}
```

initial audit 检出：

```text
id: project:pack_mcmeta:pack_format
message: pack.mcmeta missing integer pack.pack_format
errors_count: 1
```

修复命令：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent repair workspace\packformat-tool-demo --goal "Fix pack.mcmeta audit failure using safe structured patches, then rerun audit." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
```

tool trace：

```text
1: retrieve_rag -> Retrieved 5 RAG snippet(s).
2: read_file -> Read 6 line(s) from src/main/resources/pack.mcmeta.
3: apply_structured_patch -> Applied structured patch to 1 file(s).
4: run_audit -> Workspace audit passed.
5: finish -> Audit/build observations pass.
```

structured patch diff：

```diff
--- a/src/main/resources/pack.mcmeta
+++ b/src/main/resources/pack.mcmeta
@@ -1,6 +1,6 @@
 {
   "pack": {
     "description": "ruby_mod resources",
-    "pack_format": "BROKEN"
+    "pack_format": 61
   }
 }
```

关键结果：

- repair success: `true`
- tool calls count: `5`
- changed files: `src/main/resources/pack.mcmeta`
- snapshot written: `true`
- rollback evidence written: `true`
- reviewer decision: `approve`
- final audit success: `true`
- final audit errors: `0`

参考证据路径（按上述命令运行后）：

```text
L:/projects/MinecraftMods/idea-copy-copy/workspace/packformat-tool-demo/.agent/agent-run.md
L:/projects/MinecraftMods/idea-copy-copy/workspace/packformat-tool-demo/.agent/tool-call-trace.json
L:/projects/MinecraftMods/idea-copy-copy/workspace/packformat-tool-demo/.agent/structured-patch-diff.md
L:/projects/MinecraftMods/idea-copy-copy/workspace/packformat-tool-demo/.agent/structured-patch-report.json
L:/projects/MinecraftMods/idea-copy-copy/workspace/packformat-tool-demo/.agent/structured-patch-rollback-report.json
L:/projects/MinecraftMods/idea-copy-copy/workspace/packformat-tool-demo/.agent/reviewer-report.json
L:/projects/MinecraftMods/idea-copy-copy/workspace/packformat-tool-demo/.agent/audit-report.json
```

这条 case 适合说明：repair/refine 不是自由 diff。LLM 只能选择受控工具，patch 只能落在 workspace 内允许路径，写前有 snapshot，写后有 patch report、rollback report 和 deterministic audit gate。

## 证据讲解顺序

1. 先打开本页，讲两个 case 的差异：recipe case 展示 managed-file regeneration，pack metadata case 展示 tool-calling structured patch。
2. 展示 recipe case 的 `initial audit success=false`、`detected issue=recipe:ruby_axe:json_key:R`、`final audit success=true`。
3. 展示 structured patch case 的 5 个 tool action，强调 LLM 没有自由改文件。
4. 展示 patch diff，只改了 `pack_format` 一行。
5. 展示 rollback evidence，说明修复不是不可追踪的直接覆盖。
6. 收束到边界：这次默认没有跑 Gradle build，也不等价于 Minecraft 客户端内 runtime 自动化测试。

## 项目讲解口径

可以这样讲：

> 失败注入 demo 不只展示 happy path。第一个 case 把 recipe JSON 的材料引用改坏，audit 能定位到 `recipe:ruby_axe:json_key:R`，repair RAG 给出相关知识，repair-loop 再根据 `.agent/modspec.json` 重生成 managed files，最后 audit 通过。第二个 case 把 `pack.mcmeta` 的 `pack_format` 改成字符串，tool-calling repair loop 依次检索 RAG、读文件、应用 structured patch、复跑 audit，并留下 snapshot 和 rollback evidence。这个用来证明系统有观察、诊断、受控修复和可追溯验收闭环。

## 没有声称的部分

- 这两条演示默认没有跑 Gradle build；需要更强验收时可以加 `-Build` 或单独跑 build。
- audit/build 仍不能替代 Minecraft 客户端内真实 runtime 自动化测试。
- recipe case 的修复方式是 managed-file regeneration；structured patch case 才是展示 `apply_structured_patch` 的主证据。
