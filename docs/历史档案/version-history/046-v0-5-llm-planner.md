## V0.5 LLM Planner

Goal: add LLM support without allowing the LLM to directly write project files.

Completed:

- Added optional `llm` planner mode while keeping `rules` as the default.
- Added `auto` planner mode.
- Added `MockLLMClient` for offline deterministic tests.
- Added OpenAI-compatible client support through environment variables.
- Added LLM planner artifacts:
  - planner input
  - raw LLM JSON
  - normalized LLM JSON
  - planner warnings
- Normalized and validated LLM output into `ModSpec`.

Value:

- Introduced LLM capability while preserving deterministic generation.
- Avoided the common failure mode of letting the model directly emit Java or Gradle code.
