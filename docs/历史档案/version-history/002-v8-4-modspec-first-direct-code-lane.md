## V8.4 ModSpec-First + Direct Code Lane

目标：把 agent 从“只能输出 ModSpec/DSL”的单一路径升级为 `ModSpec-first` 混合架构。默认仍优先生成可审计的 `ModSpec`，当需求超出 ModSpec 表达能力时，进入 Direct Code Lane，以结构化补丁的方式修改生成 workspace。

完成内容：

- `agent generate` / `agent modify` 新增 `--code-lane {hybrid,modspec,direct}`，默认 `hybrid`。
- 新增 Direct Code Plan / Review / Apply 证据链，只允许 JSON `write_file` 和精确一次 `replace_text`。
- Direct Code Lane 限定在生成 workspace 内，禁止绝对路径、路径越界、`.git`、Gradle wrapper jar、build output 和工具项目源码。
- Runtime 的 stage state 扩展为 intent contract，可记录 `modspec`、`direct_code_plan` 和 `routing_decision`。
- Replay evidence 新增 `direct_code_reviewer` / `direct_code_agent` 角色输出。
- 每次 Direct Code apply 写入 plan、review、diff、report、rollback report 和 affected-file snapshots。
- Direct Code Lane 强制 audit plus Gradle build；失败时 run 不算成功，并把 rollback 标记为 recommended。
- 新增文档 [direct-code-lane.md](../../Agent与能力/direct-code-lane.md) 和 [project-limitations.md](../../总览/project-limitations.md)。

快速验证：

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli agent generate "Create a ruby mod with a custom helper outside ModSpec." --planner llm --llm-provider mock --code-lane hybrid --workspace-name v84-direct-code-smoke --overwrite --build --json
```

边界：

- Direct Code Lane 不是通用 coding agent，不接受自由 diff。
- 第一版没有 AST patch、自动 direct-code repair-loop、事务式自动恢复或 Minecraft runtime smoke 自动化。
- 当前本地回归基线：`py -3.11 -m unittest discover -s tests -v` 通过 163 个 unittest case。
