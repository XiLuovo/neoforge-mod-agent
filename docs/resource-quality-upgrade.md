# V8 Resource Quality Upgrade

> 文档定位：这是资源质量升级专项材料，不是主学习入口。需要理解贴图、资源预览和质量报告时再读。

V8 的目标不是一下子把程序化材质变成最终美术，而是先把“资源质量”纳入可描述、可审计、可展示的生成闭环。

它仍然遵守项目边界：LLM / rules 只输出结构化 `ModSpec`，确定性生成器输出 Java、JSON、PNG、resources 和 `.agent` 证据文件。V8 不引入外部图像生成，不安装依赖，也不让 LLM 直接写 PNG 字节。

这句话描述的是 V8 resource quality 这个功能层的稳定路径边界，不否定 V8.4+ 的 `ModSpec-first hybrid` 架构。当前全局边界以 [project-limitations.md](project-limitations.md)、[direct-code-lane.md](direct-code-lane.md) 和 [agent-workflow.md](agent-workflow.md) 为准。

## 生成内容

每次生成工作区时，资产生成器会在原有 `.agent/texture-manifest.json` 之外新增：

```text
.agent/resource-quality-report.json
.agent/resource-quality-report.md
.agent/texture-atlas.png
.agent/previews/<structure>.png
```

其中：

- `resource-quality-report.json`：记录 V8 schema、材质 profile、主色板、模型 variant 覆盖、结构预览图路径和 dashboard-ready 摘要。
- `texture-atlas.png`：把当前工作区的 16x16 PNG 贴图拼成一个像素风 atlas，用于 dashboard 或作品集快速预览。
- `.agent/previews/<structure>.png`：为 `structure` DSL 生成确定性俯视示意图，作为结构预览证据。
- `resource-quality-report.md`：面试和人工检查时可读的资源质量摘要。

## Texture Profile

每条 manifest texture 现在会带一个 `quality_profile`：

```json
{
  "type": "item",
  "id": "ruby",
  "path": "src/main/resources/assets/resource_mod/textures/item/ruby.png",
  "template": "gem",
  "quality_profile": {
    "profile_id": "gem_cut",
    "feature_type": "item",
    "silhouette": "faceted_item",
    "shading": "outline_shadow_highlight",
    "detail": "white sparkle pixels",
    "resolution": "16x16",
    "quality_gate": "valid_png_profiled"
  },
  "dominant_rgba": [189, 36, 79, 255],
  "palette": {
    "shadow": "#901f4a",
    "base": "#bd244f",
    "highlight": "#e74c77"
  }
}
```

这让后续升级有稳定接口：可以替换某个 profile 的生成器，或把 profile 交给受控图像资产流程，而不会破坏资源路径、模型引用和 audit。

## Model Variant Report

V8 会把方块模型变体写入 `resource-quality-report.json`：

```json
{
  "id": "polished_ruby_stairs",
  "type": "block",
  "block_kind": "stairs",
  "variant_roles": ["straight", "inner", "outer", "top_bottom_state"],
  "variant_count": 4,
  "model_files": [
    "src/main/resources/assets/resource_mod/models/block/polished_ruby_stairs.json",
    "src/main/resources/assets/resource_mod/models/block/polished_ruby_stairs_inner.json",
    "src/main/resources/assets/resource_mod/models/block/polished_ruby_stairs_outer.json"
  ]
}
```

这一步把“有模型 JSON”升级成“能解释生成了哪些视觉状态”。

## Dashboard Preview

静态 dashboard 会读取 showcase 生成工作区里的 `.agent/resource-quality-report.json`，新增 `Resource Preview` 区块：

- texture atlas 直接嵌入页面。
- 展示 profile 数量、模型 variant 数量和结构预览数量。
- 提供 `resource-quality-report.json` 和 `texture-atlas.png` 链接。

运行：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m agent.cli dashboard --run-name v80-resource-dashboard --json
```

打开：

```text
workspace/dashboard-runs/v80-resource-dashboard/index.html
```

## 快速验证

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_generation_audit tests.test_dashboard tests.test_capabilities -v
py -3.11 -m agent.cli generate-from-spec .\examples\resource_quality_showcase.json --workspace-name v80-resource-smoke --overwrite --audit --no-build --json
```

关键证据：

```text
workspace/v80-resource-smoke/.agent/resource-quality-report.json
workspace/v80-resource-smoke/.agent/resource-quality-report.md
workspace/v80-resource-smoke/.agent/texture-atlas.png
workspace/v80-resource-smoke/.agent/previews/ruby_gallery.png
workspace/v80-resource-smoke/.agent/audit-report.json
```

## 当前边界

- V8 仍是确定性程序化资源，不是最终美术资源。
- `texture-atlas.png` 和结构预览图用于展示与审计，不是游戏内 runtime 资源。
- 结构预览是俯视示意图，不是 NBT 结构渲染，也不代表完整建筑生成。
- 后续如果接 AI 贴图或真实结构截图，建议保留现在的 report/manifest 接口，把新资源作为 profile 后端替换进去。
