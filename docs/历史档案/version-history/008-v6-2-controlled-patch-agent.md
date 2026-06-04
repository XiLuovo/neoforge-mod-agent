## V6.2 Controlled Patch Agent

目标：把 `modify` 路径显式升级成受控 patch-agent。LLM 先输出 patch plan，系统只修改 managed files，并在执行后补齐 audit / build / rollback 证据。

完成内容：

- 新增 `.agent/patch-agent-plan.json` / `.md`，记录 patch plan、managed-file policy、before/after ModSpec、增删改跳过统计和 rollback steps。
- 新增 `.agent/patch-agent-report.json` / `.md`，记录 patch 执行结果、audit/build/repair gate、managed files 和最终成功状态。
- 新增 `.agent/patch-agent-rollback-report.json` / `.md`，在 audit 或 build 失败时给出 rollback 建议。
- `modify` 和 `agent modify` 现在明确通过 patch plan 驱动 managed-file regeneration，而不是让 LLM 直接改整个 repo。
- Capability matrix 和工作流说明同步补齐 patch-agent boundary。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m unittest tests.test_agent_eval tests.test_web_demo tests.test_capabilities -v
py -3.11 -m agent.cli modify .\workspace\demo --planner llm --llm-provider mock --json
```

边界：

- 仍然不是裸 repo patch。
- 只允许 managed files；用户手写文件不在 overwrite scope 内。
- patch-agent 的最终接受条件仍然是 audit / build / rollback 证据链。
