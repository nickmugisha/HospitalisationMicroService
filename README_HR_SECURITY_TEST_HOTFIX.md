# ProjectX Backend Completion v3 — HR security regression test hotfix

Test-only patch. It does not modify services, protobuf contracts, migrations, RBAC, or database schemas.

Fixes a regression-test expectation error:
- future attendance date => `INVALID_ARGUMENT` (valid request validation)
- current attendance date while a scheduled shift has not ended => `FAILED_PRECONDITION` (business-state guard)

The test now verifies both branches separately.

It also performs best-effort cleanup of abandoned `PXV3-*` regression employees/shifts from earlier failed runs, and cleanup on later test failure. Historical HR employee/audit records are preserved by terminating test employees rather than deleting them.
