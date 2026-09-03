# ProjectX — Cahier v2.0 Completion Matrix + ProjectX Extensions

Date: 2026-08-15  
Status: **Backend Completion v3 pre-client freeze candidate**. This document distinguishes the official 11-service cahier baseline from later ProjectX extensions agreed by the team.

## A. Official v2.0 baseline

| Cahier area | Server status at v3 | Evidence / notes |
|---|---|---|
| Accueil | Implemented and preserved | Patient create/search/update, arrival/orientation/queue. Existing validated contract is unchanged by v3. |
| Hospitalisation | Completed for client administration | Admission, approval with reason, ward/room/bed administration, availability, assign/transfer/discharge, stay notes, history reads. V3 adds registered doctor directory/workload and assignment lifecycle. |
| Paiement & facturation | Implemented and preserved | Charges, invoice/balance, payment, receipt, reversal, idempotency/overpay guards. V3 adds optional explicit Auth recipient for payment/reversal notifications. |
| Consultation | Implemented and preserved | Consultation, diagnosis, prescription, lab/hospitalisation requests, close/immutability guard. Existing contract unchanged. |
| Laboratoire | Completed for frontend selection | Orders, sample, results, validation/history plus v3 `ListLabTests`/`GetLabTest` so doctors select valid catalogue test codes. |
| Pharmacie / stock / logistique | Completed for frontend workflow | Catalogue discovery, medicine admin, stock/batches/FEFO, stock alerts, prescription inbox, dispensing, supplier/PO create/read/update/receive. |
| Maternité | Completed MVP + client discovery | Pregnancy/prenatal/labour/delivery/newborn flows plus case list/search and close-after-delivery. |
| Rendez-vous & agenda | Completed MVP + scheduled reminders | Slot create/list/update/block, appointment create/read/history/confirm/reschedule/cancel/check-in/complete/no-show; reminder worker retries until appointment time. |
| Authentification & notification | Implemented + hardened service-to-service notification path | JWT/RBAC, account approval, QR, notifications, staff directory. Internal notification RPCs require private service token and are not client operations. |
| BI & statistique | Implemented with truthful quality semantics | 12-service health, KPI/dashboard, service filter. Historical filtering is exact only where source RPCs expose period data; otherwise response is marked PARTIAL/warned rather than fabricated. |
| Chatbot avancé | Validated before v3 and protected from regression | Public-safe + authenticated bilingual assistant; role/context aware; 13 live-data intents. V3 installer reruns its deterministic regression. |

## B. ProjectX extensions agreed after the original cahier

These are **not claimed as original v2.0 requirements**.

| Extension | v3 server behavior |
|---|---|
| HR service on 50062 | Employee records, employment state, shifts, attendance, leave, audit, dashboard. |
| No public staff signup | HR requests staff identity; Auth creates PENDING_APPROVAL/inactive/no business role; Admin assigns role(s) and approves. |
| Password + QR authentication | Approved user may authenticate with credential or personal QR; both resolve current Auth/RBAC. Revoked QR is rejected. |
| HR lifecycle ↔ Auth | SUSPENDED/INACTIVE/TERMINATED block Auth access; TERMINATED revokes QR; HR profile changes synchronize professional Auth profile. |
| Explicit attendance | Login is never attendance. Employee Clock In/Clock Out records server time. HR may correct/manual-record only through controlled/audited RPCs. |
| Overnight shifts | End time <= start time is treated as next-day overnight; overlap checks span midnight. |
| HR self-service | Staff can read own attendance, shifts and leave; can cancel only own pending leave request. |
| Hospitalisation doctor assignment | Admin/hospitalisation staff chooses an active registered MEDECIN. Active workload creates a warning, not a prohibition. One active doctor assignment per admission is DB-protected. |
| Registered hospital structure | Authorized admin/hospitalisation role creates/updates wards, rooms and beds; occupied/inactive safeguards prevent unsafe transitions. |

## C. Non-functional / final-demo requirements

| Requirement | v3 preparation |
|---|---|
| gRPC contracts are source of truth | Existing proto field numbers/signatures preserved; v3 additions are additive. Final client handoff bundles exact protos + SHA256. |
| Server-side RBAC | New operations have explicit permissions; internal notifications use a separate service credential. |
| Service isolation | No new cross-service SQL access; HR/Auth, Lab/Auth, Pharmacy/Auth, Billing/Auth, Maternity/Auth and Rendezvous/Auth integration uses gRPC. |
| Deadlines/failure isolation | Existing architecture retained; notification failures are secondary and must not turn a successful clinical/financial write into fake failure. |
| No client MySQL | Unchanged. Linux client uses local FastAPI → gRPC only. |
| Backup/restore before demo | v3 includes 12-database backup and destructive restore with full preflight + explicit confirmation. |
| Offline behavior | Must be proven during final Linux↔Windows integration by stopping one secondary service and verifying UNAVAILABLE/OFFLINE without global crash. |
| Real two-PC scenario | Still required after Windows v3 runtime regression: Linux React/FastAPI must call current Windows LAN IP, not localhost. |
| Reproducible tests | v3 includes contract/static checks, read-only live regression and HR security regression; existing HR and Chatbot regression suites remain mandatory. |

## D. Freeze gate

The backend contract can be promoted from **freeze candidate** to **frozen for client integration** only after the Windows machine reports:

1. safe installer PASS;
2. 12/12 global health PASS;
3. v3 read-only live regression PASS;
4. existing HR/Auth/QR/Attendance smoke PASS;
5. existing Chatbot v2 full E2E PASS;
6. optional/deeper v3 HR security regression PASS before final presentation;
7. then the Linux machine copies the exact final proto bundle, regenerates stubs and performs real cross-PC workflows.
