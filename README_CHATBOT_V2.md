# ProjectX Chatbot v2 — Context-aware bilingual hospital assistant

This overlay upgrades the existing deterministic Chatbot service on **port 50061**. It is designed for the current ProjectX architecture with the HR v2.2 extension on port 50062.

## What changes

### 1. Login-page public assistant

Two deliberately public RPCs are added:

- `GetPublicWelcome`
- `AskPublicAssistant`

They require **no JWT**, but they are intentionally isolated from hospital data. They never call Accueil, Consultation, Laboratory, Pharmacy, Hospitalisation, Billing, Maternity, Rendez-vous, BI, HR, or notification data.

The public assistant can explain login, QR login, account approval and basic ProjectX usage. Sensitive questions receive a privacy boundary response asking the user to sign in.

A small in-process per-peer rate limit protects the public endpoint from obvious flooding.

### 2. Name-aware greeting after login

`StartSession` now returns:

- `welcome_message`
- `language`
- `suggested_questions`
- `mode`

The welcome message uses `staff_profile.first_name`, then `display_name`, then `username` as fallback. The name comes from the Auth-validated user, not from React.

### 3. English + French

The assistant detects English/French from the question and accepts a locale hint (`en`, `en-US`, `fr`, `fr-BI`, etc.). Users may switch language between messages.

### 4. Current dashboard/module context

`AssistantContext` can carry:

- current module/route
- active patient id/number
- consultation/admission/invoice/employee identifiers
- locale

These values help understand the question but **never grant permission**. JWT + server RBAC remain authoritative.

### 5. ProjectX procedural knowledge

The deterministic knowledge layer explains real workflows in Auth, HR, Accueil, Consultation, Laboratory, Pharmacy, Hospitalisation, Billing, Maternity, Rendez-vous and BI.

Examples:

- `How do I register a patient?`
- `Comment enregistrer un patient ?`
- `How do I collect a lab sample?`
- `Comment effectuer un reversal de paiement ?`
- `How do I clock in?`
- `Comment clôturer les présences ?`

Each procedure has the exact backend permission and canonical role(s). The assistant says whether the current authenticated account has the required permission.

### 6. Permission-safe live reads

Existing live reads are preserved and expanded. Chatbot v2 can perform authorized reads for:

- patient identity/search — Accueil
- bed availability — Hospitalisation
- medicine stock / stock alerts — Pharmacie
- appointment agenda — Rendez-vous
- patient balance — Billing
- consultation history — Consultation
- laboratory-result history — Laboratoire
- maternity record summary — Maternité
- HR attendance dashboard — HR
- own notifications — Auth
- hospital KPI / service health — BI

Every downstream request propagates the same Bearer token. Before any live call, Chatbot checks the required permission; the downstream service checks it again.

### 7. Sensitive writes are not auto-executed

Chatbot v2 can explain write workflows but does not silently execute clinical, financial, HR, pharmacy, or administrative writes. This prevents a conversational misunderstanding from becoming a real hospital action. Write-action orchestration can be added later with explicit confirmation, idempotency and audit per RPC.

## Installation order

This overlay expects the latest ProjectX HR/QR/Attendance v2.2 extension to already be extracted because Chatbot v2 imports the HR gRPC client.

From the ProjectX root:

```powershell
$env:PYTHONPATH="$PWD;$PWD\generated"
.\scripts\install_chatbot_v2.ps1
```

Then restart Chatbot or all ProjectX services and run:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_chatbot_v2_smoke.py
```

Do not paste the admin password into chat or logs.

## Client synchronization

The Linux client must receive the updated:

```text
proto/chatbot/v1/chatbot.proto
```

and regenerate its gRPC stubs. Do not manually edit `*_pb2.py` or `*_pb2_grpc.py`.
