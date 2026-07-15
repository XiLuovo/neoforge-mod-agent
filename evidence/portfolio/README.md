# Portfolio Evidence Manifest

该目录只保存经过脱敏的冻结报告，用于让 README 中的公开结论可以复验。
audit/build 证据不等于 Minecraft 客户端或服务端 runtime 验收。

## mock-development-e2e-20260627

- Status: `complete`
- Provider: `mock`
- Source run: `workspace/eval-runs/public-polish-decomposed-e2e-20260627/.agent`
- Validation: `planner, generator, audit`
- Boundary: Offline reproducible evidence; no Gradle build or Minecraft runtime validation.

- `mock-development-e2e-20260627/eval-report.json` — SHA-256 `0f97fb0e9caf209f0f693598cf495b5dd823fa85ff886fdeccf4d23f54c23725`
- `mock-development-e2e-20260627/eval-report.md` — SHA-256 `3e223d0078678335f4c0f15039062c49fccd036e556685e14d9a44ccf82f4a8e`

## mock-build-showcase

- Status: `complete`
- Provider: `mock`
- Source run: `workspace/showcase-runs/public-build-smoke-clean/.agent`
- Validation: `doctor, planner, generator, audit, gradle-build`
- Boundary: Generated workspaces passed the recorded build gate; no Minecraft runtime validation.

- `mock-build-showcase/showcase-report.json` — SHA-256 `ac467e6e7e36fb0730629cab9c90826b08da42a9bb4fcd6a08fcd714ae848b4e`
- `mock-build-showcase/showcase-report.md` — SHA-256 `d4796ad3ab8ac239ecea5885ab4dd7de35f291789c3ae5609d072f24a54c0082`

## real-provider-13case-historical

- Status: `complete`
- Provider: `real-provider`
- Source run: `workspace/real-llm-stability-runs/real-llm-13case-runtime-upgrade/.agent`
- Validation: `provider, schema, generator, audit`
- Boundary: Historical non-decomposed run. It must not be used as evidence for the later decomposed-planner token or latency claims. No Minecraft runtime validation.

- `real-provider-13case-historical/real-llm-stability.json` — SHA-256 `436a339b1b349fa78f286e0a53e3e3a096de4493c664019c147adcbc1236d2f6`
- `real-provider-13case-historical/real-llm-stability.md` — SHA-256 `1b2d3f38ce33886de6a5c0d8ebe78286cf1ce831a6932078269d8b5a3b298420`
