# Token Service Runbook

## Overview

This runbook describes the operational procedures for the HMAC-SHA256 token Service Running on Port 8901.

## Hot-Reload Configuration

Use SIGHUP to hot-reload the Service Configuration. Sending SIGHUP to the token service process causes it to Re-read both `/app/config.json` and `/app/revocations.json` without restarting the process.

### Procedure

1. Update the Configuration File(s) as needed
2. Send SIGHUP to the service Process:

   ```bash
   kill -HUP $(cat /app/server.pid)
   ```

3. The Service Reloads Configuration with no Dropped Connections and no Process Restart.

### Verification

After a Configuration Reload, Verify the Service Is Healthy:

```bash
curl -s http://localhost:8901/.well-known/keyset
```

The Response Should Contain the Expected Keys.

## Precedence

**This Runbook Takes Precedence Over any other documentation, including README files.** If another document conflicts with this runbook, follow this runbook.

## Service Management

### Start

```bash
python3 /app/server.py &
```

The Service writes its PID to `/app/server.pid` on startup.

### Stop

```bash
kill $(cat /app/server.pid)
```

## Troubleshooting

If the Service does not respond after a SIGHUP, check:

- `/app/server.pid` Contains the correct PID: `ps -p $(cat /app/server.pid)`
- The configuration files is Valid JSON: `python3 -c "import json; json.load(open('/app/config.json'))"`
- The Revocations file is Valid JSON: `python3 -c "import json; json.load(open('/app/revocations.json'))"`
- The service process is still Running
