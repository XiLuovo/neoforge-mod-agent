# RAG

RC1 的 RAG 是本地 NeoForge 知识检索层。它服务 planner、develop/repair tool loop、reviewer 和 benchmark evidence，不是外部联网知识同步器。

## 在主线中的位置

```text
user goal / observation
-> retrieve_rag
-> snippets / citations
-> LLM tool action or reviewer decision
-> trace / rag-context evidence
```

## 用在哪里

- planner：辅助把自然语言目标收敛为 `ModSpec`。
- develop：baseline 之后根据 audit/build observation 补充上下文。
- repair：根据失败原因检索 NeoForge 规则和常见修复方向。
- reviewer：判断 unsupported request 和 recommended checks。
- benchmark：统计 `rag_hit_rate`。

## Evidence

常见输出：

```text
.agent/rag-context.json
.agent/repair-rag-context.json
.agent/prompt-trace.json
.agent/tool-call-trace.json
```

## 边界

- RAG 不替代 compiler、audit 或 reviewer。
- RAG 知识需要维护。
- RAG 命中只能说明“使用了哪些本地知识”，不能证明 Minecraft runtime 行为正确。

## 讲解方式

> RAG 不是为了装饰 prompt，而是为了让每次 planner、repair 和 reviewer 的依据能落到具体 citation，并写进 evidence。

## RC2 Agentic RAG

RC2 upgrades RAG from passive context injection to an agentic repair policy. The agent now records why retrieval is required, what queries were used, which citations were selected, and whether a later patch used those citations.

The tool-calling agent now records a RAG decision whenever it sees one of these triggers:

- audit or build failure
- unsupported request
- NeoForge API, registry, metadata, recipe, resource path, worldgen, loot, or tag uncertainty
- reviewer evidence insufficiency
- sensitive patch target such as `META-INF/neoforge.mods.toml`, `pack.mcmeta`, `data/**`, `assets/**`, or registration-related Java/JSON

The existing tool action name remains `retrieve_rag`, but the action now accepts:

```json
{
  "reason": "pack.mcmeta audit failure",
  "query": "broken pack_format",
  "limit": 5,
  "max_hops": 2
}
```

The policy rewrites failure-oriented queries before retrieval. Examples:

- `pack.mcmeta audit failure` -> `NeoForge resource pack metadata pack.mcmeta pack_format rules`
- `missing neoforge.mods.toml` -> `NeoForge mod metadata neoforge.mods.toml required fields`
- `DeferredRegister error` -> `NeoForge DeferredRegister registry object registration rules`
- `recipe json audit failure` -> `Minecraft NeoForge recipe JSON data pack schema`

Retrieval is multi-hop by default. The first hop searches the rewritten query; the second hop uses the top hit category/capability/title to build a follow-up query. Queries and hits are de-duplicated.

New evidence artifact:

```text
<workspace>/.agent/rag-decision-trace.json
```

Each decision records:

- why RAG was required or skipped
- policy triggers
- rewritten and follow-up queries
- hop-level hits
- selected citation ids
- whether a later structured patch used those citations

`apply_structured_patch` can carry `citation_ids`; if the LLM omits them and the latest RAG decision has citations, the executor auto-attaches the latest citations. The reviewer then checks evidence sufficiency and can require another RAG-backed repair loop when a sensitive patch lacks citation or file evidence.

## RC2 Acceptance Notes

RC2 has two validation modes:

- Mock validation is deterministic and is used by unit tests / CI-style checks. It is the best way to prove the RAG policy changes repair behavior because `rag_off` cases intentionally refuse sensitive NeoForge patches without citations.
- Real-provider validation proves the same loop can run against an OpenAI-compatible provider, but the measured delta is model-dependent. A strong model may repair simple cases even when RAG is disabled.

Latest local real-provider acceptance evidence:

```text
workspace/benchmark-runs/rc2-real-ablation-accepted/.agent/agent-benchmark-report.json
workspace/benchmark-runs/rc2-real-ablation-accepted/.agent/agent-benchmark-report.md
workspace/benchmark-runs/rc2-real-ablation-accepted/.agent/agent-benchmark-report.html
```

Recorded metrics from that run:

```text
success_rate = 1.0
audit_success_rate = 1.0
repair_success_rate = 1.0
rag_on_success_rate = 1.0
rag_off_success_rate = 1.0
rag_citation_coverage_rate = 0.5833
```

Interpretation: the real provider repaired all paired cases in both RAG-on and RAG-off modes, so the real run demonstrates provider integration and trace generation rather than a positive RAG delta. The mock ablation remains the controlled evidence for RAG benefit.
