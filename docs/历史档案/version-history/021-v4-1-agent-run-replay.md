## V4.1 Agent Run Replay / 历史运行回放

目标：让已经保存下来的 `.agent/agent-run.json` 可以被离线回放，形成一份按时间线组织的中文报告，方便面试展示和问题复盘。

完成内容：

- 新增 `replay.py`。
- 新增 CLI 命令：`replay <target> [--json]`。
- `target` 支持：
  - workspace 路径或 workspace 名称
  - `.agent` 目录
  - 直接的 `agent-run.json` 文件路径
- 回放不会重新执行：
  - LLM provider
  - generator
  - audit
  - build
  - repair
- 回放报告会整理：
  - run metadata
  - role steps
  - decisions
  - prompt traces
  - RAG hit / used knowledge 统计
  - JSON repair / retry 统计
  - artifact 路径索引
- 新增 artifact：
  - `.agent/agent-run-replay.json`
  - `.agent/agent-run-replay.md`
- Capability Matrix 新增 `agent_replay`。
- package metadata 更新到 `4.1.0`。

价值：

- 面试时可以展示历史 agent run 的完整证据链，而不必每次现场重跑。
- 调试时可以快速复盘 planner、reviewer、executor、auditor、repair agent 的输入、输出、决策和失败点。
- 继续保持确定性边界：replay 只读历史 artifact，不让 LLM 或 generator 参与。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent generate "Create a ruby mod with ruby." --planner llm --llm-provider mock --workspace-name v41-replay-source --overwrite --no-build --json
py -3.11 -m agent.cli replay workspace/v41-replay-source --json
```
