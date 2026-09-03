# ProjectX - Registration Approval + Credential/QR Login

This overlay is built against backend checkpoint `76bcde1`.

## Final account flow

1. A new user registers with `username + password + display_name`.
2. Auth creates the account as **PENDING**, inactive, with **no role and no QR**.
3. The pending user cannot log in yet.
4. An authenticated administrator lists pending users.
5. The administrator approves one user and assigns one or more real ProjectX roles.
6. Approval changes the account to **ACTIVE** and automatically issues a new QR login credential.
7. The approval response returns the raw QR payload **once** so the admin UI can render/print it for the user.
8. After approval the user may sign in using either:
   - username + password; or
   - QR scan.
9. Both login methods return the same JWT, current roles, permissions and `dashboard_route`.
10. The server still validates roles/permissions on protected RPCs. Frontend redirection is convenience, not authorization.

## Dashboard mapping returned by Auth

- `ADMIN_HOPITAL` -> `/administration`
- `AGENT_ACCUEIL` -> `/accueil`
- `RESP_HOSPITALISATION` / `INFIRMIER` -> `/hospitalisation`
- `CAISSIER` -> `/paiement`
- `MEDECIN` -> `/consultation`
- `LABORANTIN` -> `/laboratoire`
- `PHARMACIEN` / `RESPONSABLE_LOGISTIQUE` -> `/pharmacie`
- `SAGE_FEMME` -> `/maternite`
- `RESPONSABLE_BI` -> `/statistiques`

For multi-role users the backend uses a deterministic priority and always returns all roles and permissions.

## QR security model

The QR does **not** contain the password, JWT, user id or role. It contains a random 256-bit bearer credential with prefix `PROJECTX-QR1:`. Only its SHA-256 hash is stored in MySQL. The raw QR payload is returned only when issued. Issuing a new QR automatically revokes the previous one. Disabling/rejecting an account also revokes its QR.

Treat a QR like a badge/key: anyone who photographs it can try to use it until it is revoked. The admin can rotate or revoke it immediately.

## New/extended Auth RPCs

Public:
- `Register`
- `Login`
- `LoginWithQr`
- `ValidateToken`
- `GetCurrentUser`

Admin lifecycle:
- `ListPendingUsers`
- `ApproveUser` (assigns role(s) + issues QR)
- `RejectUser`
- `DisableUser`
- `CreateUser`
- `AssignRole`
- `IssueQrCredential` (rotates QR)
- `RevokeQrCredential`

Existing notification and `HealthCheck` RPCs remain in the contract.

## Installation on the Windows server

First stop running ProjectX services so Auth files and generated code are not in use.

From `D:\skl\HospitalisationMicroService`, extract this ZIP **into the project root**, allowing the listed files to overwrite the old versions. Then run:

```powershell
$env:PYTHONPATH="$PWD;$PWD\generated"
.\scripts\install_qr_auth_approval.ps1
```

Start the services again:

```powershell
.\scripts\start_all_services.ps1
```

Then run the end-to-end Auth smoke test:

```powershell
$env:PYTHONPATH="$PWD;$PWD\generated"
.\.venv\Scripts\python.exe .\scripts\test_auth_qr_approval_smoke.py
```

The test asks for the existing admin credentials without storing them in source code.

## Client / Linux gateway integration

Regenerate the Python Auth client from the exact updated `proto/auth/v1/auth.proto` copied from the server contract. Do not invent a separate Auth proto on the client.

The login page should present two choices:

- **Sign in with credentials** -> gateway calls `AuthService.Login`.
- **Scan QR code** -> browser camera/scanner reads the complete QR string and gateway calls `AuthService.LoginWithQr`.

On success, store/use the returned access token exactly as normal credential login and route to `dashboard_route`. Protected routes must still check `user.roles`/permissions.

The admin UI should have a Pending Accounts page that calls `ListPendingUsers`. Its Approve action selects the role(s), calls `ApproveUser`, then immediately renders `qr_payload` as a QR image and offers Print/Save for secure handoff. The backend intentionally does not create image files because the QR image is a presentation concern; the credential is the returned payload.

## Important compatibility point

The original password login remains supported. Existing users are migrated to ACTIVE/DISABLED based on their current `active` flag, so the migration does not turn existing working accounts into pending accounts.
