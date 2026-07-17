# Runtime Manual Validation

本文定义 Minecraft runtime 人工验收证据的最小格式。它补充 audit/build gate，但不替代 `ModSpec-first`、deterministic generator、structured patch、audit/build 和 trace-backed evidence 主线。

## 使用场景

在这些场景中使用 runtime manual validation：

- 准备把某个 generated workspace 作为公开 showcase 或 benchmark 证据。
- 需要证明 jar 不只是 Gradle build 成功，还被人工放进 Minecraft / NeoForge 环境加载过。
- 需要把 runtime 结果传给 `real-llm-stability --runtime-evidence`、benchmark report 或 evidence-chain report。

没有 runtime evidence 的 case 必须保持 `runtime_unverified` 或“不包含 runtime evidence”的口径，不能写成 Minecraft runtime 已通过。

## Schema v1

工具读取的 runtime evidence 使用统一结构：`manual-runtime-evidence/v1`。

```json
{
  "runtime_evidence_cases": [
    {
      "schema_version": "manual-runtime-evidence/v1",
      "evidence_kind": "manual_minecraft_runtime",
      "id": "basic_ruby",
      "workspace": "workspace/real-llm-stability-runs/<run-name>/runs/01-basic_ruby-strict",
      "status": "passed",
      "passed": true,
      "source": "docs/验证与可靠性/runtime-evidence/<date>-basic-ruby.json",
      "notes": "NeoForge client launched with the generated jar; ruby item/block appeared in creative inventory; recipe smoke checked; no startup crash."
    }
  ]
}
```

字段约定：

- `schema_version`：固定为 `manual-runtime-evidence/v1`。
- `evidence_kind`：固定为 `manual_minecraft_runtime`。
- `id`：优先使用 eval / real-llm-stability case id，方便自动匹配。
- `workspace`：指向被验收的 generated workspace。
- `status`：建议使用 `passed`、`failed`、`blocked` 或 `runtime_unverified`。
- `passed`：只有人工确认通过时才写 `true`。
- `source`：指向这份 evidence 文件或更详细的人工记录。
- `notes`：简短说明实际检查了什么，不写没做过的内容。

Markdown 表格也可以被读取，列顺序至少是：

```markdown
| Case | Workspace | Result | Manual runtime checks |
| --- | --- | --- | --- |
| basic_ruby | `workspace/basic-ruby` | passed | Client launched and basic item/block smoke passed. |
```

## 前置条件

运行人工 runtime 验收前，至少确认：

1. workspace 对应的 `.agent/modspec.json` 存在。
2. `audit` 已通过，并有 `.agent/audit-report.json` 或 `.agent/audit-report.md`。
3. 如果声明 build 通过，必须有 Gradle build 输出或 `.agent/logs/gradle-build.*` 证据。
4. 使用的是本次要验收的 jar，不是旧 workspace 或旧 build 产物。
5. 记录中不包含 API key、账号、私有路径截图或不可公开材料。

## 人工检查清单

最小 checklist：

1. 启动匹配版本的 Minecraft / NeoForge 客户端或服务端。
2. 加载本次 workspace 生成的 jar。
3. 确认游戏能进入主菜单、世界或服务端，不因 mod 初始化崩溃。
4. 按 `ModSpec` 检查核心功能：item/block 注册、recipe 可见或可合成、ore/worldgen 可合理确认、behavior/progression 能触发关键路径。
5. 失败时记录 crash report、`latest.log` 关键片段或复现步骤。
6. 给出明确结论：`passed`、`failed`、`blocked` 或 `runtime_unverified`。

Worldgen 手工检查需要区分两条路径：

- `/place feature <id>` 直接执行 configured feature，只适合验证 feature 能否在当前目标方块环境中放置。Ore feature 必须在满足其 rule test 的实心方块环境中执行，例如 `stone_ore_replaceables` 对应的 Stone，或 `deepslate_ore_replaceables` 对应的 Deepslate；在空气、草地或不匹配方块处返回 placement failed，不等于 registry 或 generator 失败。
- 自然生成会经过 placed feature、placement modifiers 和 biome modifier。高度范围、生成次数、biome 注入和自然矿脉应在新生成区块中单独检查，不能由 `/place feature` 成功替代。

验收方法本身出错时，应保留首次 attempt，再追加修正前置条件后的 revalidation，不要覆盖历史失败记录。

## 消费路径

当前消费 runtime evidence 的入口：

- `real-llm-stability --runtime-evidence <file>`
- `benchmark-report --runtime-evidence <file>`
- `evidence-chain-report` 通过 benchmark stable layer 消费同一个 schema summary

这些报告只把 `manual_minecraft_runtime` 计入 runtime evidence。audit/build 通过不会自动产生 runtime 通过结论。

## 对外表述边界

可以说：

- 这个 workspace 通过了 audit/build gate。
- 这个 case 有人工 runtime evidence，结论是 `passed` / `failed` / `blocked`。
- real provider、schema、audit、build、runtime 和 fallback 被分层统计。

不能说：

- audit/build 通过等于 Minecraft runtime 验收通过。
- mock provider smoke 证明真实 provider runtime 稳定。
- `--no-build` 的 run 证明 jar 可编译或可进游戏。
- 没有 evidence 的 case 已经完成游戏内验收。
