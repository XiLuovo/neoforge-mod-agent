# Programmatic Texture Generation

> 文档定位：这是程序化贴图专项材料，不是主学习入口。需要理解 PNG 生成、贴图审计和资源路径时再读。

V2.3 introduced deterministic programmatic texture generation for generated NeoForge workspaces. V8 keeps that controlled path and adds resource quality profiles, texture atlas previews, model variant reporting, schematic structure previews, and dashboard visualization.

The goal is practical rather than artistic: generated content should have valid in-game textures instead of Minecraft's black/purple missing-texture placeholder. These textures are intentionally simple placeholder art and are not a replacement for final custom art or future AI-generated art.

## Generated Files

For supported features, the asset generator writes `16x16 RGBA PNG` textures under:

```text
src/main/resources/assets/<modid>/textures/item/<id>.png
src/main/resources/assets/<modid>/textures/block/<id>.png
```

It also writes resource evidence under `.agent`:

```text
.agent/texture-manifest.json
.agent/resource-quality-report.json
.agent/resource-quality-report.md
.agent/texture-atlas.png
.agent/previews/<structure>.png
```

Manifest shape:

```json
{
  "version": 1,
  "generator": "procedural_16x16_rgba",
  "mod_id": "ruby_mod",
  "textures": [
    {
      "type": "item",
      "id": "ruby",
      "path": "src/main/resources/assets/ruby_mod/textures/item/ruby.png",
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
      },
      "width": 16,
      "height": 16,
      "color_type": "rgba"
    }
  ]
}
```

## Templates

Current deterministic templates:

- `gem`: default item / gem icon.
- `heal_badge`: item with `right_click_heal`.
- `effect_crystal`: item with `right_click_effect`.
- `apple`: food icon.
- `sword`: sword icon.
- `tool_<type>`: pickaxe, axe, shovel, and hoe icons.
- `armor_<slot>`: helmet, chestplate, leggings, and boots icons.
- `solid_block`: normal block texture.
- `ore_block`: ore block texture.
- `machine_block`: machine front panel texture.
- `mob_face`: entity portrait texture.

Colors are derived from the feature id and display name. Ruby-like content is red, speed/effect content is blue, apple-like content is red, emerald-like content is green, and unknown content falls back to a neutral gray.

## V8 Resource Quality Report

V8 writes `.agent/resource-quality-report.json` as the stable handoff for future resource upgrades:

```json
{
  "version": 8,
  "generator": "deterministic_resource_quality_v8",
  "summary": {
    "textures": 3,
    "model_variant_blocks": 2,
    "model_variants": 4,
    "structure_previews": 1,
    "dashboard_ready": true
  },
  "preview_artifacts": {
    "texture_atlas": {
      "path": ".agent/texture-atlas.png",
      "texture_count": 3,
      "cell_size": 20
    }
  }
}
```

The static dashboard reads this report and renders a `Resource Preview` section with the atlas image, model variant counts, profile tags, and structure preview thumbnails.

## Audit

`audit` now checks:

- `.agent/texture-manifest.json` exists for newly generated workspaces.
- `.agent/resource-quality-report.json` exists for newly generated workspaces.
- manifest JSON contains a `textures` array.
- every manifest texture file exists.
- feature models have corresponding texture PNG files.
- each PNG has a valid PNG signature and `IHDR`.
- each generated texture is `16x16`, 8-bit, RGBA.
- the V8 texture atlas and structure preview PNGs are valid RGBA preview images.

Example:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli generate "做一个红宝石模组，添加红宝石。" --workspace-name v23-texture-ruby --overwrite --no-build --audit --json
py -3.11 -m agent.cli audit workspace/v23-texture-ruby --json
py -3.11 -m agent.cli generate-from-spec .\examples\resource_quality_showcase.json --workspace-name v80-resource-smoke --overwrite --audit --no-build --json
```

If a managed texture is deleted, audit should fail with an error such as:

```text
item:ruby:texture
```

## Repair Loop

Because textures are generated deterministically and recorded as managed files, `repair-loop` can restore missing generated textures:

```powershell
py -3.11 -m agent.cli repair-loop workspace\v23-texture-ruby --max-attempts 1 --no-build --audit --json
```

This keeps the same safety boundary as the rest of the project: the repair loop regenerates managed files from `.agent/modspec.json` and does not ask the LLM to directly edit Java, JSON, or PNG bytes.

## Current Limits

- Textures are placeholder-quality, not final art.
- Textures are generated at `16x16` only.
- The generator creates PNGs directly and does not use external image libraries.
- No LLM image generation is used yet.
- Custom user-provided textures are not interpreted or upgraded by audit.
- Structure previews are schematic top-down PNGs, not NBT structure renders.
