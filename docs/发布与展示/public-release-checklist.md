# Public Release Checklist

这份 checklist 用于公开仓库、作品集附件或展示材料改动前的自检。当前对外主线是 Minecraft NeoForge 领域内的受控 Coding Agent，不是通用 RAG 产品、聊天机器人或无限制 Coding Agent。

## 文档

- README 明确写当前主线是 `Natural language -> ModSpec planner -> deterministic generator -> controlled repair/refine -> reviewer + audit/build -> benchmark/.agent evidence`。
- 公开入口从根目录 [README.md](../../README.md) 开始。
- 主线流程统一为 planner / ModSpec -> generator -> controlled tool-calling loop -> reviewer -> audit/build -> benchmark / RAG ablation -> evidence。
- 旧版本报告不作为公开主线入口。
- local-only 材料不作为架构真相源。

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

首选公开 smoke：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --planner decomposed --llm-provider mock --audit --no-build --run-name public-smoke-decomposed-e2e --json
py -3.11 -m agent.cli showcase --run-name public-build-smoke --llm-provider mock --build --json
```

可选可靠性补充：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent bench --run-name public-rag-ablation-smoke --suite examples/agentic_rag_ablation.json --llm-provider mock --rag-ablation --audit --no-build --json
```

如果 run 名已经存在，最小改动方案是换一个 workspace/run 名；只有明确要重建旧目录时才给 CLI 加 `--overwrite`。

## Evidence

确认 `workspace/eval-runs/<eval-run>/.agent/` 至少能看到：

```text
.agent/eval-report.json
.agent/eval-report.md
```

并从 case workspace 里抽样确认：

```text
.agent/agent-run.json
.agent/agent-run.md
.agent/prompt-trace.json
.agent/agent-trace-summary.json
.agent/audit-report.json
.agent/decomposed-planner/
.agent/decomposed-modify/
```

确认 `workspace/showcase-runs/<showcase-run>/.agent/` 至少能看到：

```text
.agent/showcase-report.json
.agent/showcase-report.md
```

如果该 showcase 使用 `--build`，从 generated workspace 里抽样确认：

```text
.agent/logs/gradle-build.json
build/libs/*.jar
```

如果补跑 RAG ablation，再确认 `workspace/benchmark-runs/<bench-run>/.agent/` 至少能看到：

```text
.agent/agent-benchmark-report.json
.agent/agent-benchmark-report.md
.agent/agent-benchmark-report.html
```

并从 case workspace 里抽样确认：

```text
.agent/tool-call-trace.json
.agent/rag-decision-trace.json
.agent/reviewer-report.json
```

发布包脚本应围绕这些当前主线产物收集 evidence，而不是引用旧的 `v80` / `v81` / `v82` workspace：

```powershell
.\scripts\create_public_release.ps1
```

使用非默认示例名时：

```powershell
.\scripts\create_public_release.ps1 -Rc1WorkspaceName <workspace-name> -Rc1BenchmarkRunName <bench-run-name>
```

当前脚本的 `Rc1*` 参数用于兼容 curated evidence 打包。当前推荐公开 smoke 的 primary evidence 仍以 `workspace/eval-runs/<eval-run>/.agent/` 和 case workspace `.agent/` 为准。

缺失示例产物会进入 `release-manifest.md` 的 Missing Optional Evidence；发布前应先补齐或确认它确实只是可选展示材料。

## 禁止夸大

- 不说“通用 agent”。
- 不说“LLM 自由改代码”。
- 不说“reviewer 代替 audit/build”。
- 不说“已经自动完成 Minecraft runtime 测试”。
