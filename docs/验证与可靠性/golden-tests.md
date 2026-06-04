# Golden Tests

> 文档定位：这是 golden tests 专项材料，不是主学习入口。需要理解快照回归和生成稳定性时再读。

V2.9 新增 `golden-test`，用于做 deterministic golden snapshot 验收。它不是新的生成路径，也不依赖真实 LLM，而是用固定提示生成标准 workspace，再检查生成结果是否符合预期。

## 命令

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli golden-test --run-name v29-golden --json
```

可选只跑前 N 个 case：

```powershell
py -3.11 -m agent.cli golden-test --run-name v29-golden-smoke --limit 2 --json
```

## 覆盖范围

- `basic_ruby_item`
- `ruby_block`
- `ruby_charm_behavior`
- `ruby_food_effect`
- `ruby_sword_ignite`
- `ruby_ore_worldgen`
- `ruby_tool_set`
- `ruby_armor_set`
- `ruby_block_variants`

这些 case 覆盖当前主要内容能力：item、block、ore、food、sword、tool、armor、recipe、behavior、worldgen、程序化贴图、pack metadata 和 V2.8 方块变体。

## 检查内容

- 生成是否成功。
- `.agent/modspec.json` 是否包含期望 feature id。
- `generation-summary.json` 中的 `generated_files` 数量是否达到下限。
- 关键文件是否真实存在，并且是否被 `generation-summary.json` 记录。
- 关键 JSON 字段是否符合预期，例如 item model parent、recipe result、worldgen configured/placed/biome modifier 字段。
- 生成后的 workspace 是否通过 `audit`。

## 产物

```text
workspace/golden-runs/<run-id>/.agent/golden-cases.json
workspace/golden-runs/<run-id>/.agent/golden-report.json
workspace/golden-runs/<run-id>/.agent/golden-report.md
workspace/golden-runs/<run-id>/workspaces/
```

## 与 Quality Gate 的关系

V2.9 开始，`quality-gate` 默认运行 golden tests：

```powershell
py -3.11 -m agent.cli quality-gate --run-name v29-quality-gate --json
```

如果只想快速跑其他检查，可以跳过：

```powershell
py -3.11 -m agent.cli quality-gate --run-name v29-no-golden --no-golden --json
```
