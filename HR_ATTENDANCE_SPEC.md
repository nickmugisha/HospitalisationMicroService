# ProjectX HR Attendance System — v2.2

## Ownership
Attendance belongs to **Service 12 — Ressources Humaines (port 50062)**. A separate attendance microservice is intentionally not added because attendance, shifts, leave and employee employment status form one HR bounded context. Auth remains the identity/RBAC source; HR owns workforce attendance data.

## Authority model
- `RESPONSABLE_RH` controls schedules, attendance records, corrections, validation, day closing and attendance reports.
- Regular hospital employees can only send their own `ClockIn` and `ClockOut` events.
- An employee cannot list all attendance, edit times, mark themselves absent/excused, validate attendance or close a work day.
- `ADMIN_HOPITAL` retains global administrative permissions but normal attendance operations belong to HR.

## Daily workflow
1. HR creates shifts for employees.
2. Employee clocks in. The service determines `PRESENT` or `LATE` using the shift start and configured grace period.
3. Employee clocks out. Worked minutes are calculated.
4. HR monitors the live attendance dashboard.
5. HR may manually record or correct a record, always with an audit reason.
6. HR finalizes the day. A scheduled employee with no attendance becomes `ABSENT`; if an approved leave covers the day, the record becomes `EXCUSED`.
7. HR can query summaries for a date range, employee or department.

## Attendance statuses
- `PRESENT` — clocked in within the grace period.
- `LATE` — clocked in after scheduled start + grace period.
- `ABSENT` — scheduled but no attendance when HR finalizes the day.
- `EXCUSED` — approved leave or HR-authorized absence.

## Attendance sources
- `EMPLOYEE_CLOCK` — generated from the employee's own authenticated clock event.
- `HR_MANUAL` — entered/corrected by HR.
- `SYSTEM_AUTO` — generated during HR day finalization.

## HR RPCs
- `CreateShift`, `ListShifts`, `CancelShift`
- `ListAttendance`
- `RecordAttendanceByHR`
- `CorrectAttendance`
- `FinalizeAttendanceDay`
- `GetAttendanceSummary`
- `GetHrDashboard`

Employee self-service RPCs are limited to `ClockIn`, `ClockOut` and leave submission.

## HR dashboard requirements for the Linux client
The HR dashboard should have: **Today's Attendance**, **Employees**, **Schedules**, **Attendance History**, **Corrections**, **Leave Requests**, and **Reports**. Today's Attendance should display employee number, employee name, department, shift, clock-in, clock-out, status, late minutes, worked minutes and source. HR actions include mark attendance, correct, finalize day and view period summary.

## Audit and safety rules
- one attendance record per employee/day;
- duplicate clock-in/out rejected;
- clock-out requires prior clock-in;
- manual HR attendance requires a reason;
- corrections record the HR actor and timestamp;
- finalization is safe to repeat because existing records are reused;
- approved leave takes precedence over automatic absence;
- no direct SQL access to Auth or other service databases;
- all authorization remains server-side.
