# LLM Engineering Report

RC1 的 LLM 工程重点是把模型输出限制在可验证接口里。

## 接口

- planner JSON；
- tool action JSON；
- reviewer JSON。

## Trace

```text
.agent/prompt-trace.json
.agent/tool-call-trace.json
.agent/reviewer-report.json
.agent/agent-run.json
```

prompt trace 保存 prompt/response 摘要和结构化输出，不保存长 chain-of-thought。

## 安全策略

- schema validation；
- workspace path safety；
- structured patch only；
- snapshot before write；
- rollback evidence；
- deterministic audit/build gate；
- benchmark reads real trace。

## 评估方式

LLM 工程质量不看“回答是否好听”，而看：

- 是否稳定输出合法 JSON；
- 是否选择合适工具；
- 是否能根据 observation 迭代；
- 是否尊重 patch 边界；
- reviewer 是否能发现缺口；
- audit/build 是否通过。
