# Repair RAG Advisor

> 文档定位：这是 Repair RAG 专项材料，不是主学习入口。需要理解修复阶段如何检索知识和解释错误时再读。

V4.2 adds a deterministic Repair RAG Advisor.

Its job is simple: when `agent generate` or `agent modify` sees an audit/build failure, the repair step turns the failure context into a local knowledge-base query and attaches the retrieved evidence to the repair plan.

## Failure Lab Coverage

V4.4 adds `failure-lab`, which deliberately creates broken generated workspaces and runs audit, repair RAG, and repair-loop for each case. This gives repair RAG predictable failure inputs such as missing textures, missing models, missing worldgen JSON, missing behavior Java classes, and broken recipe JSON references.

```powershell
py -3.11 -m agent.cli failure-lab --run-name v44-failure-lab --json
```

The resulting per-case `.agent/repair-rag-context.json` files are meant to show why a repair action was selected, not to directly modify generated Java, JSON, PNG, or Gradle files.

## What It Reads

- repair root causes
- repair action ids and summaries
- audit errors and audit report paths
- build issues and build artifact paths
- generated artifact hints such as missing texture, worldgen, recipe, behavior, or model files

## What It Writes

```text
<workspace>/.agent/repair-rag-context.json
<workspace>/.agent/repair-rag-context.md
<workspace>/.agent/agent-repair-plan.json
<workspace>/.agent/agent-repair-plan.md
```

The `agent-repair-plan.md` report includes a `Repair RAG Context` section with the query, hit count, report paths, and relevant knowledge ids.

## Visualization

V4.3 surfaces the same evidence in three places:

- Static Dashboard: `Self-Healing Repair` cards show the RAG query, hit ids, and a deterministic root cause -> repair action -> knowledge mapping.
- Agent Replay: `replay` includes a `repair_rag` event, plus `repair_rag_events_count` and `repair_rag_hits_count` metrics.
- Web Demo: the `Self-Healing` tab shows repair RAG query, categories, capabilities, hits, and mapping entries.

## Safety Boundary

- It does not call a real LLM.
- It does not write Java, JSON, PNG, or Gradle files.
- It does not apply patches.
- It does not change repair success or failure by itself.
- It only provides explanatory repair context.

The safe repair loop still regenerates managed files from `.agent/modspec.json`.

## Example Failure Mapping

- Missing texture or invalid `texture-manifest.json` should retrieve `assets.procedural_textures`, `audit.texture_checks`, or `assets.models_textures`.
- Missing worldgen JSON should retrieve `worldgen.overworld_ore`.
- Missing behavior item class should retrieve `behavior.right_click_item`.
- Missing sword ignite class should retrieve `behavior.sword_ignite`.

## Test

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m unittest tests.test_repair_rag tests.test_agent_eval -v
```
