# V7 Progression / Gameplay Loop DSL

> 文档定位：这是 Progression DSL 专项材料，不是主学习入口。需要理解玩法阶段、目标和解锁关系时再读。

V7 的目标是把一组单点 feature 组织成玩家能理解、能演示、能审计的玩法线。它仍然遵守项目边界：LLM / rules 只输出结构化 `ModSpec`，确定性生成器只产出受控 Java、JSON、PNG 和 `.agent` 证据文件。

这句话描述的是 V7 Progression DSL 这个功能层的稳定路径边界，不否定 V8.4+ 的 `ModSpec-first hybrid` 架构。当前全局边界以 [project-limitations.md](../总览/project-limitations.md)、[direct-code-lane.md](../Agent与能力/direct-code-lane.md) 和 [agent-workflow.md](../Agent与能力/agent-workflow.md) 为准。

## 能表达什么

`progression` 可以把已有 ModSpec feature 串成路线：

```text
矿物 -> 材料 -> 机器加工 -> 装备/道具 -> 实体掉落 -> 结构战利品 -> 维度推进
```

每条路线由 stages 和 links 组成：

- `stages[]`: 每一步的 id、类型、标题、requires、provides、unlocks 和 evidence。
- `links[]`: 从一个 stage 到下一个 stage 的触发方式和条件。
- `entry_stage` / `end_stage`: 用于验证入口是否能抵达终点。

## Stage 类型

当前支持：

- `ore`
- `material`
- `recipe`
- `machine`
- `equipment`
- `item`
- `block`
- `entity`
- `structure`
- `loot_pool`
- `dimension`
- `biome`
- `world_feature`
- `milestone`

## 证据报告

生成后会写：

```text
.agent/progression-report.json
.agent/progression-report.md
```

报告里包含：

- loop / stage / link 数量。
- 每个 stage 的 requires / provides / unlocks / evidence。
- 每个引用解析到的目标类型。
- 缺失引用列表。
- stage type 覆盖统计。
- entry stage 到 end stage 的可达性。
- cycle 提示。

## 示例

运行：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m agent.cli generate-from-spec .\examples\progression_gameplay_loop.json --workspace-name demo-progression --overwrite --audit --no-build --json
```

重点查看：

```text
workspace/demo-progression/.agent/progression-report.json
workspace/demo-progression/.agent/progression-report.md
workspace/demo-progression/.agent/audit-report.json
workspace/demo-progression/.agent/generation-summary.json
```

## 边界

- V7 不生成任意 Java patch。
- V7 不等于任务系统、成就树、剧情脚本或复杂维度门逻辑。
- `progression` 的作用是把现有 DSL 能力组织成可审计玩法路线；实际玩法节点仍由 item、ore、machine、entity、structure、loot_pool、dimension 等 feature 承载。
- 未解析到现有 ModSpec feature 的 evidence / requires / provides / unlocks 会作为 warning 和 missing reference 进入报告。
