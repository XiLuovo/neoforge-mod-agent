# RC1 Showcase

RC1 showcase 的目标是让项目展示为一个可验证、可回放、可评测的领域 Coding Agent。

## 展示顺序

1. 打开 [../总览/rc1-learning-guide.md](../总览/rc1-learning-guide.md)，用 1 分钟说明项目定位。
2. 运行 `agent develop`，展示 baseline generation 和 tool-call trace。
3. 运行 `agent repair`，展示 structured patch、snapshot、rollback evidence。
4. 打开 `.agent/reviewer-report.json`，说明 reviewer 只审查风险，不替代 gate。
5. 运行 `agent bench`，展示 trace-backed metrics。
6. 打开 [agent-rc1-showcase.md](agent-rc1-showcase.md)，对比普通 generator 和当前 agent。

## 推荐命令

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent develop "Create a ruby mod with a ruby item, ruby block and ruby ore." --planner llm --llm-provider mock --workspace-name rc1-showcase --no-build --json
py -3.11 -m agent.cli agent repair rc1-showcase --goal "Fix audit failures using safe structured patches." --planner llm --llm-provider mock --max-iterations 5 --no-build --audit --json
py -3.11 -m agent.cli agent bench --llm-provider mock --eval-limit 1 --repair-limit 1 --no-build --audit --json
```

## 讲解重点

- 不是让 LLM 一次性写完整 Mod；
- planner、generator、tool loop、reviewer、audit/build 各司其职；
- tool call 和 reviewer 都有真实 JSON evidence；
- benchmark 读真实 trace，而不是静态报告；
- Minecraft runtime 仍是边界，不要夸大成自动游戏内验收。
