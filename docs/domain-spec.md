# DomainSpec 插件化规格层

> 文档定位：这是 DomainSpec 规格层专项材料。需要区分 DomainSpec、ModSpec 和 planned domain plugin 时再读。

第 6 项升级把 `ModSpec` 上收为 `DomainSpec` 的一种实现。这样项目不再只能解释为“一个 Minecraft Mod 生成器”，而是可以讲成：

```text
DomainSpec -> Domain Plugin -> deterministic generator -> audit/build/repair/eval/replay
```

当前稳定实现是：

```text
domain_id: minecraft.neoforge
spec_type: ModSpec
artifact: .agent/modspec.json
```

规划中的扩展槽位是：

```text
domain_id: spring.api
spec_type: SpringApiSpec

domain_id: unity.component
spec_type: UnityComponentSpec
```

这两个目前只是 registry 里的 planned plugin，不会假装已经能生成 Spring 或 Unity 项目。

## 为什么要抽这一层

原来的主线是：

```text
自然语言 -> ModSpec -> NeoForge generator -> audit/repair
```

这能很好地证明 Minecraft Mod 生成闭环，但系统边界仍然绑在 `ModSpec` 名字上。抽出 `DomainSpec` 后，通用 Agent runtime 可以只关心：

- planner 是否产出一个结构化 domain spec
- reviewer 是否能验证这个 spec
- executor 是否能调用对应 domain plugin
- auditor / repair / trace 是否能记录同一套证据链

至于这个 spec 是 `ModSpec`、`SpringApiSpec` 还是 `UnityComponentSpec`，应该由 domain plugin 决定。

## 代码入口

- `src/neoforge_agent/domain_spec.py`
  - `DomainSpec`：结构化规格协议。
  - `DomainSpecMetadata`：领域、状态、schema、输入输出、runtime stage 元数据。
  - `DomainSpecPlugin`：load / dump / schema / validate / describe 插件协议。
  - `DomainSpecRegistry`：注册和发现 domain spec plugin。
  - `NeoForgeModSpecPlugin`：当前稳定的 Minecraft NeoForge 实现。
  - `PlannedDomainSpecPlugin`：Spring / Unity 的规划占位实现。

- `src/neoforge_agent/agent_runtime.py`
  - `AgentRuntimePlugin` 现在暴露 `domain_spec_plugin`。

- `src/neoforge_agent/agent_orchestrator.py`
  - `NeoForgeRuntimePlugin` 绑定 `NeoForgeModSpecPlugin`，并在 agent run payload 里写入 domain spec metadata。

## CLI

列出所有 domain spec：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli domains
```

输出 JSON：

```powershell
py -3.11 -m agent.cli domains --json
```

只看已实现 domain：

```powershell
py -3.11 -m agent.cli domains --status stable --json
```

只看规划 domain：

```powershell
py -3.11 -m agent.cli domains --status planned --json
```

## ModSpec 现在是什么

`ModSpec` 仍然是 NeoForge 生成的真相源，但它现在带有领域标识：

```json
{
  "domain": "minecraft.neoforge",
  "domain_spec_type": "ModSpec",
  "mod_id": "ruby_mod",
  "mod_name": "Ruby Mod",
  "package": "com.generated.ruby_mod",
  "features": []
}
```

这不改变现有 `.agent/modspec.json` 的使用方式；旧 payload 没有 `domain` 也可以通过 registry 自动识别。

## 后续接 Spring / Unity 的方式

新增一个领域时，不需要改通用 runtime 的阶段顺序，而是新增一组 domain plugin：

```text
SpringApiSpecPlugin
  load / dump / json_schema / validate / describe
  planner contract
  deterministic generator
  auditor
  repair rules
  benchmark cases
```

或者：

```text
UnityComponentSpecPlugin
  load / dump / json_schema / validate / describe
  planner contract
  deterministic generator
  editor/test evidence
  repair rules
  benchmark cases
```

这就是项目从“只会生成 Mod”升级成“可插拔 AI 工程生成框架”的关键边界。
