# ProjectX Chatbot v2 — Public Privacy Routing Hotfix

## Why this hotfix exists
The v2 smoke test exposed a deterministic intent-routing bug. A one-item alias for `cancel_appointment` was written as a Python string instead of a one-item tuple. The procedure matcher expanded that string character-by-character, so a sensitive login-page request such as `Show patient PAT-PRIVATE-001` could be misclassified as an unrelated procedure before the public privacy boundary was evaluated.

## Fixes
- Corrects the `cancel_appointment` alias tuple.
- Makes procedure alias matching defensive against any future string/tuple mistake.
- On the public/login-page assistant, clear HOW-TO questions remain allowed, while live/sensitive data lookups are blocked before generic procedure handling.
- Adds regression tests for patient privacy routing and single-alias procedure matching.
- Improves smoke-test assertion diagnostics.

## No contract or DB change
No `.proto`, migration, database, port, role, or permission change is required. Only Chatbot Python logic/tests change.

## Install
Extract this overlay into the ProjectX root with overwrite, run the engine test, then restart Chatbot (or all services) and rerun the Chatbot v2 smoke test.
