# LinkVault: CRLF Injection Fix

## Background

LinkVault is a lightweight URL-shortener service written in Python using `http.server`. It runs on port 8080 and is started with:

```
python3 -m linkvault.app
```

The codebase lives in `/app/linkvault/` as a Python package. It handles URL shortening, redirects, user login, profile updates, and a dashboard.

A fresh database is created on first start at `/app/data/linkvault.db`, seeded with an admin user (username `admin`, password `admin123`, display name `Administrator`) and two sample short links.

## Problem

The service has HTTP header injection vulnerabilities: user-supplied data containing CRLF characters (`\r` or `\n`) can break out of header values and inject extra, attacker-controlled header lines into HTTP responses.

**Security property that must hold:** No user-supplied value can ever put a line break (CR or LF) into any HTTP response header, status line, or cookie. This must hold for every endpoint and every code path in the service.

## Your Task

Fix the codebase so the above property holds everywhere. The fix must not break any legitimate functionality — redirects must still redirect, cookies must still be set, error responses must still indicate errors, and headers that do not contain CRLF must be passed through unchanged.

You can test the service by starting it and using `curl` (installed) or any other tool. After making changes, restart the server to pick them up.
