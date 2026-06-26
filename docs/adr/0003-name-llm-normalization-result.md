---
status: accepted
---

# Name LLM Normalization Result

LLM planner and patch outputs are normalized before they become `ModSpec` data, but the public normalization entrypoints returned raw tuples of normalized JSON and warnings. That made the boundary easy to confuse with provider responses, parser repair, or validator results.

## Considered Options

- Keep returning raw tuples from normalization entrypoints.
- Move schema validation and retry policy into the normalizer.
- Introduce a named normalization result while leaving planner policy in place.

## Decision

Introduce `LLMNormalizationResult` for successful public normalization entrypoints. It names the existing fields as `normalized_json` and `warnings`.

The normalizer still only turns model-produced planner or patch JSON into ModSpec-compatible data. Planner retries, provider fallback, schema validation, evidence writing, and audit/build gates remain at their existing boundaries.

## Consequences

Planner callers can distinguish normalized ModSpec-compatible JSON from raw provider JSON and validator outcomes without changing trace payload shape, ModSpec JSON shape, CLI behavior, or generated workspace materialization.

## Follow-up

The decomposed planner later stopped importing individual private normalizer helpers directly. It now depends on `DECOMPOSED_PLANNER_NORMALIZATION`, a named facade for the small set of normalization rules it needs while composing and hardening decomposed feature JSON. The underlying compatibility rules remain owned by the LLM output normalizer.
