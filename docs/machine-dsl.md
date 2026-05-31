# V5.2 Machine DSL

> 文档定位：这是 Machine DSL 专项材料，不是主学习入口。需要理解机器方块、BlockEntity、Menu、Screen 和 machine GUI 生成时再读。

Machine DSL 是 V5.2 的核心：把“方块”从静态资源推进到带状态、容器、能量、进度和 GUI 的机器模板，同时继续保持 Java / JSON / PNG 由确定性生成器产出。

## 结构

```json
{
  "type": "machine",
  "id": "ruby_compressor",
  "display_name_en_us": "Ruby Compressor",
  "display_name_zh_cn": "红宝石压缩机",
  "strength": 4.0,
  "resistance": 6.0,
  "sound": "metal",
  "requires_correct_tool": true,
  "tool_tier": "iron",
  "block_kind": "cube",
  "machine_kind": "compressor",
  "inventory_slots": 2,
  "input_slots": 1,
  "output_slots": 1,
  "energy_capacity": 10000,
  "energy_per_tick": 20,
  "max_progress": 100,
  "menu_title": "Ruby Compressor"
}
```

## 当前支持

- Machine kinds: `furnace`, `compressor`, `upgrade_table`, `magic_altar`, `storage`
- BlockEntity: `SimpleContainer`、能量字段、进度字段、服务端 tick
- Menu: `AbstractContainerMenu`、机器槽位、玩家背包槽位、shift-click 移动物品
- Screen: `AbstractContainerScreen`、能量条、进度条、标题和数值文本
- Data sync: `ContainerData` 同步 progress、max progress、energy、energy capacity
- Assets: blockstate、block/item model、loot table、mineable / tool tier 标签、语言文件、程序化机器贴图

## 示例

```powershell
py -3.11 -m agent.cli generate-from-spec .\examples\machine_ruby_compressor.json --workspace-name v52-machine-demo --audit --no-build --json
```

这个示例会生成：

- `RubyCompressorBlock.java`: 右键打开机器菜单，注册服务端 ticker
- `RubyCompressorBlockEntity.java`: 保存容器、能量和进度，并通过 `ContainerData` 同步
- `RubyCompressorMenu.java`: 暴露机器槽位、玩家背包和进度/能量缩放方法
- `RubyCompressorScreen.java`: 绘制进度条、能量条和机器状态文本
- `MachineModClient.java`: 在 MOD event bus 上注册 Screen

## 边界

Machine DSL 是模板化机器系统，不是任意 Java 生成。当前重点是让“熔炉类机器、压缩机、升级台、魔法祭坛、储物方块”具备可演示的结构骨架；复杂配方匹配、能源网络、多方块结构、自定义实体 AI 和任意 Screen 逻辑仍属于后续扩展。
