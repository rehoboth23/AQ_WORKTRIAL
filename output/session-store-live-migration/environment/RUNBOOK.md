# Session Service Migration Runbook

## Overview

The session service (`/app/session_svc.py`) currently stores sessions in
SQLite at `/app/data/sessions.db`.  Operations has decided to move to an
append-only log store for durability.  The migration must happen **live**:
traffic continues, no connections drop, no stale reads, no lost writes.

## Current Architecture

| Component | Value |
|-----------|-------|
| Service   | `/app/session_svc.py` |
| Port      | 8080 |
| Backend   | SQLite, `/app/data/sessions.db` |
| Default TTL | 300 s |
| TTL refresh | On read (GET) only |

## Target Architecture

| Component | Value |
|-----------|-------|
| Backend   | Append-only log store, `/app/data/session_log.jsonl` |
| Format    | JSON lines, one entry per line |
| Compaction | `/admin/compact` endpoint |

### Log store entry format

Each line in `session_log.jsonl` is a JSON object:

```json
{
  "session_id": "<uuid>",
  "data":       { ... },
  "expires_at": <unix_timestamp_float>,
  "ts":         <unix_timestamp_float>,
  "op":         "write" | "touch" | "delete"
}
```

* **write** – a new session or a data update (PUT).
* **touch** – TTL refresh on read (GET).  Data is copied from the latest
  write entry; `expires_at` is set to `now + TTL`.
* **delete** – session deletion.

**Read returns the entry with the highest `ts` for a session** (not the
latest by file position).  If the highest-`ts` entry is a delete, the
session is gone (404).  If the highest-`ts` entry's `expires_at` has
passed (`expires_at <= now`), the session is expired (404).

## Migration Procedure

The migration is triggered by `POST /admin/migrate` on the **live**
process.  No restart.

1. **Start dual-write mode** – writes go to both SQLite and the log store.
2. **Copy existing sessions** from SQLite to the log store.
3. **Switch reads** to the log store.
4. **Stop SQLite writes** – SQLite is retired.
5. **Record the migration** in `/app/data/access.log`.

## Rules

1. **Sessions written during the switch-over must not be lost.** Dual-write
   ensures writes arriving mid-switch are persisted to the log store.

2. **Each copied entry must carry its original `updated_at` timestamp from
   SQLite**, so the log store can determine which entry is newer when a
   dual-written update exists.  Using the current time as `ts` for copied
   entries makes them newer than dual-written updates and causes stale
   reads.

3. **TTL refresh on read: reading a session resets its expiry to
   `now + TTL`.** This must be implemented in the log store path (append a
   `touch` entry on GET).

4. **PUT updates data but does NOT refresh TTL.** Only read (GET) refreshes
   TTL.  PUT preserves the existing `expires_at`.

5. **Sessions expiring during the switch must be handled correctly: an
   expired session must return 404, not stale data.** Check
   `expires_at <= now` before copying; skip expired sessions so they are
   absent from the log store and return 404.

6. **After migration, SQLite must not be used for reads or writes.**

7. **After compaction, the log file must be under 2 MB.** Compaction
   rewrites the file keeping only the latest entry (highest `ts`) per
   `session_id`.

8. **Append a migration record to `/app/data/access.log`** with the
   timestamp and the number of sessions migrated.

9. **The migration must happen via `/admin/migrate` on the live process.**
   No restart that drops connections.

10. **Preserve the HTTP API** (endpoints, response formats, cookie format)
    and TTL behaviour.

11. **Precedence:** when dual-write is active, reads come from SQLite until
    the switch; after the switch, reads come from the log store only.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Create session. Body `{data, ttl?}`. Returns 201 `{session_id, data}`. `Set-Cookie: session_id=<uuid>; Path=/`. |
| GET | `/sessions/<id>` | Read session. Returns 200 `{session_id, data}` if valid, 404 `{error: "not found"}` if expired/missing. Refreshes TTL. |
| PUT | `/sessions/<id>` | Update data. Body `{data}`. Returns 200 `{session_id, data}` if valid, 404 if expired/missing. Does NOT refresh TTL. |
| DELETE | `/sessions/<id>` | Delete session. Returns 204 always. |
| POST | `/admin/migrate` | Perform live migration. Returns 200 `{status: "migrated", sessions_migrated: N}`. |
| GET | `/admin/store` | Returns 200 `{store: "sqlite" | "logstore"}`. |
| POST | `/admin/compact` | Compact the log store. Returns 200 `{status: "compacted", entries: N}`. |

**All responses include the header `X-Service-PID: <pid>`.**

## Access Log

`/app/data/access.log` is an append-only text file.  Each migration record
includes:

* Timestamp
* Number of sessions migrated

Example line:

```
2024-06-01T12:00:00.123456 migration: 42 sessions migrated
```

## Practice Tools

* **Load generator:** `/app/loadgen.py` — generates a deterministic request
  stream from a seed and records responses.
  * `python3 /app/loadgen.py --seed 1 --host localhost --port 8080 --output /tmp/log.json`
  * `python3 /app/loadgen.py --seed 1 --stream-only --output /tmp/stream.json`
* **Practice stream:** `/app/practice_stream.json` — the stream for seed 1.
* **Scenario:** `/app/scenario.json` — describes the practice scenario.
* **Smoke test:** `/app/tests_public/test_smoke.py` — covers the idle common
  path.
