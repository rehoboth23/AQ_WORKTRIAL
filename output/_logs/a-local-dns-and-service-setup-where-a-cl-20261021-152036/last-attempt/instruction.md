The service `api.internal.local` was recently migrated from a legacy backend (version 1.0 at 127.0.0.2:8080) to the active backend (version 2.0 at 127.0.0.1:8080). Since the migration, the service health check intermittently reports version 1.0 instead of 2.0—roughly half the time it connects to the decommissioned backend.

Eliminate the intermittency so that `api.internal.local` always resolves to the active backend. After your fix, all of these must hold:

1. DNS resolution via the local resolver returns exactly one IP for `api.internal.local`, and it is `127.0.0.1`
2. System host resolution (`getent hosts`) returns only `127.0.0.1` for `api.internal.local`
3. The health check consistently reports version 2.0 across at least 10 consecutive runs
4. Host resolution follows the standard system convention (local files consulted before DNS)
5. Other internal hostnames (`web.internal.local`, `db.internal.local`) must continue to resolve correctly via the local resolver
6. No configuration, script, or code anywhere should direct `api.internal.local` to the decommissioned backend's IP

The project files and documentation are under `/app/`. System DNS/resolver configuration is under `/etc/`. Services are not running at container start—you need to start them yourself. The startup script is `/app/bin/start_services.sh`.
