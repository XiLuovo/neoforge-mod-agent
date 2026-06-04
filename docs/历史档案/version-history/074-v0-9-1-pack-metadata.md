## V0.9.1 Pack Metadata

目标：将 `pack.mcmeta` 纳入正式生成产物。

完成内容：

- 生成 `src/main/resources/pack.mcmeta`。
- 将 `pack.mcmeta` 记录到 `generation-summary.json`。
- 扩展 audit 检查：
  - 文件存在
  - JSON 可解析
  - 包含 `pack` object
  - 包含 `pack.description`
  - 包含整数型 `pack.pack_format`
- 保持对旧 workspace 的兼容。

价值：

- 补齐资源包 / 数据包基础元信息。
- 让 V1.0 前的 audit 更完整。
