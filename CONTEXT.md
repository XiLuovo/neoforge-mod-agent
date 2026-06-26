# NeoForge Mod Agent

This context names the domain language for a controlled Minecraft NeoForge Mod coding agent. It exists to keep ModSpec-first planning, deterministic generation, repair, audit, and evidence discussions precise.

## Language

**Feature Kind**:
A ModSpec content type that represents one kind of NeoForge mod capability that can be generated, merged, audited, and evaluated.
_Avoid_: feature type, component, service

**LLM Output Normalization**:
The project discipline of turning model-produced planner or patch JSON into stable ModSpec-compatible data before deterministic generation, merge, audit, or evidence recording.
Successful public normalization entrypoints return an `LLMNormalizationResult` with `normalized_json` and `warnings`; this names the Python boundary without changing the ModSpec-compatible JSON shape.
_Avoid_: prompt cleanup, parser hack, free-code repair

**Planner Resolution**:
The settled successful planning outcome for a natural-language generate/develop request or modify patch request after planner mode selection, fallback policy, output normalization, and evidence context have been applied.
_Avoid_: raw planner tuple, provider response, prompt parse result

**Workspace Materialization**:
The project discipline of turning an accepted ModSpec into generated NeoForge workspace files and replayable `.agent` evidence.
_Avoid_: file dumping, generator wrapper, workspace patching

**Agent Evidence Writing**:
The project discipline of recording agent, planner, repair, reviewer, and patch processes as replayable `.agent` evidence for audit, review, benchmark, and showcase claims.
_Avoid_: report dumping, logging, generic telemetry
