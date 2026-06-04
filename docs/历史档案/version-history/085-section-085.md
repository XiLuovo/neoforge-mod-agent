## 当前架构总结

项目当前支持：

- `generate`：从自然语言或 spec 创建新 workspace
- `modify`：对已有 workspace 做自然语言增量修改
- `audit`：确定性检查 workspace 与 `ModSpec` 是否一致
- `build`：Gradle 构建验证
- `repair`：生成构建失败修复上下文
- `agent generate`：多角色编排的新项目生成
- `agent modify`：多角色编排的已有项目修改
- `eval`：面向 Agent 工作流的 benchmark 评测
- `unittest`：快速自动化回归检查
- `quality-gate`：一键可靠性门禁
- GitHub Actions CI：push / pull request 时自动运行质量门禁
- `doctor`：本地环境诊断
- `quality-gate` 内置 doctor preflight
- `showcase`：一键生成项目展示报告
- `capabilities`：结构化项目能力矩阵导出

核心设计原则：

```text
LLM / natural language -> ModSpec -> deterministic Java/JSON generation -> audit/build/repair
```

这让 LLM 输出保持受控，也让生成项目更容易测试、复现和调试。
