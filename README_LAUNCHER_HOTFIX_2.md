# ProjectX Final Launcher Hotfix 2

Fixes a Windows virtual-environment launcher PID mismatch. `Start-Process` can return the small venv launcher PID while the child Python interpreter owns the gRPC socket. The old final launcher incorrectly marked all services OFFLINE even though their logs showed successful startup.

The fixed launcher starts only when ports 50051-50061 are free, waits for each real listener, records both launcher and listener PIDs, and clears stale logs. The stop script understands both the new state file and the older PID format.
