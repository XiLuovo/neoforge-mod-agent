# Direct Code Lane

> 文档定位：这是 Direct Code Lane 机制真相源。结构化补丁接口、路径边界、artifact、audit/build gate 和 rollback 以本文为准。

Direct Code Lane upgrades the agent from a ModSpec-only path to a ModSpec-first hybrid path:

```text
Natural language
  -> ModSpec-first routing
  -> deterministic NeoForge generation
  -> optional structured Direct Code Patch
  -> audit + Gradle build
  -> repair analysis + rollback evidence
  -> replay
```

It is not an unbounded coding agent. The LLM may request source edits only as structured JSON, and the executor applies them only inside the generated mod workspace after review.

## Relationship To Free-Code Lab

Direct Code Lane is part of a production `agent generate` / `agent modify` run. It extends one generated workspace with a reviewed patch and accepts the run only after audit plus Gradle build pass.

Free-Code Lab is different: it copies an existing generated workspace into `workspace/free-code-lab-runs/<run-id>/workspace`, applies experimental structured patches there, and writes a harvest candidate. Lab runs are for discovering generate gaps; they do not change the original workspace and do not update this tool's generator code automatically.

Use this rule of thumb:

- Direct Code Lane: "this agent run needs a bounded source patch to finish."
- Free-Code Lab: "stable generate cannot express this yet; experiment first, then decide whether to harvest into the generator."

## Code Lanes

`agent generate` and `agent modify` support:

```text
--code-lane hybrid   # default: ModSpec first, Direct Code only when requested or needed
--code-lane modspec  # ModSpec only, no Direct Code writes
--code-lane direct   # generate/load the workspace baseline, then apply a Direct Code plan
```

Non-agent commands keep their existing behavior.

## Patch Format

The first version supports only:

- `write_file`: write a complete file.
- `replace_text`: perform exactly one literal search/replace in an existing file.

Each change must include:

```json
{
  "path": "src/main/java/com/generated/demo/directcode/Demo.java",
  "operation": "write_file",
  "content": "package com.generated.demo.directcode;\n\npublic final class Demo {\n}\n",
  "reason": "Add a compile-verifiable helper class.",
  "risk_level": "low"
}
```

`replace_text` uses `search` and `replace` instead of `content`. Zero matches or multiple matches fail the plan.

## Safety Boundaries

Allowed roots are:

```text
src/main/java
src/main/resources
build.gradle
gradle.properties
.agent
```

The reviewer rejects absolute paths, traversal segments, paths outside the workspace, `.git`, `gradle/wrapper`, build output folders, binary artifacts, unsupported operations, missing reasons, unsafe Java tokens, and Java package declarations that do not match their source path.

Gradle file edits are allowed by policy but reported as higher scrutiny and must pass the build gate.

## Evidence

Every Direct Code run writes:

```text
.agent/direct-code-plan.json
.agent/direct-code-plan.md
.agent/direct-code-review.json
.agent/direct-code-diff.md
.agent/direct-code-report.json
.agent/direct-code-rollback-report.json
.agent/direct-code-snapshots/
```

`agent-run.json` and replay evidence include `direct_code_reviewer` and `direct_code_agent` roles when the lane is used.

## Gates And Rollback

Direct Code Lane forces audit and Gradle build, even if the caller passes `--no-build`. A Direct Code run is accepted only when:

- the structured patch review passes;
- the patch applies cleanly;
- workspace audit passes;
- Gradle build passes.

If review, apply, audit, or build fails, the rollback report marks rollback as `recommended` and lists changed files plus snapshots that can be restored.

## Current Limitations

- The lane supports only `write_file` and exact single-match `replace_text`; it does not support free-form diffs, AST patches, file moves, deletes, or fuzzy multi-hunk edits.
- Apply is not a full transaction. Snapshots are written before changes, and rollback is reported, but failed plans are not automatically restored yet.
- The reviewer uses path policy, token checks, Java package checks, Gradle warnings, audit, and build gates. It is not a complete Java static analyzer or OS-level sandbox.
- Failed Direct Code runs do not trigger an automatic second LLM repair patch in this version.
- Build is required for acceptance, so Direct Code runs are slower and more environment-sensitive than ModSpec-only runs.

See [project-limitations.md](project-limitations.md) for the broader project gap list.
For the experimental learning loop around generate gaps, see [capability-harvest-loop.md](capability-harvest-loop.md).
