# Capability Harvest Loop

> RC1 定位：Capability Harvest Loop / Free-Code Lab 是辅助实验能力，不是当前推荐 demo 主线。

## 用途

当 deterministic generator 暂时表达不了某类需求时，Free-Code Lab 可以复制已有 generated workspace 到隔离目录，让 LLM 在副本里探索结构化实验 patch。实验结果只产生学习材料和 harvest candidate，不自动进入稳定 generator。

```text
generator gap
-> isolated lab workspace
-> structured experimental patch
-> audit/build/manual checklist
-> harvest candidate
-> future ModSpec / DSL / generator / audit / tests
```

## 与 RC1 主线的关系

RC1 的主线已经是：

```text
agent develop / repair
-> real tool-calling loop
-> structured patch
-> reviewer
-> audit/build gate
```

Free-Code Lab 只回答另一个问题：如果某个成功修复或实验模式值得长期保留，如何把它沉淀成确定性能力，而不是依赖 LLM 下次再发挥。

## 边界

- 只写实验副本，不改原 workspace。
- 不改本工具源码。
- 不自动合并到 generator。
- 不替代 reviewer 或 audit/build gate。
- 成功样本必须转化为规格、模板、audit 和测试后才能进入稳定能力。

## 讲解方式

一句话即可：

> RC1 已经能通过真实 tool-calling loop 修复 workspace；Free-Code Lab 是后续把实验样本沉淀回 generator 的学习通道，不是主线生成路径。
