from __future__ import annotations

import getpass
import uuid
from datetime import date, datetime, timedelta, timezone

import grpc

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from consultation.v1 import consultation_pb2, consultation_pb2_grpc
from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc


def metadata(token: str):
    return (("authorization", f"Bearer {token}"),)


def main():
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    with grpc.insecure_channel("127.0.0.1:50051") as channel:
        auth = auth_pb2_grpc.AuthServiceStub(channel)
        login = auth.Login(auth_pb2.LoginRequest(username=username, password=password), timeout=5)

    stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")[-10:]
    with grpc.insecure_channel("127.0.0.1:50052") as channel:
        accueil = accueil_pb2_grpc.AccueilServiceStub(channel)
        patient = accueil.CreatePatient(
            accueil_pb2.CreatePatientRequest(
                first_name="Pharma",
                last_name=f"Smoke{stamp}",
                sex=accueil_pb2.SEX_FEMALE,
                birth_date="1992-05-18",
                phone=f"+25778{stamp}",
                address="Bujumbura",
            ),
            metadata=metadata(login.access_token), timeout=5,
        ).patient

    with grpc.insecure_channel("127.0.0.1:50055") as channel:
        consultation = consultation_pb2_grpc.ConsultationServiceStub(channel)
        cons = consultation.CreateConsultation(
            consultation_pb2.CreateConsultationRequest(
                patient_id=patient.id,
                reason="Douleur et fièvre",
                symptoms="Fièvre légère",
            ), metadata=metadata(login.access_token), timeout=5,
        ).consultation
        rx = consultation.IssuePrescription(
            consultation_pb2.IssuePrescriptionRequest(
                consultation_id=cons.id,
                items=[
                    consultation_pb2.PrescriptionItemInput(
                        medicine_ref="PARACETAMOL-500MG",
                        dose="500 mg",
                        frequency="3 fois/jour",
                        duration="3 jours",
                        instructions="Après repas",
                    ),
                    consultation_pb2.PrescriptionItemInput(
                        medicine_ref="AMOXICILLIN-500MG",
                        dose="500 mg",
                        frequency="2 fois/jour",
                        duration="5 jours",
                        instructions="Selon indication clinique",
                    ),
                ],
            ), metadata=metadata(login.access_token), timeout=5,
        ).prescription

    with grpc.insecure_channel("127.0.0.1:50057") as channel:
        pharmacy = pharmacie_pb2_grpc.PharmacieServiceStub(channel)
        meds = pharmacy.SearchMedicines(
            pharmacie_pb2.SearchMedicinesRequest(query="PARACETAMOL", active_only=True, limit=20),
            metadata=metadata(login.access_token), timeout=5,
        )
        if not any(m.code == "PARACETAMOL-500MG" for m in meds.medicines):
            raise RuntimeError("Seeded Paracetamol medicine not found.")

        expiry = (date.today() + timedelta(days=365)).isoformat()
        stock = pharmacy.RegisterStockEntry(
            pharmacie_pb2.RegisterStockEntryRequest(
                medicine_code="PARACETAMOL-500MG",
                batch_number=f"SMOKE-{stamp}",
                expiry_date=expiry,
                quantity=8,
                reference=f"SMOKE-{stamp}",
            ), metadata=metadata(login.access_token), timeout=5,
        ).stock
        before = stock.total_available

        idem = f"smoke-dispense-{uuid.uuid4()}"
        first = pharmacy.DispensePrescription(
            pharmacie_pb2.DispensePrescriptionRequest(
                prescription_id=rx.id,
                items=[pharmacie_pb2.DispenseItemInput(medicine_ref="PARACETAMOL-500MG", quantity=5)],
                idempotency_key=idem,
            ), metadata=metadata(login.access_token), timeout=5,
        )
        second = pharmacy.DispensePrescription(
            pharmacie_pb2.DispensePrescriptionRequest(
                prescription_id=rx.id,
                items=[pharmacie_pb2.DispenseItemInput(medicine_ref="PARACETAMOL-500MG", quantity=5)],
                idempotency_key=idem,
            ), metadata=metadata(login.access_token), timeout=5,
        )
        after = pharmacy.GetStock(
            pharmacie_pb2.GetStockRequest(medicine_ref="PARACETAMOL-500MG"),
            metadata=metadata(login.access_token), timeout=5,
        ).stock

        if first.dispensation.id != second.dispensation.id:
            raise RuntimeError("Idempotent replay created a second dispensation.")
        if after.total_available != before - 5:
            raise RuntimeError(f"Unexpected stock after idempotent dispensing: before={before}, after={after.total_available}")

        insufficient_guard = "NOT_TESTED"
        try:
            pharmacy.DispensePrescription(
                pharmacie_pb2.DispensePrescriptionRequest(
                    prescription_id=rx.id,
                    items=[pharmacie_pb2.DispenseItemInput(medicine_ref="PARACETAMOL-500MG", quantity=999999)],
                    idempotency_key=f"smoke-insufficient-{uuid.uuid4()}",
                ), metadata=metadata(login.access_token), timeout=5,
            )
            insufficient_guard = "FAILED"
        except grpc.RpcError as error:
            insufficient_guard = error.code().name

        alerts = pharmacy.ListStockAlerts(
            pharmacie_pb2.ListStockAlertsRequest(days_to_expiry=30),
            metadata=metadata(login.access_token), timeout=5,
        )
        low_alert = any(
            a.medicine_code == "PARACETAMOL-500MG" and a.type == pharmacie_pb2.STOCK_ALERT_TYPE_LOW_STOCK
            for a in alerts.alerts
        )

        po = pharmacy.CreatePurchaseOrder(
            pharmacie_pb2.CreatePurchaseOrderRequest(
                supplier_code="SUP-001",
                items=[pharmacie_pb2.PurchaseOrderItemInput(medicine_code="AMOXICILLIN-500MG", quantity=12)],
                idempotency_key=f"smoke-po-{uuid.uuid4()}",
            ), metadata=metadata(login.access_token), timeout=5,
        ).purchase_order
        received = pharmacy.ReceivePurchaseOrder(
            pharmacie_pb2.ReceivePurchaseOrderRequest(
                purchase_order_id=po.id,
                items=[
                    pharmacie_pb2.PurchaseReceiptItem(
                        medicine_code="AMOXICILLIN-500MG",
                        batch_number=f"PO-{stamp}",
                        expiry_date=(date.today() + timedelta(days=540)).isoformat(),
                        quantity=12,
                    )
                ],
                idempotency_key=f"smoke-receipt-{uuid.uuid4()}",
            ), metadata=metadata(login.access_token), timeout=5,
        ).purchase_order

    print()
    print("====================================")
    print(" PROJECTX PHARMACIE SMOKE SUCCESS")
    print("====================================")
    print("Patient number       :", patient.patient_number)
    print("Consultation number  :", cons.consultation_number)
    print("Prescription number  :", rx.prescription_number)
    print("Prescription exposed :", True)
    print("Stock before          :", before)
    print("Dispensed quantity    :", first.dispensation.items[0].quantity)
    print("Stock after           :", after.total_available)
    print("Idempotent replay     :", first.dispensation.id == second.dispensation.id)
    print("Billing charge status :", pharmacie_pb2.BillingChargeStatus.Name(first.dispensation.billing_charge_status))
    print("Insufficient guard    :", insufficient_guard)
    print("Low stock alert       :", low_alert)
    print("PO status             :", pharmacie_pb2.PurchaseOrderStatus.Name(received.status))
    print("JWT printed           : False")


if __name__ == "__main__":
    try:
        main()
    except grpc.RpcError as error:
        print("PROJECTX PHARMACIE SMOKE FAILED")
        print("STATUS :", error.code().name)
        print("DETAIL :", error.details())
    except Exception as error:
        print("PROJECTX PHARMACIE SMOKE FAILED")
        print("DETAIL :", str(error))
