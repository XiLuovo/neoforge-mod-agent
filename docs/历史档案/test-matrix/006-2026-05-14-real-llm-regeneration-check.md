## 2026-05-14 Real LLM Regeneration Check

本轮目标是用修复后的生成器重新生成三个固定 case，并且不手工 patch 生成 workspace。验收时 `llm->rules` 不计为 real LLM 成功。

| Case | Workspace | LLM result | ModSpec / audit | Build | Result |
| --- | --- | --- | --- | --- | --- |
| Ruby Basic | `workspace/real-llm-regen2-ruby-basic-20260514` | `planner_mode=llm` | audit 304 checks, 0 errors, 0 warnings | pass | 通过 |
| Machine | `workspace/real-llm-regen2-machine-20260514` | `planner_mode=llm` | audit 160 checks, 0 errors, 0 warnings | pass | 通过 |
| Progression strict | `workspace=null` via `real-llm-regen4-progression-strict-20260514` request | `planner_mode=llm`, provider timed out | not reached | not reached | 未通过 real LLM 标准 |
| Progression fallback hardening | `workspace/real-llm-regen3-progression-after-hardening-20260514` | `planner_mode=llm->rules` | audit 287 checks, 0 errors, 0 warnings | pass | 只证明 fallback 产物可 build，不计入 real LLM 成功 |

Source-level follow-up included in this round:

- `OPENAI_MODEL=gpt-5.5;gpt-image-2` now normalizes to `gpt-5.5` for text planning and records a warning.
- `agent generate --require-llm` fails instead of falling back when the real LLM request times out or errors.
- Entity codegen was updated for MC 26.1 and verified with `workspace/entity-regression-build-20260514` (`audit` 55 checks, `build` pass).
