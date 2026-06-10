# Screenshots And Visual Evidence

RC1 展示时优先展示可回放 evidence，而不是旧静态截图。

## 推荐截图

- `agent develop` 终端输出；
- generated workspace 的 `.agent/agent-run.json`；
- `.agent/tool-call-trace.json` 中的真实 tool action；
- `.agent/reviewer-report.json`；
- `.agent/structured-patch-diff.md`；
- `.agent/structured-patch-rollback-report.json`；
- `agent-benchmark-report.html` 的 metrics 区块。

## 现有资产

`docs/assets/` 中的旧 dashboard 或 benchmark 图片可作为历史展示素材，但不要把它们当作 RC1 主证据。RC1 主证据以新运行生成的 `.agent` 文件和 trace-backed benchmark report 为准。

## 截图原则

- 截图要能指向真实文件路径；
- 不展示密钥、环境变量或私有 prompt；
- 需要说明 reviewer 不是最终 gate；
- 需要保留 audit/build result 和 rollback evidence。
