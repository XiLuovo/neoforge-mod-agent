## V8 Resource Quality Upgrade

目标：把资源从“只有占位图”推进到“可描述、可审计、可预览”的质量层，为后续材质 profile、模型 variant、结构预览图和 dashboard 可视化打基础。

完成内容：

- package metadata 更新到 `8.0.0`。
- `texture-manifest.json` 的每条 texture 新增 `quality_profile`、主色 `dominant_rgba` 和 `palette`。
- 新增 `.agent/resource-quality-report.json` 和 `.agent/resource-quality-report.md`，汇总 texture profile、模型 variant、结构预览和 dashboard-ready 摘要。
- 新增 `.agent/texture-atlas.png`，把生成贴图拼成静态像素 atlas，方便 dashboard 和作品集快速查看。
- 对 `structure` DSL 生成 `.agent/previews/<structure>.png` 俯视示意图，作为结构预览证据。
- `audit` 新增 V8 resource quality 检查，验证 report、atlas 和结构预览 PNG。
- `dashboard` 新增 `Resource Preview` 区块，展示 atlas、profile 统计、模型 variant 数量和结构预览图。
- 能力矩阵新增 `resource_quality_profiles`、`texture_atlas_preview`、`model_variant_report`、`structure_preview`、`dashboard_resource_preview` 和 `resource_quality_audit`。
- 新增示例 `examples/resource_quality_showcase.json` 和文档 `docs/规格与生成/resource-quality-upgrade.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_generation_audit tests.test_dashboard tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\resource_quality_showcase.json --workspace-name v80-resource-smoke --overwrite --audit --no-build --json
py -3.11 -m agent.cli dashboard --run-name v80-resource-dashboard --json
```

边界：

- V8 仍是确定性程序化资源，不是最终美术资源。
- `texture-atlas.png` 和结构预览图用于展示与审计，不是游戏内 runtime 资源。
- 结构预览是 schematic PNG，不是 NBT 结构渲染。
- 后续接 AI 贴图、用户贴图或真实结构截图时，应继续沿用 report / manifest 接口。
