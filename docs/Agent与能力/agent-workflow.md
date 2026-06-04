# Agent Runtime / Workflow

> 文档定位：这是 Agent workflow 真相源。planner、reviewer、executor、auditor、repair、trace 的阶段和证据文件以本文为准。

## V8.5 Capability Harvest Loop

V8.5 adds an experimental learning loop around the stable agent workflow:

```text
generate gap
  -> Free-Code Lab copied workspace
  -> structured experimental code plan
  -> safety review + apply
  -> audit / build / manual runtime checklist
  -> harvest candidate
  -> later ModSpec / DSL / generator / audit / repair / test upgrade
```

`agent lab-generate` is deliberately outside the production `agent generate` acceptance path. It copies an existing generated workspace into `workspace/free-code-lab-runs/<run-id>/workspace`, applies structured experimental patches there, and writes evidence under that run's `.agent/` directory:

```text
.agent/free-code-plan.json
.agent/free-code-plan.md
.agent/free-code-diff.md
.agent/free-code-report.json
.agent/manual-runtime-checklist.md
.agent/harvest-candidate.json
```

The matching `harvest-report` command aggregates lab candidates into `workspace/harvest-runs/<run-id>/.agent/harvest-report.json` and `.md`. It does not merge code back into the generator; harvesting still requires a deliberate implementation step with examples, unit tests, audit tests, and generate smoke tests.

This is the main difference between V8.4 and V8.5:

- Direct Code Lane extends a single production agent run with reviewed workspace patches.
- Free-Code Lab is an isolated experiment area for generate gaps.
- Capability Harvest Loop is the process for turning successful lab patterns into stable deterministic generator capability.

## V8.4 ModSpec-First + Direct Code Lane

V8.4 upgrades the agent route from ModSpec-only to a ModSpec-first hybrid contract:

```text
Natural language
  -> ModSpec-first routing
  -> deterministic NeoForge generation
  -> optional structured Direct Code Patch
  -> audit / build / repair / replay
```

`agent generate` and `agent modify` now accept `--code-lane {hybrid,modspec,direct}`. The default `hybrid` lane still plans a `ModSpec` first, then enters Direct Code Lane only when the planner marks `requires_direct_code=true` or provides a `direct_code_plan`. `modspec` preserves the previous ModSpec-only behavior. `direct` creates or loads the generated workspace baseline, then applies a reviewed structured patch.

Direct Code Lane is intentionally narrow: LLM output is JSON with `write_file` or `replace_text` changes, never a free-form diff. The runtime records `direct_code_reviewer` and `direct_code_agent` evidence, writes rollback snapshots under `.agent/direct-code-snapshots/`, and accepts the run only after audit plus Gradle build pass.

## V8.3 DomainSpec Plugin Layer

V8.3 adds a `DomainSpec` registry on top of the V8.1 runtime extraction. `ModSpec` is now the stable `minecraft.neoforge` domain spec, while `spring.api` and `unity.component` are registered as planned extension points:

```powershell
py -3.11 -m agent.cli domains --json
```

## V8.1 Runtime Extraction

V8.1 splits the agent flow into a small domain-neutral runtime plus a NeoForge domain plugin:

```text
AgentRuntime
  -> planner stage
  -> reviewer stage
  -> executor stage
  -> auditor stage
  -> repair stage
  -> AgentTraceWriter

NeoForgeRuntimePlugin
  -> domain_spec_plugin: minecraft.neoforge / ModSpec
  -> natural language / LLM / rules -> intent contract
  -> deterministic NeoForge generation
  -> optional Direct Code Lane
  -> workspace audit
  -> repair-loop from .agent/modspec.json
  -> optional Free-Code Lab / harvest reporting outside production generate
```

`AgentRuntime` owns the workflow skeleton and trace persistence. `NeoForgeRuntimePlugin` owns the domain-specific behavior: planning a `ModSpec`, generating Java/JSON/PNG/resources, auditing NeoForge references, and running the safe repair loop. The plugin now also exposes `domain_spec_plugin`, so future domains can provide their own spec loader, schema, validator, generator, auditor, and repair rules.

The visible CLI behavior is unchanged:

```powershell
py -3.11 -m agent.cli agent generate "Create a ruby mod with ruby." --planner llm --llm-provider mock --workspace-name runtime-demo --overwrite --no-build --json
```

The resulting `agent-run.json` now includes a runtime payload:

