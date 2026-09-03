# ProjectX v2.1 — HR + Admin approval + QR authentication

This ZIP is an **overlay for the validated 76bcde1 backend**. It supersedes the earlier QR-only/HR-auth overlays.

It deliberately extends the original 11-service cahier baseline with a 12th gRPC service:
- `HRService` on `50062`
- DB `hospital_hr`
- employee registry
- shift planning
- attendance clock-in/out + HR correction
- leave requests + HR review
- HR dashboard + audit

Auth is also completed for the controlled hospital onboarding flow:
- no public signup;
- HR creates staff access request only;
- Admin assigns final role and approves;
- QR credential generated only after approval;
- password and QR login return the same identity/RBAC/JWT;
- QR can be rotated/revoked and expires.

Read `PROJECTX_SERVICES_REGISTRY.md` first. It is the current architecture registry and clearly marks what is official v2.0 versus ProjectX v2.1 extension.

## Installation order

1. Stop all existing ProjectX services.
2. Extract this ZIP over `D:\skl\HospitalisationMicroService` with `-Force`.
3. Run:

```powershell
$env:PYTHONPATH="$PWD;$PWD\generated"
.\scripts\install_hr_extension_v2_1.ps1
```

4. Start all services:

```powershell
.\scripts\start_all_services.ps1
```

5. Expected listener count is now **12/12**.
6. Run:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_all_services_health.py
.\.venv\Scripts\python.exe .\scripts\test_hr_extension_smoke.py
```

Do not paste passwords or raw QR payloads into chat/logs/source control.
