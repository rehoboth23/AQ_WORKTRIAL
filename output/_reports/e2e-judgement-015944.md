# Batch e2e-judgement-015944

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
| learnable (1-3/5) | 1 | 100% |
| kept (learnable, every failure the model's fault) | 0 | 0% |
| confirmed (a repeat band eval also landed 1-3/5) | 0 | 0% |
| needs review (triage could not explain a failure) | 0 | 0% |

**Yield: 0 / 1 topics kept (0%); 1 / 1 correct tasks learnable (100%).**

## Pass distribution (evaluated tasks)

| passes | 0/5 | 1/5 | 2/5 | 3/5 | 4/5 | 5/5 |
|---|---|---|---|---|---|---|
| tasks | 0 | 0 | 0 | 1 | 0 | 0 |
(A too-easy eval stops early once 4 passes make the verdict certain; it counts at the passes reached.)

## Cost and time

- Generation (z-ai/glm-5.1): $0.73
- Band eval (openrouter/z-ai/glm-5.3-flash): $0.22
- Triage (z-ai/glm-5.1): $0.04
- **Total: $0.99**; per topic $0.99
- Per kept task: - (none kept)
- Wall clock: 1.1 h (first to last audit line); summed stage time 0.9 h
- Prices: gateway-reported cost when present, else list prices per 1M tokens: z-ai/glm-5.1 $1.4 in / $4.4 out, openrouter/z-ai/glm-5.3-flash $0.15 / $0.5 (eval uses Harbor's reported cost when present).

## Tasks

| topic | genre | task | stage | critic | verdict | passes | decision | gen $ / min | eval $ / min | why | verdict file |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [judgement] a small HTTP service whose responses must never  | judgement | http-header-crlf-injection-audit | done | 5 flag(s), revised | learnable | 3/5 | rejected | $0.73 / 47 | $0.22 / 5 | unfair: the test fixture deleted the database and silently queried the agent's orphaned server on port 8080 (the agent's code pa; the agent rejected CRLF input  | /Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/output/_rejected/http-header-crlf-injection-audit/VERDICT.md |
