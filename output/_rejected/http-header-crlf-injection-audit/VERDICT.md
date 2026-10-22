# Verdict: rejected

- Topic: [judgement] a small HTTP service whose responses must never let a user-supplied value break out of a header, cookie or redirect, violated in several differently built places
- Task: http-header-crlf-injection-audit
- Why: unfair: the test fixture deleted the database and silently queried the agent's orphaned server on port 8080 (the agent's code pa; the agent rejected CRLF input with a 400 instead of sanitising it; instruction.md never says which of the two valid fixe (re-triaged by hand; the pipeline's confirmation eval scored 4/4 too easy)
- Generator: `z-ai/glm-5.1`; eval: `openrouter/z-ai/glm-5.3-flash`, reasoning_effort=high, 5 runs, learnable = 1-3 passes

## Generation

- spec gate (attempt 0): pass
- critic: {"too_easy_because": ["In the original spec, 4 out of 5 sites use send_header, so a single grep for 'send_header' reveals Sites 1, 2, 3, and 4 at once.", "Overriding send_header centrally fixes 4 of 5 sites automatically \u2014 the agent never needs to discover Sites 2, 3, or 4 individually.", "The only non-send_header site (Site 5, wfile.write) is found by a single additional grep for 'wfile.writ
- instruction_review: {"verdict": "leaks", "leaks": ["\"A security review found that visiting a redirect endpoint whose stored target URL contains CRLF characters (`\\r\\n`) causes extra, attacker-controlled headers to appear in the HTTP response. For example, creating a short link with the URL `http://example.com\\r\\nX-Injected: pwned` and then visiting `/go/{code}` results in an `X-Injected: pwned` header appearing 
- instruction_review: {"verdict": "leaks", "leaks": ["\"A security review found that visiting a redirect endpoint whose stored target URL contains CRLF characters (`\\r\\n`) causes extra, attacker-controlled headers to appear in the HTTP response.\" -> reveals WHERE the fault is (redirect endpoint, stored target URL = site 0) and the specific symptom for that fault", "\"For example, creating a short link with a URL lik
- round 0: difficulty gate: instruction.md names shipped source/config files (app.py, auth.py, response.py, store.py); which points the agent at the fault; describe the symptom and goal instead and let the agent find the location | checks: not run
- round 1: difficulty gate: pass | checks: validator=pass, oracle=pass (reward 1.0), nop=pass (reward 0.0)
- result: ok

## Band eval: 3/5 passed (0 invalid re-run) -> learnable

| trial | outcome | steps | cost | failed tests | triage |
|---|---|---|---|---|---|
| http-header-crlf-injection-audit__49UDMKj | fail | 9 | 0.009043191 | test_redirect_no_crlf, test_cookie_no_crlf, test_request_id_no_crlf, test_display_name_no_crlf, test_clean_redirect_still_works | task: the test fixture deleted the database and silently queried the agent's orphaned server on port 8080 (the agent's code passes all 6 tests when the port is free; reproduced in the task image) |
| http-header-crlf-injection-audit__CuWqUQN | pass | 9 | 0.008845044 | - | - |
| http-header-crlf-injection-audit__Jwnf9Hp | pass | 9 | 0.014936936000000001 | - | - |
| http-header-crlf-injection-audit__Ke6ga76 | fail | 10 | 0.013350657999999998 | test_redirect_no_crlf, test_request_id_no_crlf | task: the agent rejected CRLF input with a 400 instead of sanitising it; instruction.md never says which of the two valid fixes is required, and the tests pin 'sanitise' (header present, JSON body) |
| http-header-crlf-injection-audit__kr6AAoX | pass | 9 | 0.0144436 | - | - |
- confirmation eval 1: 4/5 -> too_easy
- **confirmed: no** (every repeat eval must land 1-3/5)

## Lesson

The task split 3/2 pass/fail because of a critical ambiguity: the instructions didn't clearly specify that CRLF must be stripped/sanitized rather than rejected with 400 errors, so one failing agent rejected requests entirely (breaking test_redirect_no_crlf, test_request_id_no_crlf) while another's sanitization crashed the server (breaking test_clean_redirect_still_works and others). All passing runs correctly stripped CRLF while preserving normal HTTP functionality across redirect, cookie, request-id, and display-name paths. Next design should add an explicit rule distinguishing 'sanitize by stripping' from 'reject with error' and keep the dual-property structure (security + functionality) since the mutation check killed all 5 faults.

## Evidence

- generation log: `/Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/output/_logs/a-small-http-service-whose-responses-mus-20261022-015944-4181` (events.jsonl, raw model replies, spec.json)
- harbor job: `/Users/rehobothokorie/Desktop/afterquery_platform_engineer_work_trial/jobs/band-http-header-crlf-injection-audit-20261022-024633-e1fe-0`
