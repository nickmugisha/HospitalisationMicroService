# ProjectX — Service Registry & Backend Completion v3

**Current architecture:** ProjectX Backend Completion v3 (official v2.0 hospital baseline + HR/QR/attendance extension + contract-completeness additions)  
**Official cahier baseline:** v2.0, 11 gRPC microservices.  
**ProjectX extension:** HR is service 12 on port 50062. The HR service and QR/approval additions are project extensions and must not be represented as original cahier v2.0 content.

## Locked architecture rules

1. Linux client: React + TypeScript → local FastAPI gateway → generated Python gRPC stubs.
2. Windows server: independently startable Python gRPC services → SQLAlchemy/Alembic → MySQL.
3. The Linux client never connects to MySQL.
4. A service never reads/writes another service's SQL tables directly; cross-service actions use gRPC and business IDs.
5. Auth is authoritative for account state, JWT, roles, permissions, QR credentials and notifications.
6. HR is authoritative for employment, shifts, attendance and leave.
7. UI role hiding is UX only; every protected operation is checked server-side.
8. Interservice notifications use the private `x-projectx-service-token`; that value is generated locally in `.env` and is never sent to the client.

## Canonical roles

`ADMIN_HOPITAL`, `RESPONSABLE_RH`, `AGENT_ACCUEIL`, `MEDECIN`, `INFIRMIER`, `RESP_HOSPITALISATION`, `LABORANTIN`, `PHARMACIEN`, `CAISSIER`, `SAGE_FEMME`, `RESPONSABLE_LOGISTIQUE`, `RESPONSABLE_BI`.

## Services

| # | Service | Port | Database | Contract | Current responsibility |
|---|---|---:|---|---|---|
| 01 | Accueil | 50052 | `hospital_accueil` | `proto/accueil/v1/accueil.proto` | Patient identity, arrivals, orientation, queue |
| 02 | Hospitalisation | 50053 | `hospital_hospitalisation` | `proto/hospitalisation/v1/hospitalisation.proto` | Admission approval, wards/rooms/beds, doctor assignment/workload, transfers, stay, discharge |
| 03 | Billing | 50054 | `hospital_billing` | `proto/billing/v1/billing.proto` | Charges, invoices, payments, receipts, reversals, optional payment notification recipient |
| 04 | Consultation | 50055 | `hospital_consultation` | `proto/consultation/v1/consultation.proto` | Clinical consultation, diagnosis, prescriptions, lab/hospitalisation requests |
| 05 | Laboratoire | 50056 | `hospital_laboratoire` | `proto/laboratoire/v1/laboratoire.proto` | Test catalogue, orders, samples, results, validation, result notification |
| 06 | Pharmacie / Stock | 50057 | `hospital_pharmacie` | `proto/pharmacie/v1/pharmacie.proto` | Medicine catalogue, prescription inbox, FEFO stock, dispensing, alerts, suppliers and POs |
| 07 | Maternité | 50058 | `hospital_maternite` | `proto/maternite/v1/maternite.proto` | Pregnancy/prenatal/labour/delivery/newborn, case list/close, relevant notifications |
| 08 | Rendez-vous | 50059 | `hospital_rendezvous` | `proto/rendezvous/v1/rendezvous.proto` | Slots, slot update/block, appointments, patient history, check-in, no-show, timed reminders |
| 09 | Auth & Notifications | 50051 | `hospital_auth` | `proto/auth/v1/auth.proto` | Accounts, approval, RBAC, JWT, QR, limited staff directory, notification/audit authority |
| 10 | BI & Statistique | 50060 | `hospital_bi` | `proto/bi/v1/bi.proto` | Consolidated KPI, service filter, truthful data-quality flags, health for all 12 services |
| 11 | Chatbot v2 | 50061 | `hospital_chatbot` | `proto/chatbot/v1/chatbot.proto` | Public-safe + authenticated bilingual role/context-aware assistant, permission-safe live reads |
| 12 | Ressources Humaines | 50062 | `hospital_hr` | `proto/hr/v1/hr.proto` | Employees, overnight shifts, attendance, leave, self-service reads, HR audit, Auth lifecycle sync |

## Completed pre-client gaps in v3

- Laboratory exposes `ListLabTests` and `GetLabTest` so clinical forms can discover valid `test_code` values.
- Doctors can use the safe Pharmacy medicine catalogue permission without receiving stock-management rights.
- Pharmacy exposes a prescription inbox plus medicine/supplier/purchase-order management/read contracts.
- Hospitalisation exposes ward/room/bed administration and protects inactive/occupied structures.
- Hospitalisation supports admission approval with reason, doctor directory/workload, assignment, busy warning, completion and one-active-doctor-per-admission concurrency protection.
- HR supports overnight shifts, overlap protection, shift update, own attendance/shift/leave reads, leave cancellation, audit reads, premature-close protection, HR→Auth profile/status synchronization.
- Suspended/inactive/terminated employees are blocked in Auth; termination revokes QR. Reactivation does not override an Admin-disabled/pending/rejected identity.
- Lab result, payment (when an Auth recipient is supplied), stock alerts, maternity events and appointment reminders can create Auth notifications without granting business services a user-level notification permission.
- Rendez-vous reminders are scheduled/retried by the server; rescheduling schedules a fresh reminder. Because ProjectX has no patient→Auth identity mapping, the caller must explicitly provide `reminder_recipient_user_id` when requesting a reminder.
- BI now includes HR in service health and applies `service` filtering. Date filtering is exact where the source contract supports it (notably Rendez-vous); otherwise BI marks the result PARTIAL instead of inventing historical precision.
- Backup/restore scripts cover all 12 MySQL logical databases and restore preflights every dump before destructive work.

## HR/Auth/QR lifecycle

HR registers employee → Auth creates `PENDING_APPROVAL` inactive identity → Admin assigns business role(s) and approves → QR issued → password/QR login issue the same JWT/RBAC view. HR cannot approve roles. HR suspension/inactivity disables Auth access; termination also revokes QR. HR reactivation only re-enables an identity that remains Admin-approved and has roles.

## Attendance control model

Employees explicitly Clock In/Clock Out; login time is not attendance. HR schedules shifts, may correct/manual-record with reason, reviews attendance, and finalizes a day only after all scheduled shifts have ended. Overnight shifts such as 20:00→08:00 are supported. One attendance row per employee/work date remains enforced. Staff can read their own shifts/attendance/leave and cancel only their own pending leave request.

## Integration boundary

The final client must receive the exact final `proto/` bundle, regenerate stubs, centralize `GRPC_SERVER_HOST`, use ports 50051–50062, propagate Bearer JWT + correlation/idempotency metadata as required, and map gRPC errors without duplicating server business rules.
