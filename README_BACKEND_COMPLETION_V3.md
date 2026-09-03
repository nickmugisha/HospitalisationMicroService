# ProjectX Backend Completion v3 — pre-client freeze candidate

> Packaging/runtime revision: **v3.0.2**. Pharmacy stock-alert daily de-duplication uses a 64-character SHA-256 fingerprint to remain compatible with database installations enforcing a 1000-byte index-key limit.

This package completes the backend contract gaps identified after the v2.2 HR/QR/Attendance and Chatbot v2 validations. It is designed to preserve the validated 12-service baseline and to minimize contract churn once the Linux client starts real integration.

## What this completion adds

### Laboratory
- `ListLabTests`, `GetLabTest`.
- Safe `lab.catalog.read` permission for clinical catalogue selection.
- Validated lab results send a best-effort internal notification to the ordering Auth user when that ID is available.

### Pharmacy / stock / logistics
- Safe medicine discovery permission `pharmacy.catalog.read` for doctors/sage-femmes without exposing stock management.
- Medicine create/update administration.
- Prescription inbox: list/get exposed Consultation prescriptions.
- Supplier create/update/list.
- Purchase order get/list in addition to existing create/receive.
- Server-side stock-alert notification worker with daily fingerprint de-duplication.

### Hospitalisation
- Ward/room/bed read and administration RPCs.
- Inactive wards cannot accept new rooms/beds or available/admitted beds; occupied wards cannot be disabled.
- Explicit admission approval with approving user, timestamp and reason.
- Admission history listing.
- Doctor directory/workload and assignment workflow.
- Busy doctor generates a warning but can still receive another patient, as required.
- One ACTIVE doctor assignment per admission is additionally protected by a nullable unique DB key, preventing concurrent double assignment.
- Doctor assignment completion and automatic completion at discharge.

### HR / attendance
- Overnight shifts (for example 20:00→08:00).
- Cross-midnight shift overlap detection.
- Shift update with audit reason.
- Employee self-read: current attendance, attendance history, shifts, leave history.
- Employee can cancel only their own pending leave request.
- HR audit listing.
- Premature/future attendance-day finalization blocked.
- Dashboard separates `not_started_today` from real absences.
- HR employee profile updates synchronize to Auth.
- HR SUSPENDED/INACTIVE/TERMINATED synchronizes access state to Auth; TERMINATED revokes QR.
- HR ACTIVE does not override an Admin-disabled/pending/rejected account.

### Auth / notifications
- Limited professional staff directory.
- Controlled HR→Auth staff profile/employment synchronization.
- Manual `SendNotification` now has a dedicated permission.
- Internal-only notification RPCs use `x-projectx-service-token`, generated locally in `.env`; the token is never returned to the client and must never be committed.

### Rendez-vous
- Slot update/block.
- Patient appointment history.
- NO_SHOW transition after the slot ends.
- Real timed reminder worker with retry before appointment time.
- Reminder rescheduled when appointment moves.
- A requested reminder requires an explicit Auth `reminder_recipient_user_id`; ProjectX intentionally does not guess a patient→Auth mapping that does not exist.

### Billing / Maternity / BI
- Billing can notify an explicit Auth recipient after payment/reversal.
- Maternity case list/search and close-after-delivery; relevant maternity events may notify sage-femmes.
- BI includes HR in 12-service health and supports a service filter.
- Date filters remain truthful: exact where source contracts support historical periods; otherwise quality becomes PARTIAL with a warning instead of presenting current/all-time metrics as historical facts.

### Operational safety
- `backup_projectx_mysql.py` backs up all 12 logical MySQL databases.
- `restore_projectx_mysql.py` verifies all 12 dumps + manifest before dropping any database and requires `--confirm RESTORE_PROJECTX`.
- The safe installer takes a database backup and a code/generated-stub/.env snapshot before copying the v3 payload.

## What does NOT change

