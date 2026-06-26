# LLM 能力分层

当前主线中，LLM 的职责不是“一次性写完整 Mod”，而是在受控边界内做结构化决策。

## 当前分层

```text
自然语言理解
-> planner / ModSpec
-> tool action selection
-> reviewer JSON
-> benchmark / evidence interpretation
```

## 第一层：Planner

LLM 把用户目标收敛为 intent contract 和 `ModSpec`。这让 generator 可以稳定地产出 baseline workspace。

## 第二层：Tool-Calling Loop

LLM 在 develop/repair 中选择受控工具：

- `retrieve_rag`
- `read_file`
- `search_files`
- `apply_structured_patch`
- `run_audit`
- `run_build`
- `finish`

工具执行结果会作为 observation 回到下一轮，直到 `finish` 或达到 `max_iterations`。

## 第三层：Structured Patch

LLM 不能自由写 diff。它只能输出结构化 patch action；runtime 负责 path safety、snapshot、应用 patch、写 diff/report 和 rollback evidence。

## 第四层：Reviewer

LLM reviewer 审查：

- 需求覆盖；
- missing requirements；
- unsupported or risky requests；
- patch risks；
- recommended checks；
- decision。

reviewer 可以触发下一轮 repair/refine context，但不能替代 audit/build gate。

## 第五层：辅助实验

Direct Code Lane 是辅助能力，用于解释受控 patch 的演进；它不是当前推荐主线，也不能替代 ModSpec-first、deterministic generator、audit/build gate 和 evidence。

## 项目讲解口径

> 这个项目不是让 LLM 裸写 Java，而是把 LLM 放在 planner、tool action 和 reviewer 三个受控位置。真正写文件的要么是 deterministic generator，要么是带 path safety、snapshot 和 rollback evidence 的 structured patch executor。最后通过 audit/build gate 和 trace-backed benchmark 验收。
