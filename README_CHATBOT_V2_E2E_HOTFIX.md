# ProjectX Chatbot v2 — Full E2E Coverage Hotfix

This is a focused follow-up to the successful 12/12 ProjectX runtime and Chatbot v2 smoke test.

It fixes exactly the issues exposed by `test_chatbot_v2_full_e2e.py`:

1. Natural French HR how-to wording such as `Comment les RH corrigent une présence ?` now maps to `howto.correct_attendance`.
2. French live HR questions such as `Qui est absent aujourd'hui ?` and `Qui est en retard aujourd’hui ?` now map to `hr_dashboard`.
3. BI `GetServiceHealth` now includes the HR service on port `50062`, so the ProjectX service-health topology is 12 services instead of the legacy 11-service baseline.

No protobuf contract, database schema, migration, account, role or permission is changed.

## Apply
Extract this ZIP directly into the ProjectX repository root with `-Force`.

Then run:

```powershell
$env:PYTHONPATH="$PWD;$PWD\generated"
.\scripts\install_chatbot_v2_e2e_hotfix.ps1
```

Restart the services so BI and Chatbot load the corrected Python modules:

```powershell
.\scripts\stop_all_services.ps1
.\scripts\start_all_services.ps1
```

Verify 12/12:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_all_services_health.py
```

Then rerun the complete read-only chatbot suite:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_chatbot_v2_full_e2e.py
```

Expected final result: zero FAIL items, 13/13 live intent reads, and BI service-health topology containing all 12 services.
