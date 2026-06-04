# 公开版发布清单

> 文档定位：这是公开发布检查清单，不是主学习入口。准备公开仓库或发布包时再读。

这份清单用于把当前开发目录整理成可以放到公开仓库或发布包里的版本。原则是保留源码、模板、测试、文档和精选证据，不把本地生成区和缓存区一起打包。

## 发布包内容

默认发布脚本会保留：

- `src/`：Agent runtime、NeoForge domain plugin、generator、audit、repair、benchmark、replay 等源码。
- `templates/` 与 `examplemod-template-26.1.2/`：NeoForge 26.1 模板与参考项目。
- `examples/`：可复现的 `ModSpec` 示例。
- `tests/`：单元测试与回归测试。
- `docs/`：架构、演示、真实 LLM、失败修复、benchmark、replay 和发布材料。
- `scripts/`：一键 demo、失败修复 demo、公开版打包脚本。
- `.github/`、`README.md`、`pyproject.toml`、`.gitignore`、`TASK.md`。

默认排除：

- `workspace/`：生成出来的 demo、eval、benchmark、build 和 runtime 验证工作区。
- `.gradle-user-home/`、`.gradle-default-user-home/`：本机 Gradle 依赖缓存。
- `.tmp/`、`dist/`、`.pytest_cache/`、`__pycache__/`、`*.pyc`。
- `.codex/`、`.playwright-mcp/` 等本地工具状态。

## 打包命令

```powershell
.\scripts\create_public_release.ps1
```

输出：

```text
dist/<release-name>/
dist/<release-name>.zip
dist/<release-name>/release-manifest.json
dist/<release-name>/release-manifest.md
```

如果要覆盖同名产物：

```powershell
.\scripts\create_public_release.ps1 -ReleaseName neoforge-mod-agent-public-local -Overwrite
```

如果只想生成目录、不压缩：

```powershell
.\scripts\create_public_release.ps1 -NoZip
```

## 精选证据

发布脚本不会复制完整 `workspace/`，只会在存在时复制以下小体积证据到 `release-artifacts/evidence/`：

- session replay viewer：`agent-run-replay.html`
- benchmark report：`benchmark-report.html`、`benchmark-report.json`、`benchmark-report.md`
- evidence chain：`evidence-chain-report.json`、`evidence-chain-report.md`
- resource quality：`resource-quality-report.md`、`texture-atlas.png`、结构预览 PNG
- failure repair：failure lab report、repair eval report

这样公开仓库可以展示完整工程链路，同时避免把 GB 级生成产物提交出去。

## 发布前验证

建议在打包前跑：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m compileall -q src tests
py -3.11 -m unittest discover -s tests -v
```

打包后检查压缩包内不应包含大目录：

```powershell
Expand-Archive .\dist\<release-name>.zip .\.tmp\release-check -Force
Get-ChildItem .\.tmp\release-check -Recurse -Directory |
  Where-Object { $_.Name -in @("workspace", ".gradle-user-home", ".gradle-default-user-home", ".tmp") }
```

上面命令应该没有输出。

## 本地 workspace 清理

`workspace/` 里的历史运行证据对开发和测试不是必需的，但里面可能包含你想保留的演示结果。公开发布前推荐先用打包脚本生成干净 release artifact，再决定是否手动归档或删除旧 workspace。

不要把整个 `workspace/`、Gradle cache 或 `.tmp/` 作为公开仓库内容提交。
