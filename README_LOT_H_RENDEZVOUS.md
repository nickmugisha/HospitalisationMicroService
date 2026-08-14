# ProjectX LOT H — Rendez-vous & Agenda

Port: 50059
Database: `hospital_rendezvous`

MVP implemented:
- schedule slots by provider/service
- available slot search
- patient verification through Accueil gRPC
- appointment booking with idempotency
- double-booking protection
- confirmation, rescheduling and cancellation with event history
- daily/weekly-style agenda filtering by time window
- check-in that creates a real Accueil arrival over gRPC
- completion
- reminder is best-effort and never blocks appointment creation; if Auth notification RPC is unavailable, status is recorded as FAILED/PENDING
- Auth JWT/RBAC for all sensitive RPCs
- HealthCheck

Main tables: `schedule_slots`, `appointments`, plus `appointment_events` to preserve cancellation/reschedule history.
