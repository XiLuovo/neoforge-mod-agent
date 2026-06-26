# Resource Quality

> RC1 定位：Resource Quality 是 deterministic resource generation 的报告层，用来说明资源覆盖、预览和已知限制。

## 关注点

- texture profile；
- palette；
- model variant coverage；
- structure preview；
- dashboard-ready summary；
- missing or placeholder assets。

## 输出

```text
.agent/resource-quality-report.json
.agent/resource-quality-report.md
```

## 边界

- 不代表最终美术质量。
- 不替代人工视觉检查。
- 不自动运行 Minecraft client。
- 资源问题仍应通过 audit/build、reviewer recommended checks 或 tool-calling repair/refine 处理。
