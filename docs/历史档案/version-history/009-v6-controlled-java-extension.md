## V6 Controlled Java Extension

目标：在不放开任意 Java patch 的前提下，给生成器增加一个受控 Java 扩展口。LLM / rules 仍然只能输出结构化 `ModSpec`，确定性生成器只在 `<package>.extension` 下新增托管 class。

完成内容：

- package metadata 更新到 `6.0.0`。
- `ModSpec` 新增 `java_extension` / `java_extensions`，覆盖 `class_name`、`purpose`、`explanation`、`allowed_imports` 和 String-returning `methods`。
- 新增 `JavaExtensionGenerator`，只生成 `src/main/java/<package>/extension/<ClassName>.java` 和 `.agent/java-extension-report.*`。
- validator / auditor 检查 class/method 命名、导入 allowlist、禁止 token、报告文件、package、final class 和 static method。
- rules planner / mock LLM / LLM schema / modify merge / capabilities / knowledge base / golden tests 接入 V6。
- 新增示例 `examples/controlled_java_extension.json` 和文档 `docs/规格与生成/controlled-java-extension.md`。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_generation_audit tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli generate-from-spec .\examples\controlled_java_extension.json --workspace-name v60-java-extension-smoke --overwrite --audit --no-build --json
```

边界：

- V6 不是任意 Java patch 生成器。
- 不允许改已有源码、不允许 Gradle patch、不允许 raw package/import、不允许文件/网络/进程/反射/线程等危险 API。
- `--audit --no-build` 只证明结构和沙盒约束；正式验收仍需要 Gradle build gate。
