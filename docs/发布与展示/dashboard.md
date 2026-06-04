# Web Demo Dashboard

> 文档定位：这是 Web Demo / Dashboard 专项材料，不是主学习入口。需要理解本地演示台和静态报告页面时再读。

## Local Project Console

`web-demo` 当前定位是本地项目控制台，而不是单纯展示页。它仍然使用 Python 标准库 HTTP server，不引入前端框架或第三方依赖；启动后在浏览器打开 `http://127.0.0.1:8765/`，可以生成/修改 workspace、查看实时运行日志、audit/build、RAG / repair、Direct Code Lane evidence、资源预览和 Free-Code Lab / Harvest 只读线索。

Direct Code Lane 在控制台里只展示和汇总结构化 workspace patch 的证据链：review、snapshot、audit/build gate、diff 和 rollback evidence。控制台不把项目包装成通用 Coding Agent，也不开放任意文件编辑。

## V3.8 Self-Healing Repair 可视化

V3.8 让 Web Demo 和静态 Dashboard 都能展示 repair agent 的安全修复链路。它不是新增一个危险的“破坏文件”按钮，而是把已有 agent run 中的 repair payload 和 `.agent` repair artifacts 读出来，变成可演示、可复盘的界面。

Web Demo 新增：

- `Self-Healing` 标签页。
- `repairStatus` 摘要区，展示 `repair_needed`、`repair_executed`、`repair_success`、root causes、repair actions 和 attempts。
- workspace detail API 会读取 `.agent/agent-repair-plan.json` 与 `.agent/repair-loop-report.json`。

Dashboard 新增：

- `Self-Healing Repair` 区块。
- repair 指标：`repair_runs`、`repair_needed`、`repair_executed`、`repair_success`、`repair_attempts`。
- artifact 链接：agent repair plan 与 repair loop report。

推荐验证：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli web-demo --smoke --json
py -3.11 -m agent.cli dashboard --run-name v38-dashboard --json
```

## V3.5 RAG 知识库管理台

V3.5 让 `web-demo` 可以直接浏览内置 NeoForge RAG 知识库。这个管理台是只读的，用于解释和演示 planner 会检索到哪些本地规则。

页面新增：

- `RAG Knowledge` 标签页。
- 知识库关键词搜索。
- category / capability / tag 筛选。
- 知识条目详情展示。

后端 API：

```text
GET /api/knowledge?query=&category=&capability=&tag=&limit=50
```

返回内容包括：

- `id`
- `title`
- `category`
- `capability`
- `tags`
- `summary`
- `content`
- `source`
- `score`
- `matched_terms`
- `snippet`

## V3.4 实时运行日志与 Build 输出

V3.4 让 `web-demo` 的 generate / modify 操作改为后台 job 模式。页面不会只在请求结束后展示结果，而是通过轮询 job 状态更新运行日志。

页面新增：

- `Run Log` 标签页：展示 job queued、running、success、error 等运行事件。
- `Build Output` 标签页：勾选 build 后，展示 Gradle combined log、stdout、stderr 的尾部内容。

后端 API：

```text
POST /api/jobs/generate
POST /api/jobs/modify
GET  /api/job?id=<job_id>
```

Build 输出来源：

```text
.agent/logs/gradle-build.log
.agent/logs/gradle-build.stdout.log
.agent/logs/gradle-build.stderr.log
```

原有同步 API 仍然保留：

```text
POST /api/generate
POST /api/modify
```

## V3.3 Workspace 管理与 Modify

V3.3 让 `web-demo` 支持已有 workspace 管理和增量修改。它复用现有 `AgentOrchestrator.run_modify`，不会让 LLM 直接写 Java/JSON/PNG。

页面新增：

- workspace 下拉选择。
- 刷新 workspace 列表。
- 读取 `.agent/modspec.json`。
- 输入 modify request。
- 展示 merge 结果：`added` / `updated` / `skipped`。
- 展示 `ModSpec diff`。
- 展示 modify 后的 audit/build/agent trace。

后端 API：

```text
GET  /api/workspaces
GET  /api/workspace?name=<workspace>
POST /api/modify
```

推荐 smoke：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli web-demo --smoke --json
```

## V3.2 Interactive Web Demo

V3.2 新增交互式本地演示台。它和原来的 `dashboard` 静态报告互补：`dashboard` 适合生成一次可离线打开的报告，`web-demo` 适合现场输入 prompt 并实时运行 agent。

