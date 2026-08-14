# ProjectX LOT E — Pharmacie / Stock / Logistique

Port: 50057
Database: `hospital_pharmacie`

Included MVP:
- medicine catalog, prices and active status;
- stock entries by batch with expiry date;
- FEFO dispensing with row locks and atomic stock movements;
- rejection of insufficient or expired stock;
- prescription exposure from Consultation to Pharmacy;
- partial/complete prescription status;
- idempotent dispensing;
- low/out/expiring/expired stock alerts;
- suppliers and simple purchase-order receiving;
- billing outbox for the future Billing service;
- HealthCheck and JWT/RBAC checks through Auth.

The overlay also patches `services/consultation/config.py` and `services/consultation/service.py` so newly issued prescriptions are exposed to Pharmacy by gRPC when port 50057 is online. If Pharmacy is unavailable, the clinical prescription remains saved and the Consultation outbox remains pending.
