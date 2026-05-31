# NeoForge Knowledge Base / RAG

> 文档定位：这是 RAG 知识库专项材料，不是主学习入口。需要理解本地 NeoForge 知识如何服务 planner 和 repair 时再读。

V2.4 adds a local, deterministic NeoForge knowledge base and retrieval layer.

This is not a live web crawler and not a vector database yet. It is a curated bundled knowledge base that captures the project rules we already rely on:

- ModSpec is the source of truth.
- Historical boundary: in the original V2.4 RAG path, LLMs produced ModSpec only.
- Current boundary: the planner may produce ModSpec, DSL intent, controlled extension intent, repair plan, or Direct Code Plan; Direct Code Lane still accepts only structured workspace patches with review, snapshot, audit/build gates, and rollback evidence.
- Python generators produce Java, JSON, resources, and PNG assets.
- Audit/build/repair validate generated output.
- Supported feature families are item, block, machine, entity, dimension, biome, world_feature, structure, loot_pool, java_extension, ore, food, sword, recipe, behavior, worldgen, procedural textures, template-based machine GUI / BlockEntity generation, template-based Entity / Mob DSL generation, V5.4 World / Structure DSL generation, and V6.1 controlled Java extension generation with build/diff/rollback evidence.
- Unsupported systems such as arbitrary custom GUI logic, complex entity animation/model systems, advanced entity AI, authored NBT structures, custom terrain noise engines, complex multi-dimension gameplay systems, existing-source Java patches, Gradle patches, and free-form Java must not be invented as generated code.

## CLI

Query the knowledge base:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli knowledge query "红宝石矿石自然生成在主世界地下" --run-name v24-rag-worldgen --json
```

Reports are written to:

```text
workspace/knowledge-runs/<run-id>/.agent/rag-query.json
workspace/knowledge-runs/<run-id>/.agent/rag-query.md
```

The JSON report includes:

```json
{
  "success": true,
  "query": "...",
  "hits": [],
  "hits_count": 0,
  "context": "...",
  "report_json_path": "...",
  "report_md_path": "..."
}
```

## RAG Eval

`rag-eval` turns the bundled RAG layer into a measurable offline benchmark instead of only a prompt-context feature.

Run the default fixed case set:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
py -3.11 -m agent.cli rag-eval --run-name local-rag-eval --json
```

The default cases live in:

```text
examples/rag_eval_cases.json
```

Reports are written to:

```text
workspace/rag-eval-runs/<run-id>/.agent/rag-eval-report.json
workspace/rag-eval-runs/<run-id>/.agent/rag-eval-report.md
```

The report compares raw keyword retrieval with the existing query expansion path and records:

- `raw_recall_at_1`
- `raw_recall_at_k`
- `raw_mrr`
- `expanded_recall_at_1`
- `expanded_recall_at_k`
- `expanded_mrr`
- `expanded_expected_category_hit_rate`
- `expanded_expected_capability_hit_rate`
- `query_rewrite_recall_at_k_delta`
- `failed_cases`

This gives the project a direct answer to interview questions such as "How do you quantify RAG?", "Does query rewrite help?", and "How do you find retrieval failures?".

## Planner Integration

When `--planner llm` is used, the planner now retrieves relevant snippets from the bundled knowledge base before calling the LLM provider.

The retrieved context is appended to the LLM system prompt as:

```text
NeoForge RAG Context:
Use these bundled knowledge snippets as constraints...
```

Generated workspaces include:

```text
.agent/rag-context.json
.agent/rag-context.md
```

Agent workflow traces also include:

```text
rag_query
rag_hits
```

This makes the LLM planning step easier to explain in a portfolio: the model is not just prompted blindly; it receives retrieved project-specific NeoForge constraints and leaves a reproducible retrieval trace.

## Repair Integration

V4.2 also connects the same bundled knowledge base to the repair workflow.

When `agent generate` or `agent modify` detects audit/build failure, `RepairRAGAdvisor` builds a deterministic query from root causes, audit errors, build issues, and repair actions. The retrieved context is written to:

```text
<workspace>/.agent/repair-rag-context.json
<workspace>/.agent/repair-rag-context.md
```

The repair plan also links this context from:

```text
<workspace>/.agent/agent-repair-plan.md
```

This is advisory only: RAG does not call a real LLM, does not patch files, and does not replace the safe managed-file repair loop.

## Current Knowledge Categories

- `architecture`: ModSpec boundary and deterministic generator contract.
- `java`: NeoForge registration, generated Java patterns, and `java.controlled_extension` sandbox guidance.
- `assets`: model, texture, and procedural texture rules.
- `behavior`: right click item behavior, food effects, sword ignite.
- `data`: recipe, loot table, and tag paths.
- `worldgen`: overworld ore configured/placed/biome modifier JSON plus V5.4 dimension, biome, world_feature, structure, structure_set, template_pool, and loot_pool guidance.
- `resources`: `pack.mcmeta`.
- `audit`: texture and workspace checks.
- `limits`: unsupported systems.

## Example LLM Flow

```powershell
py -3.11 -m agent.cli generate "Create a ruby mod with ruby ore worldgen in the overworld." --planner llm --llm-provider mock --workspace-name v24-rag-llm-worldgen --overwrite --no-build --audit --json
```

Expected artifacts:

```text
workspace/v24-rag-llm-worldgen/.agent/planner-system-prompt.txt
workspace/v24-rag-llm-worldgen/.agent/rag-context.json
workspace/v24-rag-llm-worldgen/.agent/rag-context.md
workspace/v24-rag-llm-worldgen/.agent/llm-plan-normalized.json
```

## Limits

- The knowledge base is curated and local.
- It is not guaranteed to match the latest upstream NeoForge documentation.
- Retrieval is deterministic keyword scoring, not semantic embeddings.
- RAG context is guidance, not permission to generate unsupported feature types.
- `java.controlled_extension` allows only structured, additive `java_extension` specs; it is not permission for raw Java source or arbitrary patches.
- No external network access is required.
