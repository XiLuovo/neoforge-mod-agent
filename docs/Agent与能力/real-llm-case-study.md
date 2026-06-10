# Real LLM Case Study

这份文档现在用于说明真实 provider 如何接入 RC1 主线，而不是把旧的少量生成 case 当作当前主证据。

## 当前主证据

RC1 的真实行为证据应来自：

- `.agent/prompt-trace.json`
- `.agent/tool-call-trace.json`
- `.agent/reviewer-report.json`
- `.agent/agent-run.json`
- audit/build result
- benchmark report

## 推荐验证

使用 mock provider 做 CI 和本地稳定演示；使用 openai-compatible provider 时，重点检查 schema、tool action、reviewer JSON 和 gate 结果。

```powershell
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name rc1-llm-case --no-build --json
```

## 看点

- LLM 是否输出合法 JSON；
- tool action 是否在允许工具内；
- structured patch 是否通过 path safety；
- reviewer 是否输出结构化字段；
- audit/build 是否仍是最终 gate。

## 不再这样表述

不要说“若干生成 case 通过，所以 agent 成熟”。更准确的说法是：真实 provider 路径需要通过 planner、tool loop、reviewer、audit/build 和 trace-backed benchmark 全链路验证。
