# LLM Engineering Report

> 文档定位：这是 LLM 工程报告专项材料，不是主学习入口。需要理解 provider、prompt、retry、usage/cost 和可靠性摘要时再读。

这份文档解释 `llm-engineering-report` 怎么用，以及它在面试里怎么讲。

它解决的问题是：不要只说“我接了 LLM provider”，而是把 prompt、provider、重试、JSON 修复、schema 校验、token/cost 和 fallback 都变成可检查的工程证据。

## 运行命令

对一个已生成的 workspace 运行：

```powershell
py -3.11 -m agent.cli llm-engineering-report workspace/<run> --run-name local-llm-engineering --json
```

也可以直接指向 `.agent` 目录或具体证据文件：

```powershell
py -3.11 -m agent.cli llm-engineering-report workspace/<run>/.agent --json
py -3.11 -m agent.cli llm-engineering-report workspace/<run>/.agent/prompt-trace.json --json
py -3.11 -m agent.cli llm-engineering-report workspace/<run>/.agent/llm-stability.json --json
```

输出位置：

```text
workspace/llm-engineering-runs/<run-id>/.agent/llm-engineering-report.json
workspace/llm-engineering-runs/<run-id>/.agent/llm-engineering-report.md
```

## 报告里有什么

报告会聚合这些来源：

- `.agent/prompt-trace.json`
- `.agent/agent-run.json` 里的 `prompt_traces`
- `.agent/llm-stability.json`

核心字段包括：

- prompt kind、prompt version、system prompt hash、输入 hash
- provider、model、response format、temperature、stream、timeout、max retries
- provider config、provider health、capability metadata、pricing
- token usage、estimated cost
- retry attempts、schema retry attempts、parse attempts、schema validation attempts
- JSON repair 是否发生
- fallback 是否被检测到

这里的 prompt version 是低成本实现：如果 trace 里没有显式版本，就用 system prompt 的 SHA-256 短 hash 当作稳定指纹。这样不泄露 prompt 原文，也能比较不同运行是否用了同一版提示词。

## 和 benchmark 的区别

`benchmark-report` 回答的是：

> 哪个 provider / eval run 的工程结果更好？

`llm-engineering-report` 回答的是：

> 这次 LLM 调用本身是怎么配置、怎么重试、怎么修复、怎么计费、有没有 fallback？

两者可以配合讲：benchmark 看结果，LLM engineering 看调用过程。

## 面试口径

可以这样说：

> 我没有把 LLM 当黑盒调用，而是把它作为工程组件管理。每次运行都会落 prompt trace 和 LLM stability artifact，再用 `llm-engineering-report` 汇总 prompt 指纹、response format、temperature、timeout/retry、schema retry、JSON repair、token/cost 和 fallback 证据。这样换模型、换 prompt 或 provider 不稳定时，可以复盘到底是模型输出问题、schema 问题、配置问题，还是 fallback 造成的假成功。

注意不要夸大：

- 现在是单次运行聚合，不是完整线上观测平台。
- prompt A/B 对比还可以继续接入 benchmark。
- cost 是基于 provider usage metadata 的估算，不是账单系统。
