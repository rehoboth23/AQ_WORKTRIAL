# Token Service

## Overview

The HMAC-SHA256 Token Service issues and verifies bearer tokens for internal
microservices. It listens on port 8901 and provides the following endpoints:

- `POST /issue` — Sign and return a new token
- `POST /verify` — Validate a token's signature and expiry
- `POST /revoke` — Add a token's JTI to the revocation list
- `GET /.well-known/keyset` — Return the current signing key(s)

## Configuration

Configuration is stored in `/app/config.json`. The server reads this file on
startup. After making changes to the configuration (for example, adding a new
signing key or changing the active key ID), you **must restart the service**
for changes to take effect:

```bash
kill $(cat /app/server.pid)
python3 /app/server.py &
```

Revocations are stored in `/app/revocations.json`, which is also read at
startup.

## Token Format

Tokens are formatted as `base64url(header).base64url(payload).base64url(signature)`.

- **Header**: `{alg, kid, typ}` — `alg` is `HS256`, `kid` identifies the
  signing key, `typ` is `JWT`.
- **Payload**: `{sub, iat, exp, jti}` — `sub` is the subject, `iat` and
  `exp` are Unix timestamps, `jti` is a unique token identifier.
- **Signature**: HMAC-SHA256 of `base64url(header).base64url(payload)` using
  the key identified by `kid`.

## Key Rotation

To rotate the signing key:

1. Generate a new 256-bit key secret (base64url-encoded).
2. Add the new key entry to the `keys` map in `/app/config.json`.
3. Update `signing_key_id` in `/app/config.json` to point to the new key.
4. **Restart the service** to reload the configuration.
5. Wait for any tokens issued under the old key to expire.
6. Remove the old key from the `keys` map in `/app/config.json`.
7. **Restart the service** again.

For the complete rotation procedure, see the rotation policy document.

## Monitoring

The server writes its process ID to `/app/server.pid`. Use this PID to
send signals or to confirm the service is running.
