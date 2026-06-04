## V0.2 Basic Content Generation

Goal: expand from a single demo item into structured content generation.

Completed:

- Introduced `ModSpec` as the structured source of truth.
- Added rule-based planning from natural language into `ModSpec`.
- Added deterministic generation for basic assets and project metadata.
- Started separating planner, model, generator, and validator responsibilities.

Value:

- Moved the system from a demo script toward an extensible generator architecture.
- Established the core principle: natural language becomes `ModSpec`, not arbitrary generated code.
