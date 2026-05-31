# 项目当前不足与后续路线

> 文档定位：这是统一边界入口。学习主线见 [`project-learning-plan-cn.md`](project-learning-plan-cn.md)，面试讲法见 [`interview-script.md`](interview-script.md)；所有对外表述都应以本文的不足和边界为准。

最后更新：2026-05-29

这份文档记录当前项目还不够强的地方。它不是贬低项目，而是把边界说清楚：哪些能力已经可演示、可测试、可回放，哪些地方还只是第一版或工程路线。

## 总体判断

项目已经从单纯的 `ModSpec -> deterministic generator` 升级到 `ModSpec-first + Direct Code Lane`，并新增 `Capability Harvest Loop` 作为后续学习和能力沉淀路线。这让它比普通模板生成器更灵活，但还不是通用 Coding Agent，也不是完整 Minecraft runtime 自动测试平台。

最准确的定位是：

```text
Natural language
  -> ModSpec-first routing
  -> deterministic generation
  -> optional structured Direct Code Patch
  -> optional Free-Code Lab experiment for generate gaps
  -> audit / build / repair / replay evidence
  -> harvest candidate / generator upgrade plan
```

## 主要不足

1. Direct Code Lane 还是第一版
   - 只支持 `write_file` 和一次精确 `replace_text`。
   - 没有 AST-aware patch、语义级重构、跨文件依赖分析或自动冲突合并。
   - 多 change 计划不是严格事务式应用；失败时会生成 rollback 建议和快照，但不会自动恢复。

2. Repair 还没有 Direct Code repair-loop
   - Direct Code 写入后如果 build/audit 失败，系统会标记 rollback recommended。
   - 当前不会自动让 LLM 生成第二轮 Direct Code 修复补丁。
   - 后续可以做 `direct-code repair-loop`，但必须继续保留结构化补丁、审查、snapshot、build gate。

3. Free-Code Lab 还是实验闭环第一版
   - `agent lab-generate` 已经能复制 workspace、应用结构化实验补丁、写 manual checklist 和 harvest candidate。
   - 但它还不会自动把成功样本整理成 generator 模板。
   - `harvest-report` 只是汇总候选，不负责自动合并代码。
   - `harvest_into_generator` 仍需要人工 runtime 结论、设计抽象、代码整理和回归测试。

4. 安全检查仍偏工程启发式
   - 当前有路径策略、危险 token、Java package 校验、Gradle 风险提示和 build/audit gate。
   - 但它不是完整 Java 静态分析器，也不是隔离容器沙箱。
   - Gradle build 仍在本地环境执行，未来可以补 sandboxed build、权限隔离和更细粒度 allowlist。

5. Audit 不等于真实游戏内测试
   - Audit 能检查生成文件、资源引用、报告和结构一致性。
   - Gradle build 能检查编译层面问题。
   - 但机器交互、实体 AI、GUI 行为、维度进入、任务链体验等还缺少自动化 Minecraft runtime harness。

6. NeoForge 是唯一稳定 domain
   - `minecraft.neoforge` / `ModSpec` 已经是完整主线。
   - `spring.api` 和 `unity.component` 仍是 planned registry entry，不应包装成已落地多领域生成器。
   - 下一步如果要证明 DomainSpec 抽象，应实现一个最小 Spring API 或 Unity component vertical slice。

7. 真实 LLM 覆盖仍弱于 mock 基线
   - Mock provider 用于稳定离线测试和演示。
   - OpenAI-compatible provider 有 health check、JSON repair、retry 和 `--require-llm`。
   - 但真实模型的系统性 A/B、成本、延迟、失败样本和 Direct Code 质量评估还可以继续扩充。

8. 生成内容仍偏模板化
   - items、blocks、ores、tools、armor、machines、entities、worldgen、quests、resources 等覆盖面已经较广。
   - 复杂多方块系统、复杂 GUI、网络同步、动画、真实美术资源、复杂 boss 机制仍需要更强 DSL 或 Direct Code 模板库。

9. 文档存在历史债务
   - 部分历史版本记录仍保留当时“LLM 不直接写 Java”的版本边界，这是历史上下文，不代表当前最新架构。
   - 当前最新口径应改为：默认不让 LLM 裸写工程文件；当 ModSpec 表达不足时，允许 Direct Code Lane 产出结构化补丁，并强制 review、snapshot、audit、build、rollback evidence。
   - 部分历史中文文档存在编码显示问题，后续可以单独做一次文档清洗。

## 优先级路线

短期优先：

- 用 Free-Code Lab 收集 generate gap 样本，优先围绕高级 machine GUI / BlockEntity。
- 把人工 runtime checklist 填写结果结构化，避免只写一句“测试通过”。
- 用 `harvest-report` 统计哪些样本可保留、哪些应该拒绝、哪些值得固化。
- 给 Direct Code Lane 和 Free-Code Lab 增加更多 eval cases，统计 review fail、apply fail、build fail、audit fail 和 manual runtime blocker。

中期优先：

- 把第一个成功 Free-Code Lab 样本整理成稳定 generator 能力，例如 machine GUI / BlockEntity 增强。
- 为固化能力补 example spec、unit test、audit test 和 generate smoke test。
- 做 Direct Code repair-loop，但限定为结构化 JSON patch，不开放自由 diff。
- 引入 Java AST 或至少 package/import/class name 层面的静态分析。
- 给 Gradle build 增加隔离运行配置和超时/资源限制。
- 实现一个非 NeoForge 的最小 DomainSpec vertical slice。

长期优先：

- 接入真实 Minecraft runtime smoke harness。
- 让复杂 GUI、网络同步、动画、AI goal 走更强 DSL 或受控 patch template。
- 建立真实 LLM Direct Code 质量基准，包括成功率、修复率、成本、延迟和人工 review 负担。
- 形成可复用的 `gap detected -> lab generated -> tested -> harvested -> generator upgraded -> regression protected` 能力采集闭环。
