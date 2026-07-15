# Screenshots And Visual Evidence

当前展示时优先展示可回放 evidence，而不是旧静态截图。

## 推荐截图

- `evidence/runtime/attachments/` 中的 Minecraft 客户端人工验收截图；
- `agent develop` 终端输出；
- generated workspace 的 `.agent/agent-run.json`；
- `.agent/tool-call-trace.json` 中的真实 tool action；
- `.agent/rag-decision-trace.json` 中的 RAG policy、queries 和 citations；
- `.agent/reviewer-report.json`；
- `.agent/structured-patch-diff.md`；
- `.agent/structured-patch-rollback-report.json`；
- `agent-benchmark-report.html` 的 metrics 区块。

## 现有资产

`evidence/runtime/attachments/` 当前保存 3 个人工 runtime case 的截图：Basic Ruby 和 Speed Crystal 为 passed，modify/worldgen case 因 `/place feature ruby_mod:ruby_ore` 失败而整体记为 failed。展示自然 Ruby Ore 截图时必须同时说明这个整体状态，不能把局部通过扩大为 worldgen 全链路通过。

`docs/assets/` 中的旧 dashboard 或 benchmark 图片可作为历史展示素材，但不要把它们当作当前主证据。当前主证据以公开冻结 report、`.agent` trace、runtime checklist 和带 hash 的截图附件为准。

## 截图原则

- 截图要能指向真实文件路径；
- 不展示密钥、环境变量或私有 prompt；
- 需要说明 reviewer 不是最终 gate；
- 需要保留 audit/build result 和 rollback evidence。
- runtime 截图要关联具体 case、JAR hash 和逐项 checklist；passed/failed 结果必须原样保留。
