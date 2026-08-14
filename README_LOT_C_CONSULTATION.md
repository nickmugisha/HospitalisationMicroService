# ProjectX LOT C - Consultation

Overlay package for the existing Windows server repository.

Implements the Consultation MVP on gRPC port 50055 with its own MySQL logical database `hospital_consultation`.

Included business flow:
- open a consultation only for an existing ACTIVE Accueil patient;
- get consultation detail and patient history;
- update clinical notes, vitals and structured diagnoses only while OPEN;
- issue a structured prescription only while OPEN;
- create laboratory and hospitalization/maternity outbound requests with correlation IDs;
- close consultation;
- reject clinical mutation after CLOSED;
- HealthCheck against MySQL;
- JWT/RBAC checks through the existing Auth service.

The `outbound_requests` table is an integration outbox owned by Consultation. It does not contain another service's business tables. LOTs for Laboratoire/Hospitalisation will wire delivery of these requests to their real gRPC services.

## Install

From `D:\skl\HospitalisationMicroService`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\install_lot_c_consultation.ps1"
```

Keep Auth on 50051 and Accueil on 50052, then start Consultation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\start_consultation.ps1"
```

Smoke test from another terminal:

```powershell
$env:PYTHONPATH="$PWD;$PWD\generated"
python .\scripts\test_consultation_grpc_smoke.py
```
