## V3.4 Web Demo 实时运行日志 / Build 输出展示

目标：让 Web Demo 更像真实的 Agent 控制台，而不是只在执行结束后展示一份静态结果。演示 generate / modify 时，用户可以看到后台 job 状态、运行事件和 Gradle build 输出尾部。

完成内容：

- `web_demo.py` 新增内存 job 管理：
  - `start_generate_job`
  - `start_modify_job`
  - `get_job`
- 新增 Web Demo job API：
  - `POST /api/jobs/generate`
  - `POST /api/jobs/modify`
  - `GET /api/job?id=<job_id>`
- Web 页面 generate / modify 按钮改为异步 job 模式，前端轮询 job 状态。
- 页面新增：
  - `Run Log` 标签页
  - `Build Output` 标签页
- build 输出展示会读取：
  - `.agent/logs/gradle-build.log`
  - `.agent/logs/gradle-build.stdout.log`
  - `.agent/logs/gradle-build.stderr.log`
- 原有同步 API 保留：
  - `POST /api/generate`
  - `POST /api/modify`
- capability matrix 新增 `web_demo_live_logs`。
- package metadata 更新到 `3.4.0`。

价值：

- 面试演示时可以解释“Agent 不是黑盒等结果”，而是有可观察的运行过程。
- 勾选 build 后，可以直接在浏览器里看到 Gradle 输出尾部，失败时更容易讲清楚 build / repair 链路。
- 继续保持核心边界：自然语言 / LLM -> ModSpec patch -> deterministic generator -> audit/build/repair。
