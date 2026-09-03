# ProjectX HR v2.2 — HR-controlled attendance

This overlay supersedes v2.1. It preserves the hospital onboarding/QR logic and strengthens Service 12 (HR) so attendance is owned by `RESPONSABLE_RH`.

## Attendance authority
- Employees may clock in/out only for themselves.
- HR schedules shifts and can record attendance manually.
- HR corrects records with a mandatory reason.
- HR finalizes a work day; scheduled staff without attendance become ABSENT, or EXCUSED when approved leave covers the day.
- HR can obtain per-employee and period summaries including late/worked minutes.
- Every HR write is audited.

## New RPCs
- `RecordAttendanceByHR`
- `FinalizeAttendanceDay`
- `GetAttendanceSummary`

## New migration
`hr_0002_hr_controlled_attendance.py` adds source, late/worked minutes and HR validation metadata.

Install with the existing `scripts/install_hr_extension_v2_1.ps1`; it runs `alembic upgrade head` and therefore applies both `hr_0001` and `hr_0002`.
