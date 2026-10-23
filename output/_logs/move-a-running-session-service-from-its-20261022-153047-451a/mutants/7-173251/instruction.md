You are migrating a running session service from SQLite to an append-only log store.

The session service runs on port 8080 at `/app/session_svc.py`. It currently uses SQLite at `/app/data/sessions.db`. Read `/app/RUNBOOK.md` for the migration procedure and all rules. The runbook is authoritative.

Your task: implement the append-only log store and wire it into the service so that `POST /admin/migrate` performs a live migration with zero failed or stale responses. The service must keep running on port 8080 throughout—use the `/admin/migrate` endpoint on the live process, do not restart the service.

Key requirements from the runbook:

- **Log store path:** `/app/data/session_log.jsonl`, append-only JSON lines. Each entry has `session_id`, `data`, `expires_at`, `ts`, `op` (write/touch/delete).
- **Read returns the entry with the highest `ts` for a session**, not the latest by file position.
- **Dual-write:** during the switch-over, writes must go to both stores so no session is lost.
- **Copy uses original `updated_at` from SQLite as `ts`**, not the current time—otherwise dual-written updates are shadowed.
- **Skip expired sessions when copying** (check `expires_at <= now` before copying).
- **After migration, SQLite must not be used for reads or writes.**
- **TTL refresh on read only:** GET refreshes TTL (`expires_at = now + TTL`). PUT updates data but does NOT refresh TTL—`expires_at` is unchanged.
- **Compaction:** `POST /admin/compact` rewrites the log keeping only the latest entry per session. File must be under 2 MB after compaction.
- **Access log:** append a migration record to `/app/data/access.log` with timestamp and session count.
- **All responses must include header `X-Service-PID: <pid>`.**
- `GET /admin/store` must return `{"store": "sqlite"}` before migration and `{"store": "logstore"}` after.

Preserve the HTTP API exactly: endpoints, status codes, JSON response shapes, and `Set-Cookie: session_id=<uuid>; Path=/` on create.

A practice load generator is at `/app/loadgen.py` and a smoke test at `/app/tests_public/test_smoke.py`. Use them to verify your work.

Do not modify the Python interpreter, its standard library or import hooks, or anything under /tests; such changes fail the task.
