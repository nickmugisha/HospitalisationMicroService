# ProjectX Global Health Compatibility Hotfix

This overlay fixes the final 11-service health validation without changing any protobuf contract or database schema.

Reason: the existing `common.proto` exposes health enum names using `SERVICE_HEALTH_STATUS_*`, while several earlier service implementations expected `HEALTH_STATUS_*` / `ONLINE`. Some services therefore returned enum value 0 (`UNSPECIFIED`), and Billing/Maternite/Rendezvous referenced enum constants that do not exist in the generated Python module.

The hotfix adds descriptor-based health compatibility, updates all 11 service HealthCheck builders, updates BI downstream health interpretation, hardens the global health test, and makes start/stop-all safe against stale/duplicate PID state.

No migration and no protobuf regeneration is required.
