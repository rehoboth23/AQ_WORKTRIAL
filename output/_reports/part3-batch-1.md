# Batch part3-batch-1

Generator `z-ai/glm-5.1`. Eval `openrouter/z-ai/glm-5.3-flash`, reasoning_effort=high, 5 runs per task; learnable = 1-3 passes.
Topics finished: 3 / 4 (batch still running or was killed; `--resume` continues it)

## Funnel

| stage | tasks | of topics |
|---|---|---|
| spec passed the difficulty gate | 3 | 75% |
| files written | 3 | 75% |
| structural validation passed | 3 | 75% |
| functionally correct (oracle 1, nop 0) | 2 | 50% |
| band-evaluated | 2 | 50% |
| learnable (1-3/5) | 1 | 25% |
| kept (learnable, every failure the model's fault) | 0 | 0% |
| confirmed (a repeat band eval also landed 1-3/5) | 0 | 0% |
| needs review (triage could not explain a failure) | 0 | 0% |

**Yield: 0 / 4 topics kept (0%); 1 / 2 correct tasks learnable (50%).**

## Pass distribution (evaluated tasks)

| passes | 0/5 | 1/5 | 2/5 | 3/5 | 4/5 | 5/5 |
|---|---|---|---|---|---|---|
| tasks | 0 | 0 | 0 | 1 | 1 | 0 |
(A too-easy eval stops early once 4 passes make the verdict certain; it counts at the passes reached.)

## Cost and time

- Generation (z-ai/glm-5.1): $2.93
- Band eval (openrouter/z-ai/glm-5.3-flash): $0.09
- Triage (z-ai/glm-5.1): $0.02
- **Total: $3.04**; per topic $0.76
- Per kept task: - (none kept)
- Wall clock: 1.4 h (first to last audit line); summed stage time 3.7 h
- Prices: gateway-reported cost when present, else list prices per 1M tokens: z-ai/glm-5.1 $1.4 in / $4.4 out, openrouter/z-ai/glm-5.3-flash $0.15 / $0.5 (eval uses Harbor's reported cost when present).

## Tasks

| topic | task | stage | verdict | passes | decision | gen $ / min | eval $ / min | why | verdict file |
|---|---|---|---|---|---|---|---|---|---|
| a bulk data export that can be stopped and resumed with a ch | - | gen_failed | gen_failed | -/- | rejected | $1.15 / 79 | $0.00 / 0 | failed generation: Part 1 checks | /Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/output/_logs/a-bulk-data-export-that-can-be-stopped-a-20261022-001322-3fb5/VERDICT.md |
| a webhook consumer that records payments from a provider tha | payment-webhook-idempotency | done | learnable | 3/5 | rejected | $1.00 / 61 | $0.06 / 5 | unfair: the failing assertion requires the receiver to print 'duplicate' for a retry of an already-processed event; instruction.md states only the balance invar | /Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/output/_rejected/payment-webhook-idempotency/VERDICT.md |
| an event-sourced inventory ledger that accepts late correcti | event-sourced-ledger-corrections | done | too_easy | 4/4 | rejected | $0.79 / 48 | $0.02 / 1 | too_easy (stopped early after 4 passes) | /Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/output/_rejected/event-sourced-ledger-corrections/VERDICT.md |
| a command-line notes tool whose on-disk store is being upgra | - | generating | - | -/- | - | $0.00 / 29 | $0.00 / 0 |  | - |
