PROJECTX BACKEND COMPLETION v3.0.2 - READ-ONLY TEST HOTFIX

Scope: test-only. No service code, proto, migration, database, permission, or environment change.

Fix:
  GetLabTestRequest(test_code=...)
becomes:
  GetLabTestRequest(test_ref=...)

Reason:
  proto/laboratoire/v1/laboratoire.proto defines:
    message GetLabTestRequest { string test_ref = 1; }
  The Laboratoire service resolves test_ref by either laboratory test UUID or test code.

Install by extracting this ZIP into the ProjectX repository root with -Force.
Then rerun:
  .\.venv\Scripts\python.exe .\scripts\test_backend_completion_v3_readonly.py
