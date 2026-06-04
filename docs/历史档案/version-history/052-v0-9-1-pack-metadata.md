## V0.9.1 Pack Metadata

Goal: include `pack.mcmeta` as a first-class generated artifact.

Completed:

- Generated `src/main/resources/pack.mcmeta`.
- Added `pack.mcmeta` to `generation-summary.json`.
- Extended audit to check:
  - file existence
  - valid JSON
  - `pack` object
  - `pack.description`
  - integer `pack.pack_format`
- Preserved compatibility with older workspaces.

Value:

- Completed a small but important resource-pack/data-pack metadata requirement.
- Made audit cleaner and more complete before V1.0.
