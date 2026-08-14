# ProjectX LOT F — Hospitalisation

Overlay for the existing Windows ProjectX server.

Implements:
- gRPC service on port 50053
- hospital_hospitalisation MySQL schema
- wards, rooms, beds
- bed availability
- admission creation with patient validation through Accueil
- admission idempotency / active-patient uniqueness
- atomic bed assignment with double-occupation protection
- transfer history
- stay notes
- discharge + bed release
- pending Billing outbox for stay charge
- Consultation -> Hospitalisation gRPC bridge
- HealthCheck

Install with `scripts/install_lot_f_hospitalisation.ps1`, start Hospitalisation, restart Consultation, then run `scripts/test_hospitalisation_grpc_smoke.py`.
