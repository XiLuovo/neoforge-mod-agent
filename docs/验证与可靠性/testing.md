# Testing

RC1 的测试目标是防止受控 agent 主线回退：develop/repair 必须走真实 tool-calling loop，reviewer 必须写真实报告，benchmark 指标必须来自真实 trace。

## 推荐命令

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
python -m unittest tests.test_doc_links
python -m unittest discover tests
```

可选编译检查：

```powershell
py -3.11 -m compileall src
```

如果本机没有 `py -3.11`，使用：

```powershell
python -m compileall src
```

## 关键覆盖

- CLI parser 和 smoke；
- ModSpec / DSL / generator；
- RAG retrieval；
- `ToolCallingRepairAgent`；
- `agent develop` 的真实 tool-calling loop；
- `agent repair` 的真实 tool-calling loop；
- structured patch snapshot / rollback；
- `LLMReviewer` approve、missing requirement、needs repair；
- `agent bench` trace-backed metrics；
- doc link guard。

## 文档改动验收

文档变更至少运行：

```powershell
python -m unittest tests.test_doc_links
```

较大文档收口建议同时跑全量 unittest，确认没有误改命令示例或测试夹具。
