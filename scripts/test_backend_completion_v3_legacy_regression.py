from __future__ import annotations

import builtins
import getpass
import io
import os
import runpy
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

TESTS = [
    ("Accueil", "test_accueil_grpc_smoke.py", "PROJECTX ACCUEIL SMOKE SUCCESS"),
    ("Consultation", "test_consultation_grpc_smoke.py", "PROJECTX CONSULTATION SMOKE SUCCESS"),
    ("Laboratoire", "test_laboratoire_grpc_smoke.py", "PROJECTX LABORATOIRE SMOKE SUCCESS"),
    ("Pharmacie", "test_pharmacie_grpc_smoke.py", "PROJECTX PHARMACIE SMOKE SUCCESS"),
    ("Hospitalisation", "test_hospitalisation_grpc_smoke.py", "PROJECTX HOSPITALISATION SMOKE SUCCESS"),
    ("Billing", "test_billing_grpc_smoke.py", "PROJECTX BILLING SMOKE SUCCESS"),
    ("Rendez-vous", "test_rendezvous_grpc_smoke.py", "PROJECTX RENDEZVOUS SMOKE SUCCESS"),
    ("Maternité", "test_maternite_grpc_smoke.py", "PROJECTX MATERNITE SMOKE SUCCESS"),
    ("BI", "test_bi_grpc_smoke.py", "PROJECTX BI SMOKE SUCCESS"),
]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    username = input("Admin username: ").strip()
    password = getpass.getpass("Admin password: ")
    if not username or not password:
        raise SystemExit("Credentials are required locally for the regression runner.")

    original_input = builtins.input
    original_getpass = getpass.getpass
    passed = 0
    failed: list[str] = []

    print("\nPROJECTX V3 — LEGACY BUSINESS REGRESSION")
    print("=========================================")
    print("Runs the original service smoke tests after v3 using one local credential prompt.")
    print("These tests intentionally create isolated smoke/demo records.\n")

    def fake_input(prompt: str = "") -> str:
        if "user" in prompt.lower():
            return username
        return original_input(prompt)

    def fake_getpass(prompt: str = "Password: ", stream=None) -> str:
        return password

    builtins.input = fake_input
    getpass.getpass = fake_getpass
    try:
        for label, filename, success_marker in TESTS:
            path = scripts / filename
            print(f"\n===== {label} =====")
            if not path.exists():
                print(f"[FAIL] Missing existing regression script: {path}")
                failed.append(label)
                continue

            capture = io.StringIO()
            exc: BaseException | None = None
            try:
                with redirect_stdout(capture), redirect_stderr(capture):
                    runpy.run_path(str(path), run_name="__main__")
            except SystemExit as e:
                if e.code not in (None, 0):
                    exc = e
            except BaseException as e:
                exc = e

            text = capture.getvalue()
            if text:
                print(text.rstrip())
            if exc is not None:
                print(f"[FAIL] {label}: unhandled {type(exc).__name__}: {exc}")
                failed.append(label)
                continue

            if success_marker in text and "SMOKE FAILED" not in text:
                print(f"[PASS] {label} legacy smoke preserved after v3")
                passed += 1
            else:
                print(f"[FAIL] {label}: expected success marker not observed")
                failed.append(label)
    finally:
        builtins.input = original_input
        getpass.getpass = original_getpass

    print("\n=========================================")
    print(f"Legacy service smokes: {passed}/{len(TESTS)} PASS")
    if failed:
        print("Failed:", ", ".join(failed))
        raise SystemExit("PROJECTX V3 LEGACY BUSINESS REGRESSION: FAIL")
    print("PROJECTX V3 LEGACY BUSINESS REGRESSION: PASS")


if __name__ == "__main__":
    main()
