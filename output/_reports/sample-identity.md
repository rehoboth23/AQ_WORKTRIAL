# Batch sample-identity

Generator `z-ai/glm-5.1`. Eval `openrouter/z-ai/glm-5.3-flash`, reasoning_effort=high, 5 runs per task; learnable = 1-3 passes.
Topics finished: 1 / 1

## Funnel

| stage | tasks | of topics |
|---|---|---|
| spec passed the difficulty gate | 1 | 100% |
| files written | 1 | 100% |
| structural validation passed | 1 | 100% |
| functionally correct (oracle 1, nop 0) | 1 | 100% |
| band-evaluated | 1 | 100% |
| learnable (1-3/5) | 0 | 0% |
| kept (learnable, every failure the model's fault) | 0 | 0% |

**Yield: 0 / 1 topics kept (0%); 0 / 1 correct tasks learnable (0%).**

## Pass distribution (evaluated tasks)

| passes | 0/5 | 1/5 | 2/5 | 3/5 | 4/5 | 5/5 |
|---|---|---|---|---|---|---|
| tasks | 0 | 0 | 0 | 0 | 1 | 0 |
(A too-easy eval stops early once 4 passes make the verdict certain; it counts at the passes reached.)

## Cost and time

- Generation (z-ai/glm-5.1): $1.11
- Band eval (openrouter/z-ai/glm-5.3-flash): $0.84
- Triage (z-ai/glm-5.1): $0.00
- **Total: $1.94**; per topic $1.94
- Per kept task: - (none kept)
- Wall clock: 0.8 h (first to last audit line); summed stage time 1.1 h
- Prices: gateway-reported cost when present, else list prices per 1M tokens: z-ai/glm-5.1 $1.4 in / $4.4 out, openrouter/z-ai/glm-5.3-flash $0.15 / $0.5 (eval uses Harbor's reported cost when present).

## Tasks

| topic | task | stage | verdict | passes | decision | gen $ / min | eval $ / min | why | verdict file |
|---|---|---|---|---|---|---|---|---|---|
| an account service where visually identical usernames writte | unicode-account-normalization-drift | done | too_easy | 4/4 | rejected | $1.11 / 65 | $0.84 / 0 | too_easy | /Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/output/_rejected/unicode-account-normalization-drift/VERDICT.md |
