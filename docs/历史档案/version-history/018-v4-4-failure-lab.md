## V4.4 Failure Lab / 故障注入测试

目标：证明系统不是 happy path demo，而是能对典型坏项目完成“发现问题、解释原因、给出修复证据、执行安全修复”的闭环。

完成内容：

- 新增 `failure_lab.py`，提供 `FailureLabRunner`。
- 新增 CLI 命令：`failure-lab`。
- 默认注入 5 类故障：
  - 删除生成 texture。
  - 删除生成 model。
  - 删除 ore worldgen configured_feature JSON。
  - 删除 behavior item 自定义 Java 类。
  - 破坏实际 recipe JSON 中的引用。
- 每个 case 都会执行：
  - 生成干净 workspace。
  - 注入故障。
  - 运行 `audit`，确认能检测到预期失败。
  - 运行 `RepairRAGAdvisor`，写出 repair RAG 上下文。
  - 运行 `repair-loop`，基于 `.agent/modspec.json` 重生成 managed files。
  - 再次确认 audit 通过。
- `auditor.py` 增强：现在会检查实际 recipe JSON 文件里的 `result`、`key`、`ingredients` 引用，而不只检查 ModSpec recipe 字段。
- `quality-gate` 默认加入 Failure Lab，可用 `--no-failure-lab` 跳过。
- Capability Matrix 新增 `failure_lab`。
- package metadata 更新到 `4.4.0`。

边界：

- Failure Lab 只在隔离的 `workspace/failure-lab-runs/<run-id>/workspaces` 下制造坏项目。
- repair RAG 只提供证据和解释，不直接改 Java / JSON / PNG。
- repair-loop 仍然只基于 `.agent/modspec.json` 重生成 managed files。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli failure-lab --run-name v44-failure-lab --json
py -3.11 -m unittest tests.test_failure_lab tests.test_cli_parser tests.test_quality_gate tests.test_capabilities -v
py -3.11 -m agent.cli quality-gate --run-name v44-quality-gate --json
```
