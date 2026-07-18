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

## real-provider-decomposed-5case-20260718

- Status: `complete`
- Provider: `real-provider`
- Source run: `workspace/real-llm-stability-runs/resume-ab-20260718-decomposed-5case/.agent`
- Validation: `provider, schema, generator, audit`
- Boundary: Current decomposed batch result: 4/5 strict success. The failed basic_ruby case is preserved and must not be replaced by the separate retry. No Gradle build or Minecraft runtime validation.

- `real-provider-decomposed-5case-20260718/real-llm-stability.json` — SHA-256 `88f4c0613736f5117f8af2c869a9575dba67187ac829a09b9eb398329d826a2a`
- `real-provider-decomposed-5case-20260718/real-llm-stability.md` — SHA-256 `9ec175c29ae03db39c3a605b008aed2639dd80d68467742edd3223b1a64ebfae`

## real-provider-fullschema-5case-20260718

- Status: `complete`
- Provider: `real-provider`
- Source run: `workspace/real-llm-stability-runs/resume-ab-20260718-fullschema-5case/.agent`
- Validation: `provider, schema, generator, audit`
- Boundary: Current full-schema batch result: 5/5 strict success. This is audit-level evidence with no Gradle build or Minecraft runtime validation.

- `real-provider-fullschema-5case-20260718/real-llm-stability.json` — SHA-256 `11a66e9add7e4730dc5e9306477d405d416e153a44d469ef0919b840fa83d359`
- `real-provider-fullschema-5case-20260718/real-llm-stability.md` — SHA-256 `d677ccf4cd00dc3f1a0639da06d931508e4bafcc7fd637b64e7297beac5df008`

## real-provider-decomposed-basic-retry-20260718

- Status: `complete`
- Provider: `real-provider`
- Source run: `workspace/real-llm-stability-runs/resume-ab-20260718-decomposed-basic-retry/.agent`
- Validation: `provider, schema, generator, audit`
- Boundary: A separate retry of the failed decomposed basic_ruby case passed. It records sampling variability and does not change the original batch result from 4/5. No Gradle build or Minecraft runtime validation.

- `real-provider-decomposed-basic-retry-20260718/real-llm-stability.json` — SHA-256 `44eda43786adc66f5d0fcf4d1517aacfab766b03686aa9860f30e747f5c48c41`
- `real-provider-decomposed-basic-retry-20260718/real-llm-stability.md` — SHA-256 `c3d0294642feb4ff6971fbbdba756cf03667520c2fb3282f637dbac3b11a7073`

## real-provider-decomposed-5case-fix1-20260718

- Status: `complete`
- Provider: `real-provider`
- Source run: `workspace/real-llm-stability-runs/resume-ab-20260718-decomposed-5case-fix1/.agent`
- Validation: `provider, schema, generator, audit`
- Boundary: Post-fix decomposed batch result: 5/5 strict success and audit 5/5. The fix filters recipes with missing internal dependencies, canonicalizes vanilla recipe references, and prevents recipe ID collisions. No Gradle build or Minecraft runtime validation.

- `real-provider-decomposed-5case-fix1-20260718/real-llm-stability.json` — SHA-256 `f8c3f28c6a3cfd83cffc6158022db7101c9399ac9a384393d09fe1d54a304f0f`
- `real-provider-decomposed-5case-fix1-20260718/real-llm-stability.md` — SHA-256 `12175a926147a3d7302ad194cc2c1f0097c62c8851d5ea20f4ed59bd1f0bed7e`
