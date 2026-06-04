## V0.7 Simple Behavior Items

Goal: support controlled gameplay behavior without allowing arbitrary Java generation.

Completed:

- Added behavior declarations to `ModSpec`.
- Supported item behavior:
  - `right_click_heal`
  - `right_click_effect`
- Supported food effects through `food.effects`.
- Supported sword hit behavior through `sword.on_hit.ignite`.
- Generated custom Java item classes when behavior requires code.
- Generated custom sword item classes for on-hit ignite behavior.
- Extended rules planner and mock LLM behavior prompts.
- Extended validator to check behavior types, ranges, effect ids, cooldowns, probabilities, and allowed feature attachment.
- Verified behavior content through build and manual in-game tests.

Value:

- Moved from static content generation into behavior-driven generation.
- Preserved the project architecture: behavior is declared in `ModSpec`, Java is still generated deterministically.
