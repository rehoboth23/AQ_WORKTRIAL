# Batch auto-execref-bond-060417

Generator `z-ai/glm-5.1`. Eval `openrouter/z-ai/glm-5.3-flash`, reasoning_effort=high, 5 runs per task; learnable = 1-3 passes.
Topics finished: 1 / 1

## Funnel

| stage | tasks | of topics |
|---|---|---|
| spec passed the difficulty gate | 1 | 100% |
| files written | 1 | 100% |
| structural validation passed | 0 | 0% |
| functionally correct (oracle 1, nop 0) | 0 | 0% |
| band-evaluated | 0 | 0% |
| learnable (1-3/5) | 0 | 0% |
| kept (learnable, every failure the model's fault) | 0 | 0% |
| confirmed (a repeat band eval also landed 1-3/5) | 0 | 0% |
| needs review (triage could not explain a failure) | 0 | 0% |

**Yield: 0 / 1 topics kept (0%); 0 / 0 correct tasks learnable (-).**

## Pass distribution (evaluated tasks)

| passes | 0/5 | 1/5 | 2/5 | 3/5 | 4/5 | 5/5 |
|---|---|---|---|---|---|---|
| tasks | 0 | 0 | 0 | 0 | 0 | 0 |
(A too-easy eval stops early once 4 passes make the verdict certain; it counts at the passes reached.)

## Cost and time

- Generation (z-ai/glm-5.1): $2.05
- Band eval (openrouter/z-ai/glm-5.3-flash): $0.00
- Triage (z-ai/glm-5.1): $0.00
- **Total: $2.05**; per topic $2.05
- Per kept task: - (none kept)
- Wall clock: 2.4 h (first to last audit line); summed stage time 2.4 h
- Prices: gateway-reported cost when present, else list prices per 1M tokens: z-ai/glm-5.1 $1.4 in / $4.4 out, openrouter/z-ai/glm-5.3-flash $0.15 / $0.5 (eval uses Harbor's reported cost when present).

## Tasks

| topic | genre | task | stage | critic | verdict | passes | decision | gen $ / min | eval $ / min | why | verdict file |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a bond cash-flow scheduler that reproduces a legacy desk too | exec_ref | - | gen_failed | 6 flag(s), revised | gen_failed | -/- | rejected | $2.05 / 141 | $0.00 / 0 | failed generation: Part 1 checks | /Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/output/_logs/a-bond-cash-flow-scheduler-that-reproduc-20261022-060418-de3b/VERDICT.md |
