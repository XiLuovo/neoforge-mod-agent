## V0.6 Modify 已有项目

目标：支持对已经生成的项目做增量修改。

完成内容：

- 增加 `modify` 命令。
- 使用 `.agent/modspec.json` 作为已有项目的真相源。
- 将修改请求规划成 patch，而不是重新生成整个项目。
- 增加 merge 行为，输出 `added`、`updated`、`skipped`。
- 只清理 `generation-summary.json` 中记录的受控生成文件，保留用户自定义文件。
- 增加 modify artifacts：
  - `.agent/modspec.before.json`
  - `.agent/modspec.after.json`
  - `.agent/last-modify-request.txt`
  - `.agent/modify-summary.json`
  - `.agent/modify-history.jsonl`

价值：

- 增加第二条核心工作流：`modify`。
- 让重复 modify 请求对已有 feature 具备幂等基础。
- 让生成工作区从一次性输出目录变成可持续修改的项目。
