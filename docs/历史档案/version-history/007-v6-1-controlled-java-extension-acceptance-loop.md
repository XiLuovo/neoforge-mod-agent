## V6.1 Controlled Java Extension Acceptance Loop

目标：把 V6 的“受控新增 Java class”补成可证明版本，让演示时能说清楚：允许一点 Java，但必须经过 sandbox、diff、rollback、audit 和 Gradle build gate。

完成内容：

- package metadata 更新到 `6.1.0`。
- `.agent/java-extension-report.json` 新增 `build_gate`，在 `--build` 后回填 `pass` / `fail`，`--no-build` 时保持 `not_run`。
- 新增 `.agent/java-extension-diff.md`，把每个 extension class 渲染成 new-file diff，证明只新增托管 class。
- 新增 `.agent/java-extension-rollback-report.json` / `.md`，build 失败时标记 rollback recommended，并列出 managed files 和回滚步骤。
- 新增 sandbox 违规样例 `examples/invalid/controlled_java_extension_violation.json`，用于证明非法 import / forbidden token 会在生成前被拒绝。
- README 和 V6 文档补充 V6.1 demo 证据链。

快速验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_generation_audit tests.test_capabilities tests.test_dashboard -v
py -3.11 -m agent.cli generate-from-spec .\examples\controlled_java_extension.json --workspace-name v61-java-extension-smoke --overwrite --audit --no-build --json
py -3.11 -m agent.cli generate-from-spec .\examples\controlled_java_extension.json --workspace-name v61-java-extension-build --overwrite --audit --build --json
```

边界：

- V6.1 仍然不是任意 Java patch 生成器。
- build gate 是验收证据，不是绕过 validator/audit 的许可。
- rollback 报告只处理 generated managed extension files，不会删除或修改用户手写文件。
