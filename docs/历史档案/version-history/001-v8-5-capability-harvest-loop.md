## V8.5 Capability Harvest Loop

目标：把后续主线从“让 Direct Code Lane 越来越像通用 coding agent”改成“让 LLM 在隔离实验区探索 generate gap，成功后再固化回稳定 generator”。

完成内容：

- 新增 `agent lab-generate "<request>" --from-workspace <workspace> --run-name <name> --build --json`。
- 新增 `harvest-report --run-name <name> --json`。
- package metadata 更新到 `8.5.0`。
- 新增 `FreeCodeLabRunner`，复制已有 generated workspace 到 `workspace/free-code-lab-runs/<run-id>/workspace`，只在实验副本里应用结构化补丁。
- Free-Code Lab 写入 `free-code-plan.json`、`free-code-plan.md`、`free-code-diff.md`、`free-code-report.json`、`manual-runtime-checklist.md` 和 `harvest-candidate.json`。
- 新增 `HarvestReportRunner`，聚合所有 Free-Code Lab candidate，输出 `workspace/harvest-runs/<run-id>/.agent/harvest-report.json` 和 Markdown 报告。
- 新增安全边界：拒绝绝对路径、路径穿越、`.git`、`gradle/wrapper`、build 输出、二进制产物、工具源码路径和危险 Java token。
- 同名 lab run 不覆盖，避免误删实验证据。
- 能力矩阵和 tool manifest 新增 `free_code_lab`、`capability_harvest_report`、`capability_harvest_loop`、`free_code_lab_generate` 和 `harvest_report`。
- 第一批固化方向记录为高级 machine GUI / BlockEntity 能力增强。
- 新增文档 [capability-harvest-loop.md](../../Agent与能力/capability-harvest-loop.md)。

快速验证：

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_free_code_lab tests.test_cli_parser tests.test_capabilities tests.test_tool_manifest -v
py -3.11 -m agent.cli harvest-report --run-name local-harvest --json
```

边界：

- Free-Code Lab 是实验隔离区，不是稳定生成路径。
- 实验成功不会自动修改 generator。
- `harvest_into_generator` 必须依赖人工 runtime checklist、工程整理和回归测试。
- 第一版仍使用结构化 `write_file` / `replace_text`，方便审计和回放。
