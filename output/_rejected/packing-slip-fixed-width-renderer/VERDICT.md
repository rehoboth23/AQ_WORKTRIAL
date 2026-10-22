# Verdict: rejected

- Topic: [spec] a packing-slip generator that renders fixed-width slips from an orders CSV with strict rules for grouping, quantities, weights, address blocks, page breaks and totals
- Task: packing-slip-fixed-width-renderer
- Why: too_easy (stopped early: 3 passes, no failure yet; EARLY_STOP_PASSES=3)
- Generator: `z-ai/glm-5.1`; eval: `openrouter/z-ai/glm-5.3-flash`, reasoning_effort=high, 5 runs, learnable = 1-3 passes

## Generation

- spec gate (attempt 0): pass
- critic: {"too_easy_because": ["R5 has mathematically incorrect test values: 0.1225 does not round to 0.124 under any method (round-half-up gives 0.123, banker's gives 0.122). An agent implementing round-half-up correctly would produce 0.123 and fail a test expecting 0.124. This is unfair.", "R1 and R8 are ambiguous about whether '72 characters' means Unicode codepoints or visual columns. For lines with CJ
- instruction_review: {"verdict": "clean", "leaks": []}
- instruction_review: {"verdict": "leaks", "leaks": ["R12 error messages not specified precisely \u2192 test requires exact strings `ERROR: invalid CSV` and `ERROR: no orders`", "R15 invalid date placeholder not specified precisely \u2192 test requires exact string `INVALID DATE`"]}
- instruction_review: {"verdict": "leaks", "leaks": ["R15 invalid-date placeholder text not explicitly stated -> R15", "R12 error reason phrases not specified -> R12"]}
- round 0: difficulty gate: instruction.md names shipped source/config files (/app/orders.csv); which points the agent at the fault; describe the symptom and goal instead and let the agent find the location; instruction.md pastes 3 expected values from the tests (e.g. ['ERROR: invalid CSV', 'ERROR: no orders', 'INVALID DATE']) | checks: not run
- round 1: difficulty gate: instruction.md pastes 3 expected values from the tests (e.g. ['ERROR: invalid CSV', 'ERROR: no orders', 'INVALID DATE']); state the rule that produces them instead | checks: not run
- round 2: difficulty gate: pass | checks: validator=pass, oracle=FAIL (reward 0.0)
- round 3: difficulty gate: pass | checks: validator=pass, oracle=pass (reward 1.0), nop=pass (reward 0.0)
- result: ok

## Band eval: 3/3 passed (2 invalid re-run) -> too_easy

| trial | outcome | steps | cost | failed tests | triage |
|---|---|---|---|---|---|
| packing-slip-fixed-width-rendere__9mi3pPk | invalid (CancelledError) | 47 | 0.16119793600000001 | - | - |
| packing-slip-fixed-width-rendere__BnCSyqA | invalid (CancelledError) | 39 | 0.127648575 | - | - |
| packing-slip-fixed-width-rendere__NHPYq9k | pass | 25 | 0.06425098299999998 | - | - |
| packing-slip-fixed-width-rendere__gZGXgdu | pass | 21 | 0.053259413 | - | - |
| packing-slip-fixed-width-rendere__oBqbSME | pass | 27 | 0.082447171 | - | - |

## Lesson

The task's 19 rules achieved full mutation kill and good separation (2 invalid, 3 pass), but the rules are heavily skewed toward formatting/column-width specifications (R1, R2, R7, R8, R9, R10, R11, R16), making success depend on tedious visual-column arithmetic rather than algorithmic insight. The unicode-width rule (R8) pervasively interacting with all padding rules was the strongest hidden complexity, while pagination (R6) and overflow (R14) added structural difficulty. Next design should keep the multi-rule combinatorial approach but rebalance toward more diverse themes—fewer pure formatting rules, more arithmetic/conditional/edge-input rules—and introduce sharper hidden inputs that can't be caught by eyeballing column positions.

## Evidence

- generation log: `/Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/output/_logs/a-packing-slip-generator-that-renders-fi-20261022-034705-f1d7` (events.jsonl, raw model replies, spec.json)
- harbor job: `/Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/jobs/band-packing-slip-fixed-width-renderer-20261022-051534-5a28-0`
