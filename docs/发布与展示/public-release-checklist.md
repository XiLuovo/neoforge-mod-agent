# Public Release Checklist

RC1 已发布；这份 checklist 用于后续文档或展示改动前的自检。

## 文档

- README 明确写 RC1 / Phase 0-4。
- 文档入口从 [../README.md](../README.md) 开始。
- 主线流程统一为 planner / ModSpec -> generator -> real tool-calling loop -> reviewer -> audit/build -> benchmark -> evidence。
- 旧版本报告只在历史档案或辅助能力文档中出现。
- 学习材料不作为架构真相源。

## 测试

```powershell
python -m unittest tests.test_doc_links
python -m unittest discover tests
```

可选：

```powershell
py -3.11 -m compileall src
```

## Smoke

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name rc1-release-smoke --no-build --json
py -3.11 -m agent.cli agent repair rc1-release-smoke --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
py -3.11 -m agent.cli agent bench --run-name rc1-release-bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

如果 `rc1-release-smoke` 或 `rc1-release-bench` 已经存在，最小改动方案是换一个 workspace/run 名，并在打包时传给 `create_public_release.ps1`；只有明确要重建旧目录时才给 CLI 加 `--overwrite`。

## Evidence

确认 `workspace/rc1-release-smoke/.agent/` 至少能看到：

```text
.agent/agent-run.json
.agent/agent-run.md
.agent/agent-repair-plan.json
.agent/tool-call-trace.json
.agent/prompt-trace.json
.agent/rag-context.json
.agent/repair-rag-context.json
.agent/reviewer-report.json
.agent/audit-report.json
.agent/structured-patch-report.json
.agent/structured-patch-rollback-report.json
```

确认 `workspace/benchmark-runs/rc1-release-bench/.agent/` 至少能看到：

```text
.agent/agent-benchmark-report.json
.agent/agent-benchmark-report.md
.agent/agent-benchmark-report.html
```

发布包脚本应围绕这些当前 RC1 主线产物收集 evidence，而不是引用旧的 `v80` / `v81` / `v82` workspace：

```powershell
.\scripts\create_public_release.ps1
```

使用非默认示例名时：

```powershell
.\scripts\create_public_release.ps1 -Rc1WorkspaceName <workspace-name> -Rc1BenchmarkRunName <bench-run-name>
```

缺失示例产物会进入 `release-manifest.md` 的 Missing Optional Evidence；发布前应先补齐或确认它确实只是可选展示材料。

## 禁止夸大

- 不说“通用 agent”。
- 不说“LLM 自由改代码”。
- 不说“reviewer 代替 audit/build”。
- 不说“已经自动完成 Minecraft runtime 测试”。
