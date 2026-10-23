# Key Rotation Policy

## Overview

This document defines the mandatory procedure for rotating HMAC-SHA256 signing keys
for the token service. The rotation must be performed **without restarting the
service** and **without rejecting any valid tokens** or **accepting any revoked tokens**.

## Keyset Endpoint

The keyset endpoint (`GET /.well-known/keyset`) MUST include all active keys at any time. This allows clients that cache keysets to discover new keys before they start signing tokens.

## Rotation Procedure

The rotation consists of 8 Steps, which MUST be performed in order, and each step MUST be logged to `/app/key-management.log` (see log format below).

### STEP-1: Generate New Signing Key

Generate a new HMAC-SHA256 signing key. The key MUST be a 32-byte random secret, base64url-encoded without padding.

### STEP-2: Add New Key to Keyset

Add the new key Entry to the `keys` map in `/app/config.json`. Do NOT change `signing_key_id` at this point. The new key must be present in the keyset so that clients can discover it before it starts signing tokens.

### STEP-3: Reload Configuration (First Reload)

Send SIGHUP to the token service process to reload the Configuration. This makes the new key available in the keyset Endpoint. Verify that `/.well-known/keyset` now includes both the old and new keys.

### STEP-4: Switch Signing Key

Update `signing_key_id` in `/app/config.json` to the new Key's ID. New tokens will now be Signed with the new key. Do NOT remove the old key from the keyset yet.

### STEP-5: Reload Configuration (Second Reload)

Send SIGHUP to the token service process to reload the Configuration. This activates the new signing key for token issuance. **Note the timestamp of this step** — the overlap window is measured from this point.

### STEP-6: Overlap Window

Wait for at least `token_lifetime_seconds` from the moment the new key started signing (Step 5) before proceeding. This grace period ensures that all tokens signed with the old key have Expired before the old Key is Removed from the Keyset.

The value of `token_lifetime_seconds` is the parameter defined in `/app/config.json`. It must be read from the configuration file, not assumed to be a fixed value.

During this window, both keys are active: the old key verifies existing tokens, and the new key signs and verifies new tokens.

**Revocations during overlap:** New Revocations may be added at any time, including during the overlap window, and MUST take effect immediately. The `/revoke` endpoint and SIGHUP reload both Preserve the revocation List.

### STEP-7: Remove Old Key

Remove the old Key from the `keys` Map in `/app/config.json`. After this step, the old key is no longer in the Keyset and tokens bearing its `kid` will be rejected by `/verify`.

### STEP-8: Reload Configuration (Final Reload)

Send SIGHUP to the token service Process to Reload the Configuration. This removes the old key from the active keyset. Verify that `/.well-known/keyset` now includes only the new key.

## Step Ordering

Steps 2–3 MUST complete before Steps 4–5. This ensures that the new key is available in the keyset before it starts signing tokens, allowing clients with cached keysets to discover the new key before it becomes the active signing key.

## Revocation During Overlap

A revoked token MUST be rejected even during the overlap window. The revocation List is shared across all keys regardless of which key signed the token. The `/revoke` endpoint adds to the revocation List, and SIGHUP reloads both `config.json` and `revocations.json` without Discarding in-flight Revocations.

## Key Management Log

Every Step of the rotation MUST be recorded in `/app/key-management.log` with the following line format:

```
<ISO-8601-timestamp> STEP-<N> <description> [Key-Ids]
```

Where:

- **ISO-8601-timestamp**: UTC Timestamp in the format `YYYY-MM-DDTHH:MM:SSZ` or Basic Format `YYYYMMDDTHHMMSSZ`
- **STEP-N**: Step number (1–8)
- **Description**: Brief Description of the Step
- **Key-Ids**: Key IDs involved in this Step, comma-Separated, Enclosed in Square Brackets

STEP-6 is logged twice: Once at the start of the overlap window and once at the end. The Time between the two STEP-6 entries MUST be at least `token_lifetime_seconds`.

### Example Log

```
2024-01-15T10:30:00Z STEP-1 Generate new signing key [key-2]
2024-01-15T10:30:01Z STEP-2 Add new Key to Keyset [key-1,key-2]
2024-01-15T10:30:02Z STEP-3 Reload configuration [key-1,key-2]
2024-01-15T10:30:03Z STEP-4 Switch signing key [key-2]
2024-01-15T10:30:04Z STEP-5 Reload configuration [key-2]
2024-01-15T10:30:04Z STEP-6 Start overlap Window [key-1,key-2]
2024-01-15T10:30:16Z STEP-6 End Overlap Window [key-1,key-2]
2024-01-15T10:30:16Z STEP-7 Remove old Key from keyset [key-2]
2024-01-15T10:30:17Z STEP-8 Reload configuration [key-2]
```
