# DocVault Security Fix

You are maintaining **DocVault**, a small internal document-management service written in Python using the standard library's `http.server`. The code lives under `/app/docvault/` and is started with:

```
cd /app && python3 -m docvault.server
```

It listens on port **8080**. The SQLite database is created on first run with seed data. There is no test suite and no verify command — start the service yourself to check its responses.

## Problem

A security audit found that the service does not properly sanitize user-supplied data before incorporating it into HTTP responses, allowing crafted input to manipulate those responses in unintended ways. The initial finding was that CRLF characters in a user-supplied field could inject extra response headers, but the auditors noted the issue is broader. Fix every instance of this vulnerability class throughout the codebase.

The fixed service must enforce the following security invariants:

- **No CRLF in header values.** Carriage returns (`\r`) and line feeds (`\n`) must never appear in any response header value that incorporates user-supplied data. When such characters are present, strip them and use the remaining string; do not reject the request.
- **No open redirects.** When a user-supplied value is used as a redirect target, external URLs (those starting with `http://`, `https://`, or `//`) must not be followed. Redirect to `/` instead. Relative paths starting with `/` must redirect normally.
- **No cookie attribute injection.** Semicolons (`;`) must never appear in the value portion of a `Set-Cookie` header that incorporates user-supplied data. When a semicolon is present, strip it and use the remaining string; do not reject the request.

Where a single value falls under more than one invariant, the result must satisfy all of them.

## Constraints

- **Preserve all existing behaviour.** Every endpoint must keep working exactly as today for normal (non-malicious) inputs. Do not rewrite the service or remove functionality.
- Fix the code in place under `/app/docvault/`. You may add helper functions where useful.
- "User-supplied data" means: JSON body fields, query parameters, URL path segments (after URL decoding), and data stored in the database that originally came from users. Values the server generates itself (request IDs, computed lengths, etc.) are not user-supplied and do not need sanitization.
- Check every code path where user-supplied data reaches an HTTP response, including indirect paths through helper functions, database lookups, and URL-decoded path segments.

## Current endpoints (behaviour to preserve)

- `GET /api/docs` — list documents as a JSON array.
- `GET /api/docs/{title}` — get one document as JSON.
- `POST /api/docs` — create a document; body `{"title","author","content"}`; returns `201` with an `X-Authored-By` header.
- `GET /api/exports/{filename}` — returns a download with a `Content-Disposition` header built from the filename.
- `GET /login?next={path}` — redirects to `next` (`302` with a `Location` header).
- `GET /api/go/{code}` — looks up a stored shortcut URL and redirects to it (`302` with a `Location` header).
- `POST /api/shortcuts` — body `{"code","url"}` — stores a shortcut.
- `POST /api/prefs` — body `{"layout"}` — sets a `layout` cookie (`Set-Cookie: layout=...; Path=/`).
- `POST /api/docs/{title}/star` — sets a `starred` cookie (`Set-Cookie: starred={title}; Path=/`).