启动命令：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli web-demo --host 127.0.0.1 --port 8765
```

浏览器打开：

```text
http://127.0.0.1:8765/
```

页面能力：

- 输入 prompt。
- 选择 planner：`rules` / `mock-llm` / `real-llm` / `auto-mock` / `auto-real`。
- 可选运行 audit 和 build。
- 展示 `ModSpec`。
- 展示生成文件列表。
- 展示 audit、build、eval 结果。
- 展示 agent trace：steps、decisions、prompt traces。

快速验证命令：

```powershell
py -3.11 -m agent.cli web-demo --smoke --json
```

注意：`web-demo` 是本地开发演示服务，默认绑定 `127.0.0.1`。真实 LLM 需要配置 OpenAI-compatible 环境变量。

## V3.1 RAG Hit Summary

从 V3.1 开始，dashboard 会汇总普通 knowledge query 和 agent planner prompt trace 中的 RAG 命中结果，并渲染 `RAG Hit Summary`。

这个区块用于展示：

- dashboard 查询和 agent planner 一共命中了多少知识片段。
- 命中的知识类别，例如 `behavior`、`worldgen`、`assets`、`content`。
- 命中的能力分类，例如 `right_click_behavior`、`overworld_ore`、`procedural_textures`。
- 每个 knowledge query 的命中条目和类别计数。

## V3.0 Multi-Agent Trace

从 V3.0 开始，dashboard 会读取 showcase 中的 `.agent/agent-run.json` 和 `.agent/agent-trace-summary.json`，并在页面里渲染 `Multi-Agent Trace` 区块。

这个区块用于展示：

- 每次 agent run 的 request、成功状态、决策数和 prompt trace 数量。
- `planner_agent`、`reviewer_agent`、`executor_agent`、`auditor_agent`、`repair_agent` 的 role card。
- 每个 role 的 inputs、outputs 和第一条决策理由。
- prompt trace、agent decisions、trace summary 等原始 artifact 链接。

V2.5 新增了一个本地静态 Web dashboard，用于作品集和面试演示。

它面向一个很实际的场景：打开一个 HTML 文件，就能讲清楚整个项目故事，而不是先让观看者读一堆原始 JSON。

## Command

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli dashboard --run-name v25-dashboard --json
```

Output:

```text
workspace/dashboard-runs/v25-dashboard/index.html
workspace/dashboard-runs/v25-dashboard/.agent/dashboard-data.json
workspace/dashboard-runs/v25-dashboard/.agent/dashboard-report.md
```

Fast mode without showcase:

```powershell
py -3.11 -m agent.cli dashboard --run-name v25-dashboard-fast --no-showcase --json
```

## 展示内容

- dashboard 生成流水线状态。
- showcase 运行摘要。
- Content Coverage 内容能力覆盖率。
- capability matrix 能力矩阵和能力 id。
- RAG 知识查询与召回片段。
- 原始 JSON / Markdown 报告链接。
- 内嵌 `dashboard-data.json`，方便透明检查。

## 数据来源

dashboard 复用项目里已有的确定性报告：

- `CapabilityCatalog`
- `KnowledgeQueryRunner`
- `ShowcaseRunner`

从 V2.9 开始，它还会根据 capability matrix 和默认 eval/golden expectations 生成内容覆盖率摘要。这个信息主要服务于作品集讲解：当前声明支持的内容能力里，哪些已经被自动验收覆盖？

By default it runs the showcase flow with:

```text
planner = llm
llm_provider = mock
build = false
audit = true
```

因此 dashboard 默认仍然是离线、快速、可复现的。

## 为什么重要

在 V2.5 之前，项目已经有不少机器可读报告，但它们分散在不同文件里：

- `.agent/agent-run.json`
- `.agent/audit-report.json`
- `.agent/eval-report.json`
- `.agent/capabilities.json`
- `.agent/rag-context.json`

V2.5 把这些报告收束成一个可视化入口。对实习简历和面试尤其有用，因为你可以把项目展示成一个完整的 Agent 工程系统，而不是一堆零散 CLI 命令。

## 当前限制

- dashboard 是静态 HTML，不是实时服务端应用。
- 它只展示报告，不编辑或控制生成的 workspace。
- 当前刻意保持零前端框架依赖。
- 默认不运行 build smoke。
