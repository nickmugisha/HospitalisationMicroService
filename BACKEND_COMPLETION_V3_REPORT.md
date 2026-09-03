# ProjectX Backend Completion v3 — engineering report

Date: 2026-08-15

## Baseline protected

The input baseline for this completion is the already validated Windows server state:
- 12 gRPC services online (50051–50062);
- HR/Auth/QR/Attendance v2.2 smoke test passed;
- Chatbot v2 full E2E passed 60/60 with 13/13 live-data intents;
- BI service-health topology includes all 12 services.

This v3 package is additive. It intentionally does not rewrite Accueil/Consultation core business behavior and does not renumber or change signatures of existing proto fields/RPCs.

## Completion matrix

| Gap | v3 result |
|---|---|
| Doctor needs valid lab test codes | Lab catalogue read RPCs added |
| Doctor needs valid medicine refs | Safe medicine catalogue permission/path added |
| Pharmacist needs discoverable prescriptions | Pharmacy prescription inbox list/get added |
| Pharmacy admin/logistics reads | Medicine, supplier and PO read/manage contracts completed |
| Hospital structure administration | Ward/room/bed create/update/status/list added with occupancy/inactive safeguards |
| Admission approval | Explicit approval timestamp/user/reason added |
| Doctor assignment | Directory/workload, busy warning, assign/list/complete added; concurrent duplicate active assignment guarded in DB |
| HR overnight shifts | Supported, including overlap detection across midnight |
| Employee HR self-service reads | Attendance/shift/leave reads + pending leave cancellation added |
| HR lifecycle security | Employment status and profile synchronize to Auth; termination revokes QR |
| HR audit visibility | ListHrAuditLogs added |
| Premature absence/finalization | Finalization waits for scheduled shift end; dashboard exposes not-started count |
| Lab/payment/stock/maternity notifications | Internal notification paths added; main operations remain successful if secondary notification fails |
| Appointment reminders | Timed worker + retries + reschedule + NO_SHOW + slot update/block added |
| BI 12-service awareness | HR included; service filter added |
| BI historical truthfulness | Unsupported source-history periods marked PARTIAL rather than fabricated |
| DB demo safety | 12-DB backup and preflighted destructive restore scripts added |

## Static engineering verification performed before packaging

- All changed Python files compile with Python `compileall` in the artifact environment.
- Existing proto messages/RPC signatures were compared with the validated pre-v3 proto tree: no existing field number/type/name or RPC signature was removed/changed.
- Proto blocks were checked for duplicate message field numbers/names.
- Every RPC declared by the changed Auth, Hospitalisation, Billing, Laboratoire, Pharmacie, Maternité, Rendez-vous and HR contracts has a corresponding Python service method (Auth HealthCheck is supplied by RuntimeAuthService).
- `HasField()` usages were audited against message/optional scalar presence; new proto3 scalar presence is explicitly declared where required.
- Hospitalisation doctor assignment now has a nullable unique active-admission DB key and clears it on completion/discharge.
- Restore logic preflights all dumps before dropping any database.
- Secret-like runtime values are not bundled; only example placeholders are allowed.

## Runtime verification still required on the user's Windows machine

The artifact environment does not contain the user's MySQL instance, Windows PowerShell, `.venv` grpc-tools, or live service data. Therefore the v3 package must not be called runtime-validated until the safe installer and the provided regression sequence pass on `D:\skl\HospitalisationMicroService`.

Required post-install checkpoints:
1. installer finishes `PROJECTX BACKEND COMPLETION V3 INSTALLATION: PASS`;
2. global health remains 12/12;
3. `test_backend_completion_v3_readonly.py` passes;
4. existing `test_hr_extension_smoke.py` still passes;
5. existing `test_chatbot_v2_full_e2e.py` still passes;
6. optional write/security regression `test_backend_completion_v3_hr_security.py` passes.

Only after those checks should the final proto bundle be treated as frozen for Linux client integration.
