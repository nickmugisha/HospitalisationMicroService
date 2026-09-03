from __future__ import annotations

"""
ProjectX demo billing completion seed v1
---------------------------------------
Completes the billing portion of the ProjectX demo dataset through gRPC only.

Why this file exists:
- The main demo seeder correctly created patients/staff/clinical/pharmacy/etc.
- Its billing step used the CAISSIER token for CreateCharge.
- In ProjectX RBAC, CAISSIER records payments but does NOT create inter-service charges.
- This script creates charges with legitimate service-role actors, then records payments
  with the CAISSIER account.

Run from:
    D:\skl\HospitalisationMicroService

with:
    $env:PYTHONPATH="$PWD;$PWD\\generated"
    .\.venv\Scripts\python.exe .\scripts\seed_projectx_demo_billing_fix_v1.py
"""

import getpass
import os
import grpc

from auth.v1 import auth_pb2, auth_pb2_grpc
from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from billing.v1 import billing_pb2, billing_pb2_grpc

HOST = os.getenv("PROJECTX_GRPC_HOST", "127.0.0.1")
DEMO_PASSWORD = os.getenv("PROJECTX_DEMO_PASSWORD", "ProjectX-Demo-2026!")
TIMEOUT = 6

PATIENT_PHONES = [
    "+257796200101",
    "+257796200102",
    "+257796200103",
    "+257796200104",
    "+257796200105",
    "+257796200106",
    "+257796200107",
    "+257796200108",
    "+257796200109",
    "+257796200110",
]

# These roles legitimately own billing.charge.create in ProjectX.
SOURCE_ACTORS = [
    ("lab.luka", "LABORATOIRE", "Examen de laboratoire"),
    ("pharmacy.andrea", "PHARMACIE", "Médicaments délivrés"),
    ("hosp.roberto", "HOSPITALISATION", "Frais de séjour"),
    ("maternity.lucia", "MATERNITE", "Actes de maternité"),
]

AMOUNTS = [18000, 22500, 35000, 45000, 28000, 52000, 16000, 65000, 24000, 40000]


def md(token: str):
    return (("authorization", f"Bearer {token}"),)


def login(auth, identifier: str, password: str):
    try:
        return auth.Login(
            auth_pb2.LoginRequest(identifier=identifier, password=password),
            timeout=TIMEOUT,
        )
    except grpc.RpcError:
        return auth.Login(
            auth_pb2.LoginRequest(username=identifier, password=password),
            timeout=TIMEOUT,
        )


def main():
    print("PROJECTX DEMO BILLING COMPLETION SEED v1")
    print(f"Target gRPC host: {HOST}")
    print("No direct MySQL writes.\n")

    admin_username = input("Admin username [admin]: ").strip() or "admin"
    admin_password = getpass.getpass("Admin password: ")

    auth_ch = grpc.insecure_channel(f"{HOST}:50051")
    accueil_ch = grpc.insecure_channel(f"{HOST}:50052")
    billing_ch = grpc.insecure_channel(f"{HOST}:50054")

    auth = auth_pb2_grpc.AuthServiceStub(auth_ch)
    accueil = accueil_pb2_grpc.AccueilServiceStub(accueil_ch)
    billing = billing_pb2_grpc.BillingServiceStub(billing_ch)

    admin = login(auth, admin_username, admin_password)
    AMD = md(admin.access_token)
    print(f"[OK] Admin login: {admin.user.display_name or admin.user.username}")

    cashier = login(auth, "cashier.sofia", DEMO_PASSWORD)
    CASHIER_MD = md(cashier.access_token)
    print("[OK] Cashier login: cashier.sofia")

    actor_tokens = {}
    for username, source_type, description in SOURCE_ACTORS:
        lr = login(auth, username, DEMO_PASSWORD)
        actor_tokens[username] = lr.access_token
        print(f"[OK] Billing source actor login: {username} ({source_type})")

    patients = []
    for phone in PATIENT_PHONES:
        sr = accueil.SearchPatients(
            accueil_pb2.SearchPatientsRequest(query=phone, limit=20, offset=0),
            metadata=AMD,
            timeout=TIMEOUT,
        )
        p = next((x for x in sr.patients if x.phone == phone), None)
        if p is None:
            print(f"[WARN] Demo patient not found for {phone}; skipping.")
            continue
        patients.append(p)

    print(f"[OK] Demo patients resolved: {len(patients)}")

    completed = 0
    for i, p in enumerate(patients):
        username, source_type, description = SOURCE_ACTORS[i % len(SOURCE_ACTORS)]
        source_md = md(actor_tokens[username])
        amount = AMOUNTS[i]

        try:
            cr = billing.CreateCharge(
                billing_pb2.CreateChargeRequest(
                    source_type=source_type,
                    source_id=f"DEMO-BILL-{source_type}-{i+1:03d}",
                    patient_id=p.id,
                    amount_minor=amount,
                    currency_code="BIF",
                    description=description,
                    idempotency_key=f"DEMO-BILLING-FIX-CHARGE-{p.id}-{i}",
                    correlation_id=f"demo-billing-fix-{p.id}",
                ),
                metadata=source_md,
                timeout=TIMEOUT,
            )
        except grpc.RpcError as exc:
            print(f"[WARN] Charge {p.patient_number}: {exc.code().name}: {exc.details()}")
            continue

        inv = cr.invoice
        payment_label = "UNPAID"

        # First 3 invoices fully paid; next 3 partially paid; last 4 unpaid.
        if i < 6 and inv.balance.amount_minor > 0:
            pay_amount = inv.balance.amount_minor if i < 3 else max(1000, inv.balance.amount_minor // 2)
            try:
                pr = billing.RecordPayment(
                    billing_pb2.RecordPaymentRequest(
                        invoice_id=inv.id,
                        amount_minor=pay_amount,
                        currency_code="BIF",
                        method=(
                            billing_pb2.PAYMENT_METHOD_CASH
                            if i % 2 == 0
                            else billing_pb2.PAYMENT_METHOD_MOBILE_MONEY
                        ),
                        reference=f"DEMO-BILLING-PAY-{i+1:03d}",
                        idempotency_key=f"DEMO-BILLING-FIX-PAYMENT-{p.id}-{i}",
                    ),
                    metadata=CASHIER_MD,
                    timeout=TIMEOUT,
                )
                payment_label = "PAID" if pr.invoice.balance.amount_minor == 0 else "PARTIAL"
                inv = pr.invoice
            except grpc.RpcError as exc:
                print(f"[WARN] Payment {p.patient_number}: {exc.code().name}: {exc.details()}")

        print(
            f"[OK] {p.patient_number} | {source_type:<15} | "
            f"invoice={inv.invoice_number} | status={billing_pb2.InvoiceStatus.Name(inv.status)} | "
            f"balance={inv.balance.amount_minor} BIF | {payment_label}"
        )
        completed += 1

    print("\n" + "=" * 72)
    print("PROJECTX DEMO BILLING COMPLETION FINISHED")
    print("=" * 72)
    print(f"Billing cases completed/replayed: {completed}")
    print("Expected visual mix: paid + partially paid + unpaid invoices.")
    print("CAISSIER was used only for payments; service roles created charges.")
    print("This matches ProjectX RBAC instead of weakening permissions.")

    auth_ch.close()
    accueil_ch.close()
    billing_ch.close()


if __name__ == "__main__":
    main()
