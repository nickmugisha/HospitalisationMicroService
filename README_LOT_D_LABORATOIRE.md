# ProjectX LOT D — Laboratoire

Adds the Laboratory gRPC service on port 50056 with MySQL `hospital_laboratoire`.

Implemented MVP:
- minimal seeded lab-test catalog and BIF prices;
- Consultation -> Laboratoire synchronous delivery with correlation ID and consultation outbox fallback;
- lab order queue;
- sample collection with operator trace;
- structured/text results;
- validation and protection against silent overwrite;
- audited correction path when `correction_reason` is explicitly supplied;
- patient result history;
- idempotent billing outbox created on validation for later LOT Billing integration;
- HealthCheck.

After extraction run `scripts/install_lot_d_laboratoire.ps1`, restart Consultation, start Laboratoire, then run the smoke test.