```json
{
  "payload": {
    "runtime": {
      "domain": "neoforge",
      "domain_spec": {
        "domain_id": "minecraft.neoforge",
        "spec_type": "ModSpec",
        "status": "stable"
      },
      "stages": ["planner", "reviewer", "executor", "auditor", "repair"]
    }
  }
}
```

This is the first step toward making NeoForge one domain plugin instead of the whole agent runtime. Future domains can implement the same stage contract without reusing Minecraft-specific generators.

# V2.0 Agent Workflow

## V3.7 Repair Agent Execution

V3.7 upgrades `repair_agent` from analysis-only to safe execution. If `auditor_agent` or the build step reports failure and repair is enabled, `repair_agent` automatically runs the deterministic repair loop once.

The action is intentionally narrow:

```text
read .agent/modspec.json
  -> regenerate managed files
  -> rerun requested audit/build checks
  -> attach repair-loop result to agent-run.json
```

If the repair loop succeeds, the final agent run can recover to `success=true`. If it fails, the run keeps the root causes, repair plan, and repair-loop attempts for follow-up.

V2.0 upgrades the agent workflow from a lightweight step list into a traceable multi-role workflow.

## Goal

The project keeps the core boundary:

```text
natural language / LLM
  -> ModSpec / Behavior DSL / patch plan / repair plan / direct-code plan
  -> deterministic Java/JSON generation / controlled extension / reviewed workspace patch
  -> audit/build/repair/replay
  -> optional Free-Code Lab harvest loop for generate gaps
```

LLM output remains constrained to verifiable intermediate representations such as `ModSpec`, Behavior DSL, controlled Java extension specs, patch plans, repair plans, direct-code plans, and lab plans. The agent workflow records how each role made its decision, so the result is easier to debug, evaluate, and turn into stable generator upgrades.

## Roles

- `planner_agent`: converts the user request into an intent contract: ModSpec, Behavior DSL, controlled extension spec, patch plan, direct-code plan, repair plan, or modification patch.
- `reviewer_agent`: validates the ModSpec before generation is trusted, and reviews Direct Code patch boundaries when that lane is used.
- `executor`: runs deterministic generation, managed-file regeneration, or reviewed patch application over generated workspace files only.
- `auditor_agent`: checks generated workspace structure against ModSpec and generation-summary.
- `repair_agent`: classifies failed build or audit results and writes repair context when needed.
- `context_loader`: used by `agent modify` to load the existing `.agent/modspec.json` truth source.
- `free_code_lab`: copies a generated workspace into an isolated lab run, applies experimental structured patches, and writes harvest candidate evidence.

## Artifacts

Each successful workspace agent run writes:

```text
.agent/agent-run.json
.agent/agent-run.md
.agent/agent-decisions.md
.agent/prompt-trace.json
.agent/agent-run-replay.html
.agent/direct-code-*.json
.agent/free-code-*.json
.agent/harvest-candidate.json
```

`agent-decisions.md` is the human-readable explanation of role decisions and rationales.

`prompt-trace.json` records planner inputs, system prompt, raw LLM JSON when available, normalized ModSpec output, warnings, and errors. This is intended for debugging and replay, not for committing private prompts or secrets.

`replay` can now render `.agent/agent-run.json` into a static `agent-run-replay.html` trace viewer with role timeline filters, decision details, LLM provider telemetry, RAG/repair evidence, and artifact links.

## Commands

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli agent generate "Create a ruby mod with a ruby charm item." --planner llm --llm-provider mock --workspace-name v20-agent-trace --overwrite --no-build --json
```

```powershell
py -3.11 -m agent.cli agent modify workspace\v20-agent-trace "Add ruby ore that generates underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk." --planner llm --llm-provider mock --no-build --json
```

## 中文说明

V2.0 的重点不是让 LLM 直接写 Java，而是让 LLM 和多个确定性角色协作完成开发闭环：

```text
规划 -> 审查 -> 生成 -> 审计 -> 修复分析
```

这样做有三个好处：

- LLM 负责生成 `ModSpec`、Behavior DSL、受控扩展意图或 repair plan，风险被限制在可校验中间表示里。
- 每个角色的决策都会写入 `.agent/agent-decisions.md`，方便复盘和面试讲解。
- Planner 的输入输出会写入 `.agent/prompt-trace.json`，方便定位 LLM 输出、normalize 和 validator 之间的问题。
- 当生成能力不足时，Free-Code Lab 只在实验副本里探索；成功样本必须再沉淀成 `ModSpec` / DSL / generator / audit / test，不能直接复制进稳定路径。

这让项目从“能生成 Mod 的工具”更像一个“可追踪、可评测、可修复的 LLM 多角色开发 Agent”。
