# V6.1 Controlled Java Extension

> 文档定位：这是受控 Java extension 专项材料，不是主学习入口。它与 Direct Code Lane 的区别详见 [direct-code-lane.md](../Agent与能力/direct-code-lane.md)。

V6.1 adds a narrow, auditable Java extension path with an acceptance loop. It is not a free-form Java patch generator. The project still follows the same boundary:

```text
natural language / LLM -> ModSpec -> validator -> deterministic generator -> audit / build / repair
```

The only new Java surface is a managed additive class under:

```text
src/main/java/<package>/extension/<ClassName>.java
```

## Compared With Direct Code Lane

Controlled Java extension remains the safest Java expansion point: the LLM declares a `java_extension` feature in `ModSpec`, and the deterministic generator renders one additive managed class under the `extension` package.

Direct Code Lane is broader but still bounded. It is used only by `agent generate` / `agent modify` through `--code-lane`, accepts structured JSON `write_file` or `replace_text` changes inside the generated workspace, snapshots affected files, records review/diff/report/rollback artifacts, and requires audit plus Gradle build before success.

Use controlled Java extension when the behavior fits the ModSpec-managed helper shape. Use Direct Code Lane when the requested source change is outside ModSpec expression but can still be represented as a small audited workspace patch.

Free-Code Lab is a third, experimental path. It copies an existing generated workspace under `workspace/free-code-lab-runs/<run-id>/workspace`, applies structured experimental patches there, and writes a harvest candidate. Use it when a request is beyond current stable generate capability and you want evidence before deciding whether to add a new `ModSpec` field, DSL rule, generator template, audit rule, or test.

In short:

- Controlled Java Extension: safest additive Java surface, fully driven by `ModSpec`.
- Direct Code Lane: bounded production workspace patch for `agent generate` / `agent modify`.
- Free-Code Lab: isolated experiment for generate gaps, later harvested into stable generator capability.

## What It Can Generate

A `java_extension` feature may declare:

- `class_name`: PascalCase class name, for example `SafeInfoExtension`
- `purpose`: short reason this helper exists
- `explanation`: human-readable explanation for audit and review
- `allowed_imports`: optional imports from the sandbox allowlist
- `methods`: static String-returning helper methods

Example:

```json
{
  "type": "java_extension",
  "id": "safe_info_extension",
  "display_name_en_us": "Safe Info Extension",
  "class_name": "SafeInfoExtension",
  "purpose": "Expose a tiny compile-time helper without editing existing generated sources.",
  "explanation": "The deterministic generator renders this as an additive managed class under the extension package.",
  "allowed_imports": [
    "net.minecraft.network.chat.Component"
  ],
  "methods": [
    {
      "name": "describe",
      "return_type": "String",
      "return_value": "Controlled Java extension generated from ModSpec.",
      "explanation": "Returns a short audit-friendly description."
    }
  ]
}
```

The generated class is final, has a private constructor, and exposes only static methods declared by the spec.

## Sandbox Rules

The generator rejects or audits against unsafe surface area:

- no raw `package` or `import` text from model output
- no edits to existing generated Java classes
- no Gradle edits
- no file, network, process, reflection, thread, classloader, native, or unsafe APIs
- return types are currently limited to `String`
- imports are limited to:
  - `net.minecraft.core.BlockPos`
  - `net.minecraft.network.chat.Component`
  - `net.minecraft.resources.ResourceLocation`

This keeps V6 useful as a controlled expansion hook while preserving the reliable generator boundary.

## Reports And Gates

Generation writes:

```text
.agent/java-extension-report.json
.agent/java-extension-report.md
.agent/java-extension-diff.md
.agent/java-extension-rollback-report.json
.agent/java-extension-rollback-report.md
```

The report records the sandbox mode, generated classes, methods, allowed imports, build gate result, diff artifact, and rollback guidance.

The class diff is a review artifact rendered as a new-file diff. It proves V6.1 added only managed files under the `extension` package.

The rollback report is always written. It stays in `standby` when build is skipped, becomes `not_needed` when the build gate passes, and becomes `recommended` when the build gate fails.

Audit checks:

- the class exists under the `extension` package
- the package declaration matches `<spec.package_name>.extension`
- the class is `public final`
- declared static methods exist
- the report contains the generated class
- forbidden tokens are absent

For formal V6.1 acceptance, run Gradle build as the final gate. `--audit --no-build` proves structure and sandbox constraints, but not Java compiler compatibility.

Build-gated command:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m agent.cli generate-from-spec .\examples\controlled_java_extension.json --workspace-name v61-java-extension-build --overwrite --audit --build --json
```

## Smoke Command

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
py -3.11 -m agent.cli generate-from-spec .\examples\controlled_java_extension.json --workspace-name v61-java-extension-smoke --overwrite --audit --no-build --json
```

Expected generated files:

```text
workspace/v61-java-extension-smoke/src/main/java/com/generated/extension_mod/extension/SafeInfoExtension.java
workspace/v61-java-extension-smoke/.agent/java-extension-report.json
workspace/v61-java-extension-smoke/.agent/java-extension-report.md
workspace/v61-java-extension-smoke/.agent/java-extension-diff.md
workspace/v61-java-extension-smoke/.agent/java-extension-rollback-report.json
workspace/v61-java-extension-smoke/.agent/java-extension-rollback-report.md
```

## Sandbox Violation Sample

An intentionally invalid sample lives outside the normal example glob:

```text
examples/invalid/controlled_java_extension_violation.json
```

It asks for `java.io.File` and a `Runtime.getRuntime()` return value. The validator must reject it before generation.

## Rollback

Remove the `java_extension` entry from `ModSpec` and regenerate, or rerun generation from a previous `.agent/modspec.json` snapshot. Because V6 is additive and managed, rollback does not require modifying user-authored Java files.

---

## V6.2 Controlled Patch Agent

V6.2 is the next layer up. It keeps the same boundary, but the LLM now emits a patch plan for modify mode instead of trying to edit the repo directly.

```text
natural language / LLM -> patch plan -> ModSpec delta -> managed-file regeneration -> audit / build / rollback
```

The key rule stays the same: only managed files are touched. That includes generated Java, resources, and `.agent` artifacts. User-authored files remain outside the overwrite scope.

Generation writes:

```text
.agent/patch-agent-plan.json
.agent/patch-agent-plan.md
.agent/patch-agent-report.json
.agent/patch-agent-report.md
.agent/patch-agent-rollback-report.json
.agent/patch-agent-rollback-report.md
```

The plan records the requested change, managed-file policy, before/after ModSpec snapshots, add/update/skip counts, and rollback steps. The report records the final audit/build/repair outcome plus the managed files that were regenerated. The rollback report marks rollback as recommended when audit or build fails.

This is closer to a MiniCode / pi-mono style patch flow, but the sandbox boundary is still explicit: the LLM never gets direct write access to the whole repo.
