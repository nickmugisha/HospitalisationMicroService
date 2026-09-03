# ProjectX Backend Completion v3 — Final Write/Security E2E

Test-only overlay. It does not replace services, protos, migrations, RBAC or configuration.

The test uses uniquely prefixed `PXV3` fixtures and exercises the remaining write/security paths that the read-only regression cannot prove:

- internal notification RPC rejects user JWTs;
- HR creates a test doctor, Admin approves MEDECIN, Hospitalisation discovers the doctor;
- ward/room/bed creation and bed out-of-service/available transitions;
- two simultaneous test admissions assigned to the same doctor, including the intended busy warning;
- doctor assignment notification delivered through the private service-to-service notification route;
- doctor workload returns to zero after completion;
- test admissions are discharged and the test ward is disabled;
- appointment slot update, reminder scheduling, cancellation/blocking, and positive NO_SHOW after a short real-time slot;
- isolated pharmacy medicine/supplier creation/update, expired receipt guard, successful PO receipt, stock verification, and fixture deactivation;
- maternity premature-close guard, labor, delivery, newborn, and terminal close;
- test doctor is terminated after the run.

The test intentionally preserves audit/history rows. It does not hard-delete hospital data. Test patients and terminal records remain recognizable by their `PXV3` names/codes.

## Run

```powershell
cd "D:\skl\HospitalisationMicroService"
$env:PYTHONPATH="$PWD;$PWD\generated"
.\.venv\Scripts\python.exe .\scripts\test_backend_completion_v3_write_e2e.py
```

Expected final line:

```text
PROJECTX BACKEND COMPLETION V3 FINAL WRITE/SECURITY E2E: PASS
```
