---
status: accepted
---

# Name Planner Resolution

Planner entrypoints historically returned tuples of `ModSpec`, planner artifacts, warnings, and the effective planner mode. Those tuples were compact, but their meaning was easy to drift as planner modes, fallback policy, modify patches, and trace evidence grew.

## Considered Options

- Keep returning the raw tuple everywhere.
- Replace planner failures with a success/error result object.
- Move provider health and fallback policy into a new resolver module immediately.
- Introduce a named success result for planner entrypoints while leaving policy in place.

## Decision

Introduce a `PlannerResolution` value for successful planner results. It names the existing output fields without changing planner behavior: `spec`, `artifacts`, `warnings`, and `planner_mode_used`.

Planner failures continue to use the existing exception path. Provider health checks, `require_llm`, and fallback policy remain in their current orchestrator, CLI, and modifier logic; this decision names successful outcomes without moving those policies.

## Consequences

Runtime planning callers get a clearer interface without changing ModSpec-first generation, fallback semantics, trace payload shape, or audit/build gates. A later phase can move planner decision logic into a dedicated resolver once the named result has replaced the tuple at the runtime seam.

## Follow-up

After the runtime seam adopted `PlannerResolution`, the CLI prompt resolver also adopted the same named success result. This keeps command-line plan/validate/generate paths aligned with runtime planning while still leaving provider health checks, fallback policy, and modify planning in their existing locations.

Modify planning later adopted `PlannerResolution` for patch ModSpec outcomes as well. The value's `spec` field may therefore hold either a full ModSpec or a patch ModSpec, depending on the planning entrypoint; failure handling and fallback policy still remain at their existing call sites.
