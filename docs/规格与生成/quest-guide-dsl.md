# V7.2 Quest / Advancement / Guide DSL

> 文档定位：这是 Quest / Advancement / Guide DSL 专项材料，不是主学习入口。需要理解任务、成就和指南结构时再读。

V7.2 的目标是把 V7 玩法线变成玩家能看见的目标：任务链、advancement JSON、引导文本，以及 Patchouli-style guidebook 数据结构。

它仍然遵守项目边界：LLM / rules 只输出结构化 `ModSpec`，确定性生成器输出 Java、JSON、PNG、resources 和 `.agent` 证据文件。V7.2 不生成任意 Java patch。

这句话描述的是 V7.2 Quest / Advancement / Guide DSL 这个功能层的稳定路径边界，不否定 V8.4+ 的 `ModSpec-first hybrid` 架构。当前全局边界以 [project-limitations.md](../总览/project-limitations.md)、[direct-code-lane.md](../Agent与能力/direct-code-lane.md) 和 [agent-workflow.md](../Agent与能力/agent-workflow.md) 为准。

## 能表达什么

`quest` 可以直接写任务，也可以指向一个已有 `progression`，由生成器从 stage 自动推导任务：

```text
obtain_item
craft_item
mine_block
use_machine
kill_entity
enter_dimension
visit_structure
milestone
```

每个任务会生成一个 advancement JSON，同时进入 `.agent/guidebook.md` 和 Patchouli-style book entry。

## ModSpec 写法

```json
{
  "type": "quest",
  "id": "ruby_questline",
  "title": "Ruby Questline",
  "summary": "Visible goals for the ruby progression.",
  "target_progression": "ruby_progression",
  "guidebook_id": "ruby_guidebook",
  "category": "ruby_progression",
  "tasks": [
    {
      "id": "mine_ruby_ore",
      "title": "Mine Ruby Ore",
      "task_type": "mine_block",
      "target": "ruby_ore",
      "icon": "ruby_ore",
      "guide_text": "Start underground and mine ruby ore.",
      "reward_xp": 25
    }
  ]
}
```

字段说明：

- `target_progression` 指向已有 `progression` id。没有显式 `tasks` 时，生成器会从 progression stages 推导任务链。
- `guidebook_id` 和 `category` 会决定 Patchouli-style 输出路径。
- `parent` 可以把任务接到同一 quest 内较早的 task。
- `target` 和 `icon` 可以引用已有生成内容、`recipe:<id>` 或外部 resource location。

## 输出证据

生成时会写入：

```text
.agent/quest-report.json
.agent/quest-report.md
.agent/guidebook.md
src/main/resources/data/<modid>/advancement/<quest>/<task>.json
src/main/resources/data/<modid>/patchouli_books/<guidebook>/book.json
src/main/resources/data/<modid>/patchouli_books/<guidebook>/en_us/categories/<category>.json
src/main/resources/data/<modid>/patchouli_books/<guidebook>/en_us/entries/<quest>.json
```

`audit` 会检查 quest report 版本、quest 数量、advancement 文件和 guidebook 文件是否存在。

## 快速验证

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m agent.cli generate-from-spec .\examples\quest_guide_gameplay_loop.json --workspace-name demo-quest-guide --overwrite --audit --no-build --json
```

关键产物：

```text
workspace/demo-quest-guide/.agent/quest-report.json
workspace/demo-quest-guide/.agent/quest-report.md
workspace/demo-quest-guide/.agent/guidebook.md
workspace/demo-quest-guide/.agent/audit-report.json
```

## 边界

- V7.2 生成的是数据驱动任务/成就/指南结构，不是完整自定义任务运行时。
- Patchouli-style JSON 会被生成，但项目不会自动添加 Patchouli Gradle 依赖。
- advancement 条件覆盖常见任务类型，复杂剧情触发、跨维度脚本和任意 Java 逻辑仍属于后续受控扩展。
