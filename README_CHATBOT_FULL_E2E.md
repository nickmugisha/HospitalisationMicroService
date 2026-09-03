# ProjectX Chatbot v2 — Full E2E Verification Suite

This package is deliberately **test-only**. It does not replace Chatbot, Auth, HR, BI, any `.proto`, or any business-service file.

## What it verifies

- Public assistant English/French welcome and greeting.
- Public login/QR procedural guidance.
- Public privacy boundary for patient, financial, lab, HR and maternity requests.
- Authenticated Chatbot rejects missing JWT.
- Existing admin credential login.
- Greeting by the logged-in user's name.
- Identity awareness and current-module context awareness.
- Representative bilingual ProjectX how-to guidance.
- Every current Chatbot v2 live-read intent:
  - `service_health` → BI
  - `kpi` → BI
  - `beds` → Hospitalisation
  - `patient` → Accueil
  - `stock` → Pharmacie
  - `stock_alerts` → Pharmacie
  - `agenda` → Rendez-vous
  - `payment` → Billing
  - `consultations` → Consultation
  - `lab_results` → Laboratoire
  - `maternity_record` → Maternité
  - `hr_dashboard` → HR
  - `notifications` → Auth
- Chat history persistence.
- Test-session cleanup.

## Safety

The suite does **not** create/update/delete patients, payments, admissions, stock, appointments, maternity records, attendance, leave, employees, roles or users.

It performs only read RPCs against the métier services. The Chatbot naturally writes its own conversation/tool-call history while being tested; the suite calls `ClearSession` at the end to remove those test messages/tool calls.

The test discovers existing patients and medicine data. For Maternity, it searches existing patients and probes `GetMaternityRecord` read-only until it finds an existing maternity case. If a fixture does not exist, the suite reports a warning instead of polluting the hospital database just to create test data.

## Install

Extract this ZIP into the ProjectX project root. It adds only:

```text
scripts/test_chatbot_v2_full_e2e.py
README_CHATBOT_FULL_E2E.md
```

No restart is required.

## Run

From PowerShell:

```powershell
cd "D:\skl\HospitalisationMicroService"
$env:PYTHONPATH="$PWD;$PWD\generated"
.\.venv\Scripts\python.exe .\scripts\test_chatbot_v2_full_e2e.py
```

Enter the existing administrator username/password when prompted. Do not paste the password into chat.

## Interpreting the verdict

Best possible result:

```text
Live intent successful reads: 13/13
PROJECTX CHATBOT V2 FULL E2E LIVE COVERAGE: PASS
```

If there are no existing data fixtures (for example no maternity record yet), the suite can report:

```text
PROJECTX CHATBOT V2 ROUTING/SAFETY: PASS
PROJECTX CHATBOT V2 FULL LIVE COVERAGE: PARTIAL
```

That means the Chatbot routed safely, but a successful real-data response could not be proven for every intent using the data currently stored.

## Important architecture note discovered during audit

The global ProjectX health script already checks all 12 services. However, the current BI `GetServiceHealth` implementation was originally written for the 11-service baseline and should be checked specifically for whether it includes the new HR service (`50062`). This verification suite deliberately exercises the Chatbot's `service_health` intent so the actual runtime behavior is visible before any BI code is changed.
