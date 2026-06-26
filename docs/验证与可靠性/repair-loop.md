# Repair Loop

RC1 里有两类 repair：

1. deterministic repair loop：基于 `.agent/modspec.json` 重新生成 managed files，并重新跑 audit/build。
2. real tool-calling repair loop：LLM 根据 observation、RAG、文件内容和 reviewer feedback 选择受控工具。

## Tool-Calling Repair

```text
audit/build failure
-> observation
-> retrieve_rag / read_file / search_files
-> apply_structured_patch
-> run_audit / run_build
-> reviewer
-> finish or next iteration
```

常用命令：

```powershell
py -3.11 -m agent.cli agent repair rc1-develop-demo --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
```

## Evidence

```text
.agent/tool-call-trace.json
.agent/repair-loop-report.json
.agent/reviewer-report.json
.agent/structured-patch-plan.json
.agent/structured-patch-report.json
.agent/structured-patch-rollback-report.json
.agent/structured-patch-snapshots/
```

## Gate

repair 成功不能只看 LLM 的文字总结。最终结果必须由 audit/build gate 验收；reviewer 只能影响下一轮 context 或给出风险建议。