- Ports remain 50051–50062.
- Accueil and Consultation existing contracts are not broken.
- Existing RPC signatures and existing protobuf field numbers are preserved; v3 contract changes are additive.
- Chatbot v2 behavior remains the validated bilingual/public-private/permission-aware implementation.
- Existing HR password/QR onboarding rules remain intact.
- Client still has no direct MySQL access.

## Installation model

Use the **safe installer ZIP** rather than copying files manually. Services must be stopped. The installer:

1. checks project/.venv/.env and that ports 50051–50062 are not listening;
2. creates a private SQL backup of all 12 ProjectX databases;
3. snapshots every file that will be replaced, relevant generated stubs and `.env`;
4. copies the v3 payload;
5. generates a private `PROJECTX_INTERNAL_SERVICE_TOKEN` if missing, without printing its value;
6. regenerates affected gRPC Python stubs;
7. applies only additive Hospitalisation/Pharmacy/Rendez-vous migrations;
8. refreshes canonical RBAC permissions;
9. compiles changed code and verifies proto↔service coverage.

If post-copy installation fails, the outer safe installer restores the previous code/generated stubs/.env snapshot. Applied DB migrations are deliberately not auto-downgraded; they are additive and the pre-install database dump is kept for a deliberate restore if ever required.

## Runtime regression order after installation

Run the services and then verify, in this order:

```powershell
$env:PYTHONPATH="$PWD;$PWD\generated"
.\scripts\start_all_services.ps1
.\.venv\Scripts\python.exe .\scripts\test_all_services_health.py
.\.venv\Scripts\python.exe .\scripts\test_backend_completion_v3_readonly.py
.\.venv\Scripts\python.exe .\scripts\test_hr_extension_smoke.py
.\.venv\Scripts\python.exe .\scripts\test_chatbot_v2_full_e2e.py
```

Expected checkpoints:
- 12/12 services ONLINE.
- v3 read-only regression PASS.
- existing HR/Auth/QR/Attendance smoke PASS.
- existing Chatbot v2 full E2E PASS (60/60 and 13/13 live intents on the validated baseline; test count may rise only if the test itself is later extended).

### Explicit write/security regression

After the read-only regression is clean, optionally run:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_backend_completion_v3_hr_security.py
```

This intentionally creates a uniquely named test employee and leaves the final TERMINATED employee record for audit/history. It validates overnight shifts, shift overlap rejection, self-service reads, premature close prevention, HR→Auth profile sync, suspension/reactivation, QR behavior, HR audit and termination.

## Backup / restore demonstration procedure

Backup while the application is quiescent for the cleanest demo snapshot:

```powershell
.\scripts\stop_all_services.ps1
.\.venv\Scripts\python.exe .\scripts\backup_projectx_mysql.py
```

The backup folder appears under `backups\projectx-YYYYMMDD-HHMMSS` and is ignored by Git. Keep it private.

A restore is destructive and requires services to be stopped plus the explicit phrase:

```powershell
.\.venv\Scripts\python.exe .\scripts\restore_projectx_mysql.py `
  .\backups\projectx-YYYYMMDD-HHMMSS `
  --confirm RESTORE_PROJECTX
```

The restore preflights every SQL dump before dropping the first database.

## Known, explicit limits (not hidden)

1. ProjectX has no patient↔Auth-user identity link. Appointment/payment notifications therefore require an explicit Auth recipient ID; the server does not infer one from `patient_id`.
2. BI cannot retroactively produce exact historical filters from a source service that exposes only current/all-time values. Those cases are marked PARTIAL rather than fabricated.
3. The coursework/runtime architecture uses gRPC over the trusted LAN as defined by the project baseline. Internet-facing production hardening (TLS/mTLS, secret vault, HA, external identity provider, etc.) is outside this coursework completion package.
4. Chatbot write orchestration remains intentionally conservative: sensitive clinical/financial/HR writes continue through their dedicated screens/RPCs instead of being autonomously executed by free-form chat.

## Freeze rule

After this package passes the runtime regressions, treat the final `proto/` bundle as the pre-client freeze. Give the Linux client the final handoff ZIP, regenerate stubs there, and do not invent or manually edit generated `*_pb2.py` files.
