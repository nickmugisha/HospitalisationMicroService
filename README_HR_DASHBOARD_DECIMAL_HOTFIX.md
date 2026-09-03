# ProjectX HR Dashboard Decimal Hotfix

## Symptom
`GetHrDashboard` could fail on MySQL with:

`'decimal.Decimal' object cannot be interpreted as an integer`

## Cause
MySQL/SQLAlchemy may return `Decimal` for `SUM(...)`. Protobuf `int64` fields require native Python integers.

## Fix
Normalize SQL aggregate/count values to Python `int` before building protobuf responses. This patch also normalizes pagination totals for consistency.

## Scope
- `services/hr/service.py`
- one non-destructive local check script

No `.proto` change. No migration. No database mutation. No permission/RBAC change.

## Validate
1. `python .\scripts\check_hr_dashboard_numeric_hotfix.py`
2. Restart services (HR must reload).
3. `python .\scripts\test_all_services_health.py`
4. `python .\scripts\test_hr_extension_smoke.py`

The HR smoke test should now reach and pass `[OK] HR dashboard` and finish successfully.
