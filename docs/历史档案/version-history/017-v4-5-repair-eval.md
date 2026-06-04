## V4.5 Repair Eval 报告

目标：把自修复能力从“能演示”升级成“可量化”，让简历和面试里可以直接讲成功率、命中率和恢复率。

完成内容：

- 新增 `repair_eval.py`，提供 `RepairEvalRunner`。
- 新增 CLI 命令：`repair-eval`。
- `repair-eval` 会复用 V4.4 Failure Lab 的故障样例，并统计：
  - audit 是否发现预期故障。
  - repair RAG 是否命中与故障类型相关的知识能力。
  - repair-loop 是否完成安全修复。
  - 修复后 audit 是否恢复。
  - 完整闭环成功率。
- 新增报告：
  - `workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.json`
  - `workspace/repair-eval-runs/<run-id>/.agent/repair-eval-report.md`
- Failure Lab case 结果新增：
  - `expected_rag_capabilities`
  - `repair_rag_knowledge_ids`
  - `repair_rag_capabilities`
  - `repair_rag_categories`
  - `repair_rag_relevant`
- `quality-gate` 默认加入 `repair_eval` check，可用 `--no-repair-eval` 跳过。
- Capability Matrix 新增 `repair_eval`。
- package metadata 更新到 `4.5.0`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli repair-eval --run-name v45-repair-eval --json
py -3.11 -m unittest tests.test_repair_eval tests.test_failure_lab tests.test_cli_parser tests.test_quality_gate tests.test_capabilities -v
py -3.11 -m agent.cli quality-gate --run-name v45-quality-gate --json
```
