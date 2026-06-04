## V2.1 Repair Loop 2.0

目标：把已有 repair artifacts 推进一步，形成安全的自动修复闭环。

完成内容：

- 新增 `repair_loop.py`。
- 新增 CLI 命令：
  - `repair-loop`
- `repair-loop` 支持：
  - `--max-attempts`
  - `--audit` / `--no-audit`
  - `--build` / `--no-build`
  - `--json`
- 第一版自动修复策略为：
  - `regenerate_managed_files`
- 修复过程会根据 `.agent/modspec.json` 重新生成受控文件：
  - Java source
  - item/block models
  - textures
  - lang files
  - loot tables
  - tags
  - worldgen JSON
  - `pack.mcmeta`
- 每次 repair loop 写入：
  - `.agent/repair-loop-report.json`
  - `.agent/repair-loop-report.md`
- 如果 build 失败，继续复用已有 repair artifacts：
  - `.agent/debug-context.md`
  - `.agent/fix-request.md`
  - `.agent/suspected-errors.json`
- 新增 `docs/验证与可靠性/repair-loop.md`。
- 新增 `tests/test_repair_loop.py`，覆盖：
  - 健康 workspace 不做修复
  - 删除生成的 item model 后 repair-loop 可自动恢复
- package metadata 更新到 `2.1.0`。

价值：

- 修复闭环从“只给修复上下文”升级为“能自动修复一类安全问题”。
- 保持安全边界：V2.1 不让 LLM 直接改 Java，只从 ModSpec 重生成受控文件。
- 对演示很有用：可以故意删除一个生成文件，然后运行 `repair-loop` 展示自动恢复能力。
