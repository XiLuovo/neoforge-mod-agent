# 验证与可靠性

RC1 中，验证不只看静态报告：`agent bench` 会运行真实 develop/repair/reviewer/tool-calling 流程，并从 trace、reviewer report、audit/build result 和 rollback evidence 计算指标。

> 这里放测试、评测、故障注入、自修复和 CI。

## 推荐顺序

1. [testing.md](testing.md)
2. [quality-gate.md](quality-gate.md)
3. [repair-loop.md](repair-loop.md)
4. [benchmark-report.md](benchmark-report.md)
5. [evidence-chain-report.md](evidence-chain-report.md)
6. [eval.md](eval.md)
7. [failure-lab.md](failure-lab.md)
8. [failure-repair-demo.md](failure-repair-demo.md)
9. [failure-repair-evidence-summary.md](failure-repair-evidence-summary.md)
10. [repair-eval.md](repair-eval.md)
11. [doctor.md](doctor.md)
12. [ci.md](ci.md)
13. [golden-tests.md](golden-tests.md)

## 文档职责

- [testing.md](testing.md)：自动化测试入口。
- [quality-gate.md](quality-gate.md)：质量门禁。
- [doctor.md](doctor.md)：环境诊断。
- [ci.md](ci.md)：CI / GitHub Actions。
- [golden-tests.md](golden-tests.md)：黄金快照测试。
- [eval.md](eval.md)：评测和 benchmark。
- [repair-loop.md](repair-loop.md)：受控修复循环。
- [failure-lab.md](failure-lab.md)：故障注入。
- [failure-repair-demo.md](failure-repair-demo.md)：失败 -> audit -> repair 演示。
- [failure-repair-evidence-summary.md](failure-repair-evidence-summary.md)：本地失败注入、tool-calling repair 和面试展示证据总览。
- [repair-eval.md](repair-eval.md)：自修复量化。
- [benchmark-report.md](benchmark-report.md)：benchmark 页面。
- [evidence-chain-report.md](evidence-chain-report.md)：证据链报告。

## 继续阅读

- [../Agent与能力/README.md](../Agent与能力/README.md)
- [../发布与展示/README.md](../发布与展示/README.md)
