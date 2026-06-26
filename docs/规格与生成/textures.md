# Textures

> RC1 定位：Textures 文档说明 deterministic generator 如何生成程序化资源和预览，不涉及外部图像生成。

## 生成内容

- item texture；
- block texture；
- model JSON；
- blockstate JSON；
- atlas / preview where supported；
- resource quality report。

## Evidence

```text
.agent/resource-quality-report.json
.agent/generation-summary.json
.agent/audit-report.json
```

## 边界

- 程序化贴图不是最终美术资源。
- 不调用外部图片生成服务。
- 不让 LLM 写 PNG 字节。
- Minecraft runtime 中的视觉效果仍需人工检查。
