# Controlled Java Extension

> RC1 定位：Controlled Java Extension 是 `ModSpec` 中的窄 Java 扩展规格，不是自由 Java patch。

## 作用

它允许 planner 表达少量 additive helper class，由 deterministic generator 生成到 managed package 中，并保留 diff、report 和 rollback evidence。

## 示例

```json
{
  "type": "java_extension",
  "id": "safe_info_extension",
  "class_name": "SafeInfoExtension",
  "purpose": "Expose a tiny compile-time helper.",
  "allowed_imports": [
    "net.minecraft.network.chat.Component"
  ],
  "methods": [
    {
      "name": "describe",
      "return_type": "String",
      "return_value": "Controlled Java extension generated from ModSpec."
    }
  ]
}
```

## Safety Rules

- additive only；
- generated package only；
- allowlisted imports；
- `String` return type；
- forbidden token checks；
- audit/build gate；
- rollback evidence。

## Evidence

```text
.agent/java-extension-report.json
.agent/java-extension-diff.md
.agent/java-extension-rollback-report.json
```

## 与 RC1 Tool Loop 的关系

Controlled Java Extension 是规格输入层；`apply_structured_patch` 是 workspace 修复工具。两者都体现同一原则：LLM 不自由写完整项目，写入必须受结构化契约约束。
