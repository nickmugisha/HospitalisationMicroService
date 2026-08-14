# ProjectX — LOT B Accueil

This ZIP is an **overlay** for the existing Windows server project at:

`D:\skl\HospitalisationMicroService`

It does not replace the working Auth service. It adds Accueil on port **50052**, with its own MySQL logical database `hospital_accueil` and an independent Alembic migration.

## Included backend

- `CreatePatient`
- `GetPatient`
- `SearchPatients`
- `UpdatePatient`
- `RegisterArrival`
- `OrientArrival`
- `ListWaitingQueue`
- `HealthCheck`
- generated patient numbers such as `PAT-YYYYMMDD-XXXXXXXX`
- obvious duplicate-patient rejection
- JWT/RBAC checks through Auth `ValidateToken`
- server-side permissions using the already seeded Accueil permissions
- MySQL persistence in `patients` and `arrivals`
- structured service logs

## Install after extracting into the project root

From PowerShell in `D:\skl\HospitalisationMicroService`:

```powershell
.\.venv\Scripts\Activate.ps1
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_lot_b_accueil.ps1
```

The installer:

1. appends only non-secret Accueil settings to `.env` if missing;
2. generates Accueil protobuf Python stubs;
3. creates `hospital_accueil` and grants the existing `projectx_auth@127.0.0.1` user access;
4. runs the independent Accueil Alembic migration;
5. verifies imports and tables.

## Start

Keep Auth running on `50051`, then in another terminal:

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="$PWD;$PWD\generated"
.\scripts\start_accueil.ps1
```

Expected server line:

`PROJECTX AccueilService started on 0.0.0.0:50052`

## Smoke test

With Auth and Accueil both running:

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="$PWD;$PWD\generated"
python .\scripts\test_accueil_grpc_smoke.py
```

The test asks for the existing admin username/password, obtains a JWT without printing it, creates a unique test patient, searches that patient, registers an arrival, and verifies the waiting queue.

## Client integration later

The Linux client will compile the same `proto/accueil/v1/accueil.proto` and call the Windows host on port `50052`. Protected requests must forward metadata:

`authorization: Bearer <JWT>`

The client must not access MySQL directly.
