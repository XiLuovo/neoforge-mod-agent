## V5.2 BlockEntity + GUI

目标：把 V5.1 的“行为可组合”继续推进到“方块有状态、有容器、有界面”，让生成器能产出熔炉类机器、压缩机、升级台、魔法祭坛和储物方块这类更接近真实 Mod 的内容。

完成内容：
- package metadata 更新到 `5.2.0`。
- `ModSpec` 新增 `machine` / `machines`，覆盖 `machine_kind`、槽位数、能量容量、每 tick 能耗、最大进度和菜单标题。
- 新增 `MachineGenerator`，确定性生成机器 Block、BlockEntity、AbstractContainerMenu、客户端 Screen 和 Screen 注册类。
- 机器方块支持右键打开菜单，BlockEntity 持有 `SimpleContainer`、能量和进度字段，并用 `ContainerData` 同步到 GUI。
- 资源生成、loot table、mineable / tool tier 标签、语言文件和程序化机器贴图接入机器类型。
- planner 能从 furnace、compressor、upgrade table、magic altar、storage 以及中文机器关键词生成机器 spec。
- validator、audit、capability matrix、手工测试 checklist 和回归测试覆盖机器结构。
- 新增示例 `examples/machine_ruby_compressor.json` 和文档 `docs/规格与生成/machine-dsl.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli generate-from-spec .\examples\machine_ruby_compressor.json --workspace-name v52-machine-smoke --audit --no-build --json
```

边界：
- 当前是模板化机器系统，不是任意 Java / 任意 GUI 生成。
- 机器默认提供槽位、能量、进度、Menu、Screen 和数据同步骨架，复杂配方逻辑、能源网络、多方块结构和实体 AI 仍是后续路线。
