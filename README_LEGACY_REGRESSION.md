# ProjectX v3 — Legacy Business Regression Runner

Test-only package. It does not replace any service, proto, migration, RBAC or configuration file.

It prompts once for an existing administrator username/password locally and re-runs the original smoke scripts for Accueil, Consultation, Laboratoire, Pharmacie, Hospitalisation, Billing, Rendez-vous, Maternité and BI. The password is kept only in process memory and is not printed or written to disk.

The existing smoke tests create demonstration/test business records. Run this only on the ProjectX coursework/demo database, not on a real production hospital database.

Expected final line:

`PROJECTX V3 LEGACY BUSINESS REGRESSION: PASS`
