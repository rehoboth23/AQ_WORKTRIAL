# Key Rotation for HMAC Token Service

You are the on-call engineer for an internal HMAC-SHA256 token service. A key rotation is due. The service is running at `/app/server.py` on port 8901 with endpoints for `/issue`, `/verify`, `/revoke`, and `/.well-known/keyset`. Configuration is in `/app/config.json` and revocations in `/app/revocations.json`.

## The Problem

The `/verify` handler has a subtle bug that only manifests during key rotation: once the signing key switches, tokens signed with the old key fail verification even though they are still valid. **Identify and fix this bug before attempting the rotation.**

The documentation contains a contradiction: `/app/docs/README.md` says to restart the service after config changes, while `/app/docs/runbook.md` says to use SIGHUP for hot-reload.

## Your Task

1. **Fix the verification bug**: Identify and fix the bug in `/app/server.py`'s `/verify` handler so that old-key tokens are no longer rejected after the signing key switches.

2. **Create `/app/rotate_keys.sh`**: Write a script that performs the full 8-step key rotation procedure defined in `/app/docs/rotation-policy.md`. The script must:
   - Log every step to `/app/key-management.log` in the format specified by the policy
   - Use SIGHUP for hot-reload (never restart the service)
   - Read `token_lifetime_seconds` from `/app/config.json` for the overlap wait duration
   - Follow the step order specified in the policy

3. **Run the rotation**: Start the server, then the practice simulator at `/app/simulator/practice_sim.py`, then run `/app/rotate_keys.sh` while the simulator is active. **Zero valid tokens must be rejected and zero revoked tokens must be accepted.**

## Acceptance Criteria

- Zero valid tokens rejected during rotation
- Zero revoked tokens accepted during rotation
- The service must not restart during rotation — use SIGHUP per the runbook
- No connection errors in the simulator log
- The key-management log at `/app/key-management.log` is audited and graded: every step must be recorded in the correct format with ISO 8601 timestamps, step numbers, descriptions, and key IDs
- Everything the tool does today must keep working — the `/verify` response format, the `/issue` token format, and all existing API contracts must remain unchanged

Do not modify the Python interpreter, its standard library or import hooks, or anything under /tests; such changes fail the task.
