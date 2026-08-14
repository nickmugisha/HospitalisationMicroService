# ProjectX LOT I — Maternité

Port: 50058
Database: `hospital_maternite`

Implements the MVP maternity path from the cahier des charges:
- maternity case linked to an existing Accueil patient
- pregnancy data: gravida/para, LMP, EDD, risk level/factors
- prenatal visits and basic vitals
- labor admission and traceable labor events
- delivery with mode, outcome, complications and attendant
- mother/newborn linkage with weight and Apgar
- idempotent delivery charge sent to Billing; safe pending outbox if Billing is unavailable
- Consultation -> Maternite synchronous gRPC referral on target MATERNITE
- JWT/RBAC and HealthCheck

The default delivery charge is a DEMO tariff configured by `MATERNITE_DELIVERY_CHARGE_MINOR`; it is not a real hospital tariff and can be changed in `.env`.
