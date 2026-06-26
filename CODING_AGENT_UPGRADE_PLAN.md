# Minecraft Mod Coding Agent 升级计划

## 1. 目标

把当前项目从“带 agent 流程的 ModSpec 生成器”，升级成真正的 **Minecraft Mod Coding Agent**。

这里的 Coding Agent 不是通用、无限制、随便改代码的 agent，而是一个 **NeoForge 领域内受控的 coding agent**。它应该能做到：

- 理解用户给的 Mod 开发目标；
- 检索 NeoForge 相关知识；
- 读取和搜索生成出来的 workspace 文件；
- 运行 audit / build；
- 根据错误和文件内容提出受控 patch；
- 只在允许的 workspace 范围内改文件；
- 修完后继续 audit / build；
- 失败则继续下一轮；
- 最后输出可回放证据。

一句话目标：

```text
用户只给目标，agent 自己观察、查资料、读文件、改文件、跑验证、失败再修，直到成功或达到迭代上限。
```

## 2. 当前真实状态

项目现在已经有很多稳定基础：

- `ModSpec-first` 规划；
- 确定性 NeoForge 生成器；
- NeoForge 模板；
- 本地 RAG 知识库；
- workspace audit；
- Gradle build wrapper；
- managed-file repair-loop；
- eval / benchmark / repair-eval；
- `.agent/agent-run.json` 回放证据；
- 最近新增的 `agent develop`、`agent repair`、`agent bench` CLI 外壳；
- 最近新增的 `.agent/tool-call-trace.json` 和 `.agent/reviewer-report.json`。

但当前最大问题是：

```text
LLM 主要还是只在 planner 阶段使用。
```

也就是说，现在更像：

```text
LLM planner
-> ModSpec
-> deterministic generator
-> audit/build/repair/report
```

还不是真正的：

```text
LLM observe
-> choose tool
-> read/search/retrieve
-> patch
-> audit/build
-> repeat
```

所以不能继续只堆 CLI 和报告。下一步必须做真实 tool-calling loop。

## 3. 正确升级方向

正确架构应该是：

```text
用户目标
-> Intent Planner
-> Reviewer
-> 生成 baseline workspace 或加载已有 workspace
-> ToolCallingAgentLoop
   -> observe
   -> retrieve RAG
   -> read/search files
   -> choose action
   -> apply structured patch 或 regenerate managed files
   -> run audit/build
   -> observe again
-> final report / replay / benchmark metrics
```

LLM 应该用在这些地方：

- `planner`：把自然语言转成 ModSpec / goal contract；
- `repair_agent` 或 `refine_agent`：根据错误、RAG、文件内容决定下一步工具调用和 patch；
- 可选 `reviewer`：审查需求覆盖、unsupported 内容、patch 风险。

LLM 不应该替代这些东西：

- deterministic generator；
- audit；
- build；
- 路径安全检查；
- patch 应用器；
- 最终验收 gate。

## 4. 第一阶段：先做真正的 Tool-Calling Repair Agent

优先做 `agent repair`，不要先做 `agent develop`。

原因：repair 最能体现 coding agent 能力。因为它天然是：

```text
项目坏了
-> agent 观察错误
-> 查资料
-> 读文件
-> 改文件
-> 再验证
-> 失败继续修
```

目标命令：

```powershell
py -3.11 -m agent.cli agent repair workspace\ruby-tech-agent `
  --goal "Fix all build and audit failures without changing user-owned files." `
  --llm-provider openai-compatible `
  --max-iterations 5 `
  --json
```

背后应该发生：

```text
initial audit/build observation
-> LLM 选择 retrieve_rag / read_file / search_files / apply_patch / run_audit / run_build
-> 工具执行
-> observation 加入上下文
-> LLM 继续下一轮
-> 成功或达到 max_iterations
```

第一阶段必须支持这些工具 action：

- `retrieve_rag`
- `read_file`
- `search_files`
- `run_audit`
- `run_build`
- `regenerate_managed_files`
- `apply_structured_patch`
- `finish`

最重要产物：

```text
.agent/tool-call-trace.json
```

注意：这个文件必须记录 **真实 LLM 选择的工具调用**，不能只是从 agent step 派生出来的假 trace。

建议 trace schema：

```json
{
  "iteration": 1,
  "role": "repair_agent",
  "thought_summary": "简短原因，不能包含敏感长思维链。",
  "action": "read_file",
  "args": {
    "path": "src/main/java/..."
  },
  "observation": {
    "success": true,
    "summary": "Read 120 lines."
  }
}
```

## 5. Patch 安全边界

不能让 LLM 输出自由 diff。

LLM 只能输出结构化 patch，例如：

```json
{
  "changes": [
    {
      "operation": "replace_text",
      "path": "src/main/java/...",
      "old": "...",
      "new": "..."
    }
  ]
}
```

必须满足：

- 只允许改 generated workspace 内的允许路径；
- 禁止绝对路径；
- 禁止 `..` 路径穿越；
- 禁止 `.git`；
- 禁止 Gradle wrapper jar 等二进制关键文件；
- 禁止 build output；
- 禁止密钥和隐私文件；
- 改文件前必须 snapshot；
- patch 后必须写 rollback report；
- 最终成功必须通过 audit/build gate。

## 6. 第二阶段：把 develop 接入同一个 loop

`agent repair` 做真之后，再升级 `agent develop`。

目标流程：

