---
status: accepted
---

# Adopt Feature Kind Catalog Without Changing ModSpec Shape

The project has repeated Feature Kind knowledge across ModSpec parsing, serialization, merge preview, modify merge, audit, and eval. We will introduce a Feature Kind Catalog as the source of truth for Feature Kind metadata, while preserving the current ModSpec dataclass fields and JSON shape so existing examples, evidence, tests, and showcase flows remain stable.

## Considered Options

- Keep the repeated Feature Kind lists in each module.
- Replace the current ModSpec shape with a generic `features_by_kind` structure.
- Introduce a dynamic plugin registry for Feature Kinds.
- Add a static Feature Kind Catalog that records metadata only.

## Decision

Use a static `feature_catalog.py` module for Feature Kind metadata. The first phase keeps `ModSpec.items`, `ModSpec.ores`, `ModSpec.recipes`, and the existing `.agent/modspec.json` shape intact; the catalog provides ordered metadata such as kind, collection name, parser key, and merge policy. The catalog does not run planner normalization, generation, audit, eval, or workspace file operations.

## Consequences

Adding a new Feature Kind should start by registering its metadata in the catalog, then wiring specific generator, audit, and eval behavior where needed. This improves locality without turning the catalog into a general plugin system or changing the project's ModSpec-first evidence format.

