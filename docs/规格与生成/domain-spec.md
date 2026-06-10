# DomainSpec

> RC1 定位：DomainSpec 是通用 runtime 和 NeoForge domain plugin 之间的规格边界。当前稳定实现只有 `minecraft.neoforge` / `ModSpec`。

## 为什么需要这一层

RC1 的 agent 主线不是直接把自然语言交给 generator，而是：

```text
Natural language
-> planner / intent contract
-> DomainSpec
-> domain plugin
-> deterministic generator baseline
-> tool-calling repair/refine loop
-> reviewer
-> audit/build gate
```

`DomainSpec` 让 runtime 只关心“是否有结构化规格、能否验证、能否生成、能否审计”，而把 NeoForge 细节放在 domain plugin 中。

## 当前稳定实现

```text
domain_id: minecraft.neoforge
spec_type: ModSpec
artifact: .agent/modspec.json
```

`ModSpec` 仍是 NeoForge workspace 的生成真相源。planner、mock LLM 或 real LLM 都应该先把目标收敛到它，deterministic generator 再产出 baseline workspace。

## Planned Domains

项目里可以保留 planned domain slot，但不要把它们当作已完成能力展示：

```text
spring.api       -> planned
unity.component -> planned
```

公开讲解时应明确：这些只是架构扩展点，当前没有稳定 Spring 或 Unity generator。

## 代码入口

- `src/neoforge_agent/domain_spec.py`
- `src/neoforge_agent/agent_runtime.py`
- `src/neoforge_agent/agent_orchestrator.py`

## CLI

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli domains --json
py -3.11 -m agent.cli domains --status stable --json
py -3.11 -m agent.cli domains --status planned --json
```

## 与 RC1 Tool Loop 的关系

`DomainSpec` 负责 baseline 的结构化输入；tool-calling loop 负责 baseline 之后的读取、检索、修复和完善。二者不是替代关系：

```text
ModSpec-first baseline
-> generated workspace
-> real tool-calling loop
-> audit/build gate
```
