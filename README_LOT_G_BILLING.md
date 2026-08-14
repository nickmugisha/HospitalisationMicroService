# ProjectX LOT G — Paiement & Facturation

Overlay for the existing `D:\skl\HospitalisationMicroService` backend.

## Scope

- gRPC Billing service on port 50054.
- MySQL logical database `hospital_billing`.
- Idempotent charges by source and idempotency key.
- One consolidated running invoice per patient for the MVP.
- Partial payments with explicit BIF integer minor amounts (no floats).
- Unique reprintable receipt per payment.
- Full payment reversal without deleting or mutating the original financial amount.
- Payment/balance/status queries.
- Patches Laboratoire, Pharmacie and Hospitalisation so new billable events attempt real gRPC `CreateCharge` delivery to Billing. If Billing is unavailable, the already-committed local action remains and its outbox stays `PENDING_DELIVERY`.
- Adds `billing.charge.create` to RBAC and assigns it to the clinical/source roles that generate charges.

## Start order after installation

1. Auth :50051
2. Accueil :50052
3. Consultation :50055
4. Billing :50054
5. Laboratoire :50056 (restart)
6. Pharmacie :50057 (restart)
7. Hospitalisation :50053 (restart)

Run `scripts/test_billing_grpc_smoke.py` after Billing is online.
