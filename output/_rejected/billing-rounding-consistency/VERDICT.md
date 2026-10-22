# Verdict: rejected

- Topic: [judgement] a billing module where every monetary amount must be rounded the same way at every boundary, violated in several places that use different arithmetic paths
- Task: billing-rounding-consistency
- Why: too_easy (stopped early: 3 passes, no failure yet; EARLY_STOP_PASSES=3)
- Generator: `z-ai/glm-5.1`; eval: `openrouter/z-ai/glm-5.3-flash`, reasoning_effort=high, 5 runs, learnable = 1-3 passes

## Generation

- spec gate (attempt 0): pass
- critic: {"too_easy_because": ["rounding.py and currency.py share the same mechanism (Decimal.quantize with ROUND_HALF_EVEN) \u2014 a single grep for 'ROUND_HALF_EVEN' finds both sites, so fixing one and searching for its pattern reveals the other. This reduces the effective number of independent sites from 5 to 4, and means the agent only needs 3 independent searches (ROUND_HALF_EVEN, round, and then read
- instruction_review: {"verdict": "leaks", "leaks": ["\"A customer reports that a $1.00 item with a 12.5% tax rate shows a tax of $0.12 instead of $0.13. This violates the round-half-up rule.\" -> reveals diagnosis (WHERE the problem is: tax calculation) and a specific symptom pointing to site 1", "\"The library has a central rounding utility in `rounding.py` \u2014 make sure all modules are consistent with it.\" -> po
- instruction_review: {"verdict": "leaks", "leaks": ["\"A customer reported that tax on an item was off by a cent \u2014 a value exactly halfway between two possible cent amounts was rounded down when it should have rounded up.\" -> reveals WHERE the problem is (tax) and gives a numbered symptom, fault types 1 and 2", "\"never to the nearest even cent\" -> reveals the crux that banker's rounding is the wrong mechanism,
- instruction_review: {"verdict": "leaks", "leaks": ["\"A customer reports that a $1.00 item with a 12.5% tax rate shows $0.12 tax instead of $0.13.\" -> reveals a specific symptom pointing to one fault location (tax calculation), violating #1 and #2; also gives exact expected output values violating #8"]}
- spec gate (attempt 0): pass
- critic: {"too_easy_because": ["Sites 2 and 4 originally both used quantize() \u2014 a single grep for 'quantize' would find both, violating the 'no shared mechanism / one search finds both' rule.", "instruction_summary stated 'Module paths and all public function signatures are listed', giving the agent a complete roadmap of every function to check, reducing the discovery challenge."], "revised_gate": []}
- instruction_review: {"verdict": "leaks", "leaks": ["\"A correct helper, `round_money()`, already exists in `billing/utils.py` and implements this rule. Every function that produces a monetary amount should use it (or an equivalent round-half-up mechanism).\" -> fault 4 (pointer to where the answer lives) and fault 9 (the fix technique itself)", "\"Invoice INV-1042 shows a tax of $2.44 on a $39.12 subtotal at 6.25%. T
- instruction_review: {"verdict": "leaks", "leaks": ["\"A customer reported that invoice INV-1042 shows tax of $2.44 on a $39.12 subtotal at 6.25%, but $39.12 \u00d7 6.25% = $2.445 should round to $2.45 with round-half-up.\" -> reveals exact symptom (#2), exact expected output (#8), and WHERE the fault lives (#1: tax calculation)", "\"Investigation suggests this is not an isolated mistake \u2014 not all monetary calcul
- round 0: difficulty gate: instruction.md names shipped source/config files (bulk.py, core.py, discounts.py, fees.py, tax.py, utils.py); which points the agent at the fault; describe the symptom and goal instead and let the agent find the location | checks: not run
- round 1: difficulty gate: pass | checks: validator=pass, oracle=pass (reward 1.0), nop=pass (reward 0.0)
- result: ok

## Band eval: 3/3 passed (2 invalid re-run) -> too_easy

| trial | outcome | steps | cost | failed tests | triage |
|---|---|---|---|---|---|
| billing-rounding-consistency__ChW9Gk6 | pass | 8 | 0.009226454 | - | - |
| billing-rounding-consistency__dfWieUQ | invalid (CancelledError) | 8 | 0.007370429 | - | - |
| billing-rounding-consistency__gzG5dxu | pass | 8 | 0.009711527999999999 | - | - |
| billing-rounding-consistency__kg2FDpY | pass | 10 | 0.013297637000000001 | - | - |
| billing-rounding-consistency__mGMKSj6 | invalid (CancelledError) | 9 | 0.010365489 | - | - |

## Lesson

The billing-rounding-consistency task was well-tested (all 11 mutations killed) but too easy for agents, who passed in only 8–10 steps; the 'invalid' outcomes were environment issues rather than difficulty. The next design should keep the strong mutation-killing test coverage but add more independent rules around new billing edge cases (e.g., currency conversion rounding, tax-tier boundaries, multi-item discount interactions) to increase task depth and require more than a quick fix.

## Evidence

- generation log: `/Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/output/_logs/a-billing-module-where-every-monetary-am-20261022-020120-8df4` (events.jsonl, raw model replies, spec.json)
- harbor job: `/Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/jobs/band-billing-rounding-consistency-20261022-031707-c2cf-0`
