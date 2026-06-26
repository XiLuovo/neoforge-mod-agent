# Validation Matrix

本文件定义项目验证、展示预检和公开材料边界。原则：没跑过的验证不能写成已验证。

## 常用验证命令

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli showcase --run-name development-e2e-smoke --llm-provider mock --no-build --json
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --llm-provider mock --audit --no-build --json
```

不要求每次都跑完整套件，但必须根据改动风险选择合理验证。若无法运行测试，应说明原因和剩余风险。

## 验证选择建议

- 只改文档链接或公开文档：至少跑 `python -m unittest tests.test_doc_links`。
- 改 CLI 参数或命令分发：跑相关 CLI parser 测试和一个 mock smoke。
- 改 planner / ModSpec / generator：跑相关示例、golden/domain/schema 测试和 audit smoke。
- 改 tool-calling / structured patch / workspace safety：跑 `tests.test_tool_calling_agent`、`tests.test_workspace_safety` 和相关 repair smoke。
- 改 RAG / reviewer / benchmark：跑对应单测，并保留 RAG on/off 或 benchmark evidence。
- 改发布或展示流程：跑 quality gate 或至少跑 README 中当前推荐的 showcase/eval smoke。

## 展示与发布预检

当任务涉及“项目展示、公开发布、打包、README 主线、showcase、benchmark 报告”时，按 release-preflight 思路处理：自动检查和人工确认分开，不能把人工未验证的内容写成已通过。

推荐自动检查组合：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest tests.test_doc_links
py -3.11 -m agent.cli doctor --no-java --json
py -3.11 -m agent.cli showcase --run-name preflight-development-e2e --llm-provider mock --no-build --json
py -3.11 -m agent.cli eval --cases examples/agent_development_e2e.json --llm-provider mock --audit --no-build --json
py -3.11 -m agent.cli agent bench --suite examples/agentic_rag_ablation.json --llm-provider mock --rag-ablation --audit --no-build --json
```

人工确认项：

- README / docs / showcase 的项目定位是否一致。
- `.agent` evidence 是否存在并能支撑展示说法。
- RAG/repair 是否仍是可靠性补充，而不是项目主叙事。
- 是否明确说明 audit/build 不能替代 Minecraft runtime 自动验收。
- 如果声称进游戏验收，是否有 [../验证与可靠性/runtime-manual-validation.md](../验证与可靠性/runtime-manual-validation.md) 定义格式的 runtime evidence。
- 是否没有泄露 `.env.local`、真实 API key、私有路径或不应公开的本地材料。

如果某个自动检查过重或当前环境无法运行，应说明原因，并给出已运行的替代验证；不要把未运行的 preflight 写成完成。

## 文档与证据要求

面向公开展示的功能，最好同时沉淀至少一种证据：

- README 或 `docs/` 中的说明。
- 可复现 CLI 命令。
- 单元测试或 benchmark case。
- trace / report / showcase 输出。
- 简短设计记录。

如果功能还不稳定，应在文档中明确标为实验性、候选能力或可靠性补充，不要夸大成主线能力。

## 公开材料边界

面向公开仓库或项目展示的材料应只呈现项目能力和工程证据，不暴露内部协作细节。

- README、发布包、项目摘要和公开 commit message 不应提到本地参考目录、内部提示词、私有规划材料或 AI 协作细节。
- 可以说明“LLM planner / reviewer / tool-calling loop / mock provider / OpenAI-compatible provider”等项目真实技术概念。
- 不应把 local-only notes、临时 workspace、私有环境变量或未清理的 debug 输出当作公开材料。
- 若需要公开某份 evidence，应先确认它不包含真实密钥、私有绝对路径、账号信息或不可复现的本地状态。

## 公开表述约束

后续生成 README、项目摘要或项目介绍时，优先强调：

- 领域受控 Coding Agent。
- `ModSpec-first` 规格化生成。
- 确定性 generator 与受控 patch。
- audit/build gate。
- trace-backed evaluation。
- repair benchmark 与可靠性评估。
- RAG 作为上下文增强和可解释证据补充。

避免把项目描述成单纯“接入大模型”“做了 RAG 问答”“写了聊天机器人”。这些说法会降低项目辨识度。

所有对外表述必须和当前 evidence 匹配：当前是 RC3-candidate 时，不要写成正式 RC3 通过；audit/build 通过时，不要写成已经完成 Minecraft runtime 自动化验收；mock provider 成功时，不要暗示真实 provider 已稳定通过。