```text
用户目标
-> planner 生成 ModSpec baseline
-> generator 生成 workspace
-> reviewer 检查目标覆盖
-> tool-calling loop 修补/完善 workspace
-> audit/build
-> repair/refine until pass or max_iterations
```

generator 仍然是稳定能力的第一选择。LLM loop 用来处理：

- 生成后的 build failure；
- generator 尚未覆盖但可以小 patch 的功能；
- 缺失资源；
- recipe/schema 问题；
- 小型 Java 集成问题；
- guide / quest / progression 这类胶水逻辑。

不要一开始就让 LLM 从零写完整 Mod。

## 7. 第三阶段：加 LLM Reviewer

Reviewer 可以先保留 deterministic validator，后续再加 LLM reviewer。

LLM reviewer 输入：

- 用户原始目标；
- ModSpec；
- patch plan；
- RAG snippets；
- changed files summary；
- audit/build 结果。

LLM reviewer 输出：

- 需求是否覆盖；
- unsupported 内容；
- 风险列表；
- 还需要哪些验证；
- approve / reject 建议。

注意：最终是否成功仍然由 deterministic audit/build 决定，不能只听 reviewer。

## 8. 第四阶段：让 bench 评测真实 agent 行为

`agent bench` 不能只聚合 eval report。它应该评测真实 tool-calling loop。

需要输出：

- `success_rate`
- `build_success_rate`
- `audit_success_rate`
- `repair_success_rate`
- `avg_tool_calls`
- `avg_iterations`
- `rag_hit_rate`
- `patch_accept_rate`
- `rollback_count`
- `failed_cases`
- `trace_paths`

benchmark case 里必须包含“仅靠 regenerate managed files 修不好”的失败，这样才能证明 LLM patch loop 真正工作了。

## 9. 建议从这些文件开始

重点读这些文件：

- `src/neoforge_agent/agent_orchestrator.py`
- `src/neoforge_agent/agent_runtime.py`
- `src/neoforge_agent/cli.py`
- `src/neoforge_agent/repair_loop.py`
- `src/neoforge_agent/repair_rag.py`
- `src/neoforge_agent/direct_code_agent.py`
- `src/neoforge_agent/patch_agent.py`
- `src/neoforge_agent/llm_client.py`
- `src/neoforge_agent/llm_planner.py`

建议新增模块：

- `src/neoforge_agent/tool_calling_agent.py`

建议新增测试：

- `tests/test_tool_calling_agent.py`

建议扩展测试：

- `tests/test_agent_eval.py`
- `tests/test_cli_parser.py`
- `tests/test_benchmark_report.py`

## 10. 第一阶段验收标准

Phase 1 完成的标准：

- `agent repair` 会在 planner 之外调用 LLM；
- LLM 能真实选择工具；
- 测试中至少出现这些 action：
  - `retrieve_rag`
  - `read_file`
  - `apply_structured_patch`
  - `run_audit`
  - `finish`
- `.agent/tool-call-trace.json` 记录真实工具调用；
- 有一个坏 workspace 不是靠 managed-file regenerate 修好，而是靠结构化 patch 修好；
- repair 后 audit 通过；
- `--build` 开启时 build 通过，单元测试中可以 mock build；
- 不修改 user-owned 文件；
- patch 文件有 snapshot 和 rollback evidence。

## 11. 第二阶段验收标准

Phase 2 完成的标准：

- `agent develop` 能生成 baseline workspace；
- tool-calling loop 能读取并完善这个 workspace；
- 最终 trace 同时包含 planner 和真实 tool calls；
- `agent bench` 里的 `avg_tool_calls` 和 `avg_iterations` 来自真实 loop，不是派生值；
- build/audit gate 仍然是最终验收依据。

## 12. 给另一个对话的交接提示

可以直接把下面这段发给另一个对话：

```text
请先阅读 CODING_AGENT_UPGRADE_PLAN.md。

当前项目已经有 ModSpec-first generator、RAG、audit、build、repair-loop、agent develop/repair/bench CLI 和一些 trace/report，但 LLM 主要仍只在 planner 阶段使用。不要继续只扩展 CLI 或报告。

请优先实现 Phase 1：真实 ToolCallingRepairAgent。

目标是让 agent repair 在 planner 之外调用 LLM，让 LLM 根据 audit/build observation、RAG 和文件内容选择结构化工具：retrieve_rag、read_file、search_files、apply_structured_patch、run_audit、run_build、finish。工具执行后把 observation 放回下一轮，最多运行 max_iterations。必须写真实 .agent/tool-call-trace.json。

保留 ModSpec-first、deterministic generator、audit/build gate、workspace 路径安全、snapshot 和 rollback evidence。LLM 不能自由写任意 diff，只能输出受控结构化 patch。
```
## Phase Status

- Phase 0: complete - agent develop/repair/bench CLI shell and trace/report/evidence facade.
- Phase 1: complete - real ToolCallingRepairAgent for `agent repair`.
- Phase 2: complete - `agent develop` uses the same real tool-calling loop after baseline generation.
- Phase 2.5: complete - docs cleanup, category archive, duplicate root-doc removal, and link validation.
- Phase 3: complete - real LLMReviewer writes reviewer evidence for develop and repair without overriding audit/build gates.
- Phase 4: complete - `agent bench` runs real develop/repair/reviewer/tool-calling flows and reports metrics from traces.
- Final Integration / Release Candidate: complete - final tests, CLI smoke, evidence audit, and git status handoff completed.
