# 典型 Demo Case

> 文档定位：这是 demo case 专项材料，不是主学习入口。先学懂项目，再用本文挑选可演示案例。

这些 case 都适合面试现场展示。默认建议用 `mock` 模拟大模型，因为它离线、稳定、可复现；如果要展示真实大模型，可以把 provider 切到 `openai-compatible`。

## 推荐一键展示

```powershell
.\scripts\portfolio_showcase.ps1
```

预期：

- 生成 portfolio report。
- 生成 dashboard HTML。
- 跑通三组黄金演示：红宝石基础 Mod、机器方块、玩法线组合展示。
- 跑通一个失败样例和修复评测。

## 1. 红宝石基础 Mod

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent generate "Create a ruby mod with ruby item, ruby block, ruby ore, ruby sword, ruby tool set, and ruby armor set." --planner llm --llm-provider mock --workspace-name demo-ruby-basic --overwrite --no-build --json
```

讲解点：

- 自然语言转 ModSpec。
- 生成 Java、模型、语言文件、贴图、配方和 `pack.mcmeta`。
- audit 验证通过。

## 2. 机器方块

```powershell
py -3.11 -m agent.cli generate-from-spec .\examples\machine_ruby_compressor.json --workspace-name demo-machine --overwrite --audit --no-build --json
```

讲解点：

- 模板化生成 `BlockEntity`、能量、进度、容器槽位、菜单和界面。
- 说明系统可以覆盖比普通物品更复杂的受控代码模板。
- audit 检查机器相关文件和资源引用。

## 3. 玩法线组合展示

```powershell
py -3.11 -m agent.cli generate-from-spec .\examples\progression_gameplay_loop.json --workspace-name demo-gameplay-loop --overwrite --audit --no-build --json
py -3.11 -m agent.cli generate-from-spec .\examples\quest_guide_gameplay_loop.json --workspace-name demo-quest-guide --overwrite --audit --no-build --json
py -3.11 -m agent.cli generate-from-spec .\examples\resource_quality_showcase.json --workspace-name demo-resource-quality --overwrite --audit --no-build --json
```

讲解点：

- `progression` 展示矿物、机器、装备、实体掉落、结构战利品和维度入口。
- `quest` 展示任务、成就和指南书结构。
- `resource quality` 展示贴图质量档案、材质图集和结构预览报告。

## 4. Modify 增量修改

```powershell
py -3.11 -m agent.cli agent generate "做一个红宝石模组，添加红宝石。" --planner llm --llm-provider mock --workspace-name demo-modify --overwrite --no-build --json
py -3.11 -m agent.cli agent modify workspace/demo-modify "添加红宝石护符，右键回复4点生命值，冷却20秒。" --planner llm --llm-provider mock --no-build --json
```

讲解点：

- modify 读取 `.agent/modspec.json`。
- 只合并结构化 patch，不扫描 Java 反推状态。
- 重复执行不会重复 feature。

## 5. 失败诊断与自修复

```powershell
py -3.11 -m agent.cli failure-lab --run-name demo-failure-lab --case delete_model --json
py -3.11 -m agent.cli repair-eval --run-name demo-repair-eval --case delete_model --json
```

讲解点：

- 自动制造坏项目。
- audit 发现缺失文件。
- repair RAG 给出知识证据。
- repair-loop 安全重生成 managed files。
- repair-eval 量化恢复结果。
