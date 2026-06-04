## V0.5 LLM Planner

目标：加入 LLM 能力，但不允许 LLM 直接写项目文件。

完成内容：

- 增加可选 `llm` planner，同时保持 `rules` 为默认模式。
- 增加 `auto` planner。
- 增加 `MockLLMClient`，用于离线确定性测试。
- 增加 OpenAI-compatible client，支持通过环境变量接入真实模型服务。
- 增加 LLM planner artifacts：
  - planner input
  - raw LLM JSON
  - normalized LLM JSON
  - planner warnings
- 将 LLM 输出 normalize 并 validate 成 `ModSpec`。

价值：

- 在保持确定性生成的前提下引入 LLM。
- 避免“让模型直接吐 Java/Gradle 文件”带来的不可控风险。
