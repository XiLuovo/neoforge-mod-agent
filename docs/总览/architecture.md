# 架构图

> 文档定位：这是整体架构真相源。项目分层、数据流、DomainSpec / NeoForge plugin 边界以本文为准。

## 总体链路

```mermaid
flowchart LR
    A["自然语言需求"] --> B["Planner<br/>rules / mock LLM / real LLM"]
    B --> C["RAG 检索<br/>NeoForge 知识库"]
    C --> B
    B --> D["DomainSpec<br/>ModSpec / SpringApiSpec / UnityComponentSpec"]
    D --> E["Domain Plugin<br/>NeoForge 当前稳定实现"]
    E --> V["Validator"]
    V --> F["Deterministic Generator"]
    F --> G["Java / JSON / PNG / pack.mcmeta"]
    G --> H["Audit"]
    G --> I["Build"]
    H --> J["Repair Agent"]
    I --> J
    J --> K["Repair RAG + Repair Loop"]
    K --> F
    H --> L["Eval / Golden / Quality Gate"]
    I --> L
    L --> M["Dashboard / Replay / Portfolio Report"]
```

## 多 Agent 分工

```mermaid
flowchart TB
    P["Planner Agent<br/>自然语言 -> DomainSpec"] --> R["Reviewer Agent<br/>domain validator + 规则审查"]
    R --> E["Executor Agent<br/>确定性生成 workspace"]
    E --> A["Auditor Agent<br/>结构化验收"]
    A --> X{"是否失败?"}
    X -- "否" --> S["成功产物<br/>agent-run / dashboard / report"]
    X -- "是" --> RP["Repair Agent<br/>root cause + repair plan"]
    RP --> RG["Repair RAG<br/>检索修复知识"]
    RG --> RL["Repair Loop<br/>安全重生成 managed files"]
    RL --> A
```

## 关键边界

```mermaid
flowchart LR
    LLM["LLM / RAG"] -->|稳定层| SPEC["DomainSpec / ModSpec"]
    LLM -->|中间层| BEHAVIOR["Behavior DSL<br/>event / condition / action"]
    LLM -->|高级层| EXT["Controlled Java Extension / Patch Agent<br/>managed files only"]
    SPEC --> PLUGIN["Domain Plugin"]
    BEHAVIOR --> PLUGIN
    EXT --> SANDBOX["Sandbox / allowlist / managed files"]
    PLUGIN --> GEN["Python deterministic generator"]
    SANDBOX --> GEN
    GEN --> OUT["Java / JSON / PNG / Gradle resources"]
    LLM -. "禁止裸写 / 越界写 / 自由 diff" .-> OUT
```

更完整的三层解释见 [`docs/Agent与能力/llm-capability-layers-cn.md`](../Agent与能力/llm-capability-layers-cn.md)。

## 产物目录

```text
workspace/<name>/
  .agent/
    modspec.json
    generation-summary.json
    audit-report.json
    agent-run.json
    agent-decisions.md
    prompt-trace.json
    llm-stability.json
    rag-context.json
    repair-loop-report.json
    direct-code-plan.json
    direct-code-report.json
    harvest-candidate.json
  src/main/java/
  src/main/resources/
```

## DomainSpec 插件边界

```mermaid
flowchart TB
    RUNTIME["AgentRuntime<br/>planner / reviewer / executor / auditor / repair / trace"]
    REG["DomainSpecRegistry"]
    NF["minecraft.neoforge<br/>ModSpec<br/>stable"]
    SPR["spring.api<br/>SpringApiSpec<br/>planned"]
    UNI["unity.component<br/>UnityComponentSpec<br/>planned"]
    RUNTIME --> REG
    REG --> NF
    REG --> SPR
    REG --> UNI
    NF --> NFG["NeoForge generator / auditor / repair"]
```

## Direct Code Lane Architecture Addendum

The current architecture is a `ModSpec-first hybrid agent`, not a ModSpec-only generator. The default route still prefers `ModSpec`, Behavior DSL, and controlled extension intent. When the request is outside ModSpec expression, `agent generate` and `agent modify` can enter Direct Code Lane.

```mermaid
flowchart LR
    U["Natural language request"] --> P["Planner route_generation_request"]
    P --> IC["Intent contract: ModSpec + routing decision"]
    IC --> G["Deterministic NeoForge generation"]
    IC --> DCP["Optional Direct Code Plan: JSON write_file / replace_text"]
    G --> WS["Generated workspace"]
    DCP --> R["Direct Code Reviewer: path / token / package / rollback checks"]
    R --> A["Direct Code Agent: snapshot + apply + diff"]
    A --> WS
    WS --> Q["Audit + Gradle build gates"]
    Q --> E["Replay / reports / rollback evidence"]
```

Direct Code Lane does not accept free-form diffs, cannot modify this tool project, and cannot touch `.git`, Gradle wrapper jars, build outputs, or paths outside the generated workspace. Known gaps are tracked in [project-limitations.md](../总览/project-limitations.md).

当前只有 `minecraft.neoforge` 是稳定实现；`spring.api` 和 `unity.component` 是规划中的插件槽位，用来证明 runtime 和 spec 边界已经抽开。

## 2026-05-29 Capability Harvest Addendum

当前后续主线是 `Capability Harvest Loop`。它不是让 Direct Code Lane 继续膨胀成通用 coding agent，而是把“generate 覆盖不了的需求”放进隔离实验区，经过自动检查和人工 runtime checklist 后，再把成功模式沉淀回稳定 generator。

```mermaid
flowchart LR
    GAP["Generate gap"] --> LAB["Free-Code Lab<br/>copied experimental workspace"]
    LAB --> PLAN["Structured free-code plan"]
    PLAN --> APPLY["Safety review + apply patch"]
    APPLY --> CHECK["Audit + build + manual runtime checklist"]
    CHECK --> CAND["Harvest candidate"]
    CAND --> H{"固化建议"}
    H -- "reject" --> R["记录失败原因"]
    H -- "keep_as_lab_sample" --> S["保留实验样本"]
    H -- "harvest_into_generator" --> G["ModSpec / DSL / generator / audit / test upgrade"]
```

Free-Code Lab 只写 `workspace/free-code-lab-runs/<run-name>/` 下的实验副本，不修改原 workspace，也不修改本工具源码。汇总入口是：

```powershell
py -3.11 -m agent.cli agent lab-generate "<request>" --from-workspace <workspace> --run-name <name> --build --json
py -3.11 -m agent.cli harvest-report --run-name <name> --json
```

详细边界见 [capability-harvest-loop.md](../Agent与能力/capability-harvest-loop.md)。
