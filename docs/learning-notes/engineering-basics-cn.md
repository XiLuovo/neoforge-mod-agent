# 工程基础小词典

> 文档定位：学习项目过程中遇到的工程基础概念。这里不展开项目主流程，只解释容易卡住的小词。

## fallback 是什么

`fallback` 是备用路径或兜底方案。

在本项目里，一个典型场景是：

```text
请求使用真实 LLM 规划 ModSpec
-> 真实 LLM 调用失败，例如缺少 API key、网络超时、输出 JSON 不合法
-> 系统改用 mock provider 或规则 planner 继续跑
-> 最后生成成功
```

这里“改用 mock provider 或规则 planner 继续跑”就是 fallback。

要注意：

```text
fallback 成功 != 真实 LLM 成功
```

因为最后成功可能是备用路径完成的，不一定是 real LLM 真正完成的。

## 备用路径的意义

备用路径的意义是让工程链路不要因为真实 LLM 的外部不稳定而完全停摆。

真实 LLM 可能遇到：

- 没有配置 API key。
- 网络超时。
- 模型服务不可用。
- 返回内容不是合法 JSON。
- 成本、限流或超时问题。
- 输出不符合 `ModSpec` schema。

fallback 可以证明：

```text
自然语言 -> ModSpec -> generator -> audit -> replay
```

这条工程链路本身是通的。

但 fallback 不能证明真实模型能力足够好。真实 LLM 能力需要单独用 real provider、prompt trace、LLM engineering report 和失败样本验证。

## 工程稳定性是什么

工程稳定性指的是：程序在正常条件下能稳定跑完，不会今天能跑、明天莫名其妙跑不通。

例如同样运行：

```text
agent generate -> 生成 workspace -> audit 通过 -> replay 生成
```

如果每次都能稳定完成，就说明这条工程链路比较稳定。

## 可复现是什么

可复现指的是：同样的输入、同样的环境，别人或未来的你再跑一次，能得到相同或可预期的结果。

例如：

```text
输入：Create a ruby mod with a ruby item, ruby block and ruby ore.
provider：mock
结果：生成 ruby_mod，包含 ruby、ruby_block、ruby_ore 等内容，audit 通过
```

如果今天能跑出来，明天还能跑出来，换一台机器配置好环境也能跑出来，这就叫可复现。

## CI 是什么

`CI` 是 `Continuous Integration`，中文一般叫持续集成。

可以先理解成：

```text
每次代码有变动时，自动跑一遍检查，确认项目没有被改坏。
```

CI 常见检查包括：

- 环境诊断。
- 单元测试。
- 示例生成。
- schema 检查。
- audit。
- 质量门禁。

## 为什么 CI 常用 mock

CI 需要稳定、便宜、可重复，所以通常不希望依赖真实 LLM。

真实 LLM 会带来不稳定因素：

- CI 环境可能没有 API key。
- 网络可能失败。
- 模型输出可能每次不同。
- API 调用有成本。
- 模型服务可能限流。

mock provider 是固定逻辑，适合 CI 验证工程链路。

一句话：

```text
CI 是自动体检，mock 让体检结果稳定。
```

## 本项目有 CI 吗

有。

CI 配置在：

```text
.github/workflows/quality-gate.yml
```

触发条件包括：

- push 到 `main`。
- pull request。
- 手动触发 `workflow_dispatch`。

核心命令是：

```powershell
python -m agent.cli quality-gate --run-name ci-quality-gate --json
```

它还会上传质量门禁报告：

```text
workspace/quality-gate-runs/ci-quality-gate/.agent/**
workspace/doctor-runs/ci-quality-gate-doctor/.agent/**
```

所以本项目的 CI 可以理解为：在 GitHub Actions 上运行项目自己的 `quality-gate` 自动体检。

