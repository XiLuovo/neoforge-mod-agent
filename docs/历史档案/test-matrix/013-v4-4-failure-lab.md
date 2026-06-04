## V4.4 Failure Lab / 故障注入测试

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_failure_lab tests.test_cli_parser tests.test_quality_gate tests.test_capabilities -v
py -3.11 -m agent.cli failure-lab --run-name v44-failure-lab --json
py -3.11 -m agent.cli failure-lab --run-name v44-recipe-failure --case break_recipe_reference --json
py -3.11 -m agent.cli quality-gate --run-name v44-quality-gate --json
```

Expected:

- `failure-lab` 生成 5 个隔离坏项目。
- 每个 case 都先生成干净 workspace，再注入一个故障。
- `delete_texture` 删除生成 PNG 后，audit 报告 texture / texture-manifest 相关错误。
- `delete_model` 删除 item model 后，audit 报告 item model 缺失。
- `delete_worldgen_json` 删除 configured_feature 后，audit 报告 worldgen JSON 缺失。
- `delete_behavior_java` 删除 RubyCharmItem.java 后，audit 报告 behavior class 缺失。
- `break_recipe_reference` 修改实际 recipe JSON 引用后，audit 报告 `recipe:*:json_*` 引用错误。
- 每个 case 都生成 `.agent/repair-rag-context.json` 和 `.agent/repair-rag-context.md`。
- 每个 case 都运行 repair-loop，并在重生成 managed files 后 audit 通过。
- `quality-gate` 默认包含 `failure_lab` check。
- Project version reports `4.4.0`.
