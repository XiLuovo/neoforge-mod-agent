# Real vs Mock LLM

mock provider 和 real provider 的职责不同。

## Mock Provider

用于：

- 本地 smoke；
- CI；
- deterministic unit tests；
- reviewer/tool loop case 覆盖；
- release demo 的稳定回放。

mock provider 也必须走 `complete_json()` 和真实 tool action schema，不能绕过 LLM 接口。

## Real Provider

用于：

- 验证真实模型能否遵守 schema；
- 观察 tool selection 质量；
- 检查 reviewer 风险判断；
- 收集失败模式。

## 统一评价标准

无论 mock 还是真实 provider，成功都不能只看模型回答。最终必须看：

- tool trace；
- reviewer report；
- audit/build gate；
- patch snapshot / rollback；
- benchmark metrics。

## 面试说法

> mock 是为了可复现测试，real provider 是为了验证模型遵守契约。两者都走同一个 JSON schema 和 tool loop，所以测试不会绕过真实架构。
