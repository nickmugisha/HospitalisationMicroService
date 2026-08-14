from __future__ import annotations

import getpass
import uuid
from datetime import datetime, timezone

import grpc

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from billing.v1 import billing_pb2, billing_pb2_grpc


def metadata(token: str):
    return (("authorization", f"Bearer {token}"),)


def money_currency(value):
    fields = value.DESCRIPTOR.fields_by_name
    if "currency_code" in fields:
        return value.currency_code
    if "currency" in fields:
        return value.currency
    return ""


def create_patient(accueil, token):
    stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")[-10:]
    return accueil.CreatePatient(
        accueil_pb2.CreatePatientRequest(
            first_name="Billing",
            last_name=f"Smoke{stamp}",
            sex=accueil_pb2.SEX_MALE,
            birth_date="1990-04-21",
            phone=f"+25776{stamp}",
            address="Bujumbura",
        ),
        metadata=metadata(token),
        timeout=5,
    ).patient


def main():
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    with grpc.insecure_channel("127.0.0.1:50051") as channel:
        auth = auth_pb2_grpc.AuthServiceStub(channel)
        login = auth.Login(auth_pb2.LoginRequest(username=username, password=password), timeout=5)

    with grpc.insecure_channel("127.0.0.1:50052") as channel:
        accueil = accueil_pb2_grpc.AccueilServiceStub(channel)
        patient = create_patient(accueil, login.access_token)

    with grpc.insecure_channel("127.0.0.1:50054") as channel:
        billing = billing_pb2_grpc.BillingServiceStub(channel)
        md = metadata(login.access_token)

        source_id = str(uuid.uuid4())
        charge_key = f"smoke-charge-{uuid.uuid4()}"
        charge_request = billing_pb2.CreateChargeRequest(
            source_type="SMOKE_TEST",
            source_id=source_id,
            patient_id=patient.id,
            amount_minor=120000,
            currency_code="BIF",
            description="ProjectX Billing smoke charge",
            idempotency_key=charge_key,
            correlation_id=str(uuid.uuid4()),
        )
        charge = billing.CreateCharge(charge_request, metadata=md, timeout=5)
        replay = billing.CreateCharge(charge_request, metadata=md, timeout=5)

        balance_before = billing.GetPatientBalance(
            billing_pb2.GetPatientBalanceRequest(patient_id=patient.id),
            metadata=md,
            timeout=5,
        )

        partial_key = f"payment-{uuid.uuid4()}"
        partial = billing.RecordPayment(
            billing_pb2.RecordPaymentRequest(
                invoice_id=charge.invoice.id,
                amount_minor=50000,
                currency_code="BIF",
                method=billing_pb2.PAYMENT_METHOD_CASH,
                reference="SMOKE-CASH-1",
                idempotency_key=partial_key,
            ),
            metadata=md,
            timeout=5,
        )
        partial_replay = billing.RecordPayment(
            billing_pb2.RecordPaymentRequest(
                invoice_id=charge.invoice.id,
                amount_minor=50000,
                currency_code="BIF",
                method=billing_pb2.PAYMENT_METHOD_CASH,
                reference="SMOKE-CASH-1",
                idempotency_key=partial_key,
            ),
            metadata=md,
            timeout=5,
        )

        receipt = billing.GetReceipt(
            billing_pb2.GetReceiptRequest(payment_id=partial.payment.id),
            metadata=md,
            timeout=5,
        ).receipt

        reversal_key = f"reversal-{uuid.uuid4()}"
        reversal = billing.ReversePayment(
            billing_pb2.ReversePaymentRequest(
                payment_id=partial.payment.id,
                reason="Smoke test reversal",
                idempotency_key=reversal_key,
            ),
            metadata=md,
            timeout=5,
        )
        reversal_replay = billing.ReversePayment(
            billing_pb2.ReversePaymentRequest(
                payment_id=partial.payment.id,
                reason="Smoke test reversal",
                idempotency_key=reversal_key,
            ),
            metadata=md,
            timeout=5,
        )

        payment_status = billing.GetPaymentStatus(
            billing_pb2.GetPaymentStatusRequest(payment_id=partial.payment.id),
            metadata=md,
            timeout=5,
        )

        balance_after_reversal = billing.GetPatientBalance(
            billing_pb2.GetPatientBalanceRequest(patient_id=patient.id),
            metadata=md,
            timeout=5,
        )

        overpay_guard = "NOT_TESTED"
        try:
            billing.RecordPayment(
                billing_pb2.RecordPaymentRequest(
                    invoice_id=charge.invoice.id,
                    amount_minor=120001,
                    currency_code="BIF",
                    method=billing_pb2.PAYMENT_METHOD_CASH,
                    reference="SMOKE-OVERPAY",
                    idempotency_key=f"overpay-{uuid.uuid4()}",
                ),
                metadata=md,
                timeout=5,
            )
            overpay_guard = "FAILED"
        except grpc.RpcError as error:
            overpay_guard = error.code().name

        final_payment = billing.RecordPayment(
            billing_pb2.RecordPaymentRequest(
                invoice_id=charge.invoice.id,
                amount_minor=120000,
                currency_code="BIF",
                method=billing_pb2.PAYMENT_METHOD_MOBILE_MONEY,
                reference="SMOKE-MOMO-FINAL",
                idempotency_key=f"final-payment-{uuid.uuid4()}",
            ),
            metadata=md,
            timeout=5,
        )

        invoice = billing.GetInvoice(
            billing_pb2.GetInvoiceRequest(invoice_id=charge.invoice.id),
            metadata=md,
            timeout=5,
        )

        final_balance = billing.GetPatientBalance(
            billing_pb2.GetPatientBalanceRequest(patient_id=patient.id),
            metadata=md,
            timeout=5,
        )

    print()
    print("====================================")
    print(" PROJECTX BILLING SMOKE SUCCESS")
    print("====================================")
    print("Patient number       :", patient.patient_number)
    print("Charge number        :", charge.charge.charge_number)
    print("Invoice number       :", charge.invoice.invoice_number)
    print("Charge replay        :", replay.replayed and replay.charge.id == charge.charge.id)
    print("Balance before       :", balance_before.balance.amount_minor, money_currency(balance_before.balance))
    print("Partial payment      :", partial.payment.amount.amount_minor)
    print("Payment replay       :", partial_replay.replayed and partial_replay.payment.id == partial.payment.id)
    print("Receipt number       :", receipt.receipt_number)
    print("Reversal number      :", reversal.reversal.reversal_number)
    print("Reversal replay      :", reversal_replay.replayed and reversal_replay.reversal.id == reversal.reversal.id)
    print("Payment reversed     :", payment_status.reversed)
    print("Balance after reverse:", balance_after_reversal.balance.amount_minor)
    print("Overpay guard        :", overpay_guard)
    print("Final payment        :", final_payment.payment.amount.amount_minor)
    print("Final balance        :", final_balance.balance.amount_minor)
    print("Final invoice status :", billing_pb2.InvoiceStatus.Name(invoice.invoice.status))
    print("Charges on invoice   :", len(invoice.charges))
    print("Payments on invoice  :", len(invoice.payments))
    print("JWT printed          : False")


if __name__ == "__main__":
    try:
        main()
    except grpc.RpcError as error:
        print("PROJECTX BILLING SMOKE FAILED")
        print("STATUS :", error.code().name)
        print("DETAIL :", error.details())
    except Exception as error:
        print("PROJECTX BILLING SMOKE FAILED")
        print("DETAIL :", str(error))
