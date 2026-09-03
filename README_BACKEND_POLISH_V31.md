# ProjectX Backend Polish v3.1

## Auth contract

### Login
Preferred new request:

```json
{
  "identifier": "jean.postman@projectx.test",
  "password": "..."
}
```

or:

```json
{
  "identifier": "jean.postman",
  "password": "..."
}
```

Legacy `username` + `password` remains supported.

### ChangeMyPassword
Bearer JWT required.

```json
{
  "current_password": "...",
  "new_password": "..."
}
```

Success invalidates pre-change JWTs via `users.auth_version`. Re-login is required. QR credentials are independent and remain governed by `IssueQrCredential` / `RevokeQrCredential`.

### UpdateMyProfile
Bearer JWT required. Only `email` and `phone` are self-service. Omitted field = unchanged; empty string = clear.

```json
{
  "email": "new.address@hospital.test",
  "phone": "+257..."
}
```

HR/Admin retain authority over employee number, legal staff identity fields, department, job title, employment status and roles.

## Prescription contract

### Hospital catalogue line

```json
{
  "medicine_ref": "AMOXICILLIN-500MG",
  "medicine_source": "PRESCRIPTION_MEDICINE_SOURCE_HOSPITAL_CATALOG",
  "dose": "500 mg",
  "frequency": "3 times/day",
  "duration": "7 days",
  "instructions": "After meals"
}
```

The doctor has catalogue read permission but no catalogue/stock management permission. The server snapshots medicine identity details.

### External medicine line

```json
{
  "medicine_source": "PRESCRIPTION_MEDICINE_SOURCE_EXTERNAL",
  "medicine_name": "External Brand Medicine",
  "medicine_form": "Tablet",
  "medicine_strength": "10 mg",
  "dose": "10 mg",
  "frequency": "1 time/day",
  "duration": "5 days",
  "instructions": "Take at night"
}
```

No hospital catalogue reference is required. The backend generates an internal `EXT-...` reference for traceability. Pharmacy receives the line with `dispensable_by_hospital=false` and cannot deduct hospital stock for it.

## Client printable ordonnance

Client/gateway renders the PDF from authoritative server data. Recommended data composition:
- Consultation prescription + line snapshots from Consultation
- Patient identity from Accueil
- Doctor professional identity from Auth staff directory

The PDF is presentation; prescription validity/business state remains on the server.
