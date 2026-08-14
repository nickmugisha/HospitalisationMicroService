from __future__ import annotations

import getpass
from datetime import datetime, timezone

import grpc

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from consultation.v1 import consultation_pb2, consultation_pb2_grpc
from laboratoire.v1 import laboratoire_pb2, laboratoire_pb2_grpc


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
                first_name="Lab",
                last_name=f"Smoke{stamp}",
                sex=accueil_pb2.SEX_MALE,
                birth_date="1990-04-12",
                phone=f"+25779{stamp}",
                address="Bujumbura",
            ),
            metadata=metadata(login.access_token), timeout=5,
        ).patient

    with grpc.insecure_channel("127.0.0.1:50055") as channel:
        consultation = consultation_pb2_grpc.ConsultationServiceStub(channel)
        created_consultation = consultation.CreateConsultation(
            consultation_pb2.CreateConsultationRequest(
                patient_id=patient.id,
                reason="Fièvre persistante",
                symptoms="Fièvre et fatigue",
            ), metadata=metadata(login.access_token), timeout=5,
        ).consultation
        external = consultation.RequestLabTest(
            consultation_pb2.RequestLabTestRequest(
                consultation_id=created_consultation.id,
                test_code="CBC",
                test_name="Numération formule sanguine",
                clinical_information="Syndrome fébrile",
            ), metadata=metadata(login.access_token), timeout=5,
        ).request

    with grpc.insecure_channel("127.0.0.1:50056") as channel:
        lab = laboratoire_pb2_grpc.LaboratoireServiceStub(channel)
        pending = lab.ListPendingOrders(
            laboratoire_pb2.ListPendingOrdersRequest(limit=100),
            metadata=metadata(login.access_token), timeout=5,
        )
        order = next((o for o in pending.orders if o.correlation_id == external.correlation_id), None)
        if order is None:
            raise RuntimeError("Consultation request was not delivered to Laboratoire.")

        sampled = lab.CollectSample(
            laboratoire_pb2.CollectSampleRequest(order_id=order.id, notes="Prélèvement conforme"),
            metadata=metadata(login.access_token), timeout=5,
        ).order

        recorded = lab.RecordResult(
            laboratoire_pb2.RecordResultRequest(
                order_id=order.id,
                values=[
                    laboratoire_pb2.ResultValue(name="WBC", value="7.2", unit="10^9/L", reference_range="4.0-10.0", flag="NORMAL"),
                    laboratoire_pb2.ResultValue(name="HGB", value="14.1", unit="g/dL", reference_range="12.0-17.0", flag="NORMAL"),
                ],
                text_result="Hémogramme sans anomalie majeure.",
            ), metadata=metadata(login.access_token), timeout=5,
        )

        validated = lab.ValidateResult(
            laboratoire_pb2.ValidateResultRequest(order_id=order.id),
            metadata=metadata(login.access_token), timeout=5,
        )
        fetched = lab.GetLabResult(
            laboratoire_pb2.GetLabResultRequest(order_id=order.id),
            metadata=metadata(login.access_token), timeout=5,
        )
        history = lab.ListPatientLabResults(
            laboratoire_pb2.ListPatientLabResultsRequest(patient_id=patient.id, limit=20),
            metadata=metadata(login.access_token), timeout=5,
        )

        validated_guard = "NOT_TESTED"
        try:
            lab.RecordResult(
                laboratoire_pb2.RecordResultRequest(
                    order_id=order.id,
                    text_result="Silent overwrite must fail",
                ), metadata=metadata(login.access_token), timeout=5,
            )
            validated_guard = "FAILED"
        except grpc.RpcError as error:
            validated_guard = error.code().name

    print()
    print("====================================")
    print(" PROJECTX LABORATOIRE SMOKE SUCCESS")
    print("====================================")
    print("Patient number       :", patient.patient_number)
    print("Consultation number  :", created_consultation.consultation_number)
    print("Consult -> Lab        :", consultation_pb2.ExternalRequestStatus.Name(external.status))
    print("Lab order number      :", order.order_number)
    print("Sample code           :", sampled.sample.sample_code)
    print("Recorded values       :", len(recorded.result.values))
    print("Final status          :", laboratoire_pb2.LabOrderStatus.Name(validated.order.status))
    print("Result validated      :", bool(fetched.result.validated_by))
    print("History total         :", history.total)
    print("Billing charge status :", laboratoire_pb2.BillingChargeStatus.Name(validated.order.billing_charge_status))
    print("Validated edit guard  :", validated_guard)
    print("JWT printed           : False")


if __name__ == "__main__":
    try:
        main()
    except grpc.RpcError as error:
        print("PROJECTX LABORATOIRE SMOKE FAILED")
        print("STATUS :", error.code().name)
        print("DETAIL :", error.details())
    except Exception as error:
        print("PROJECTX LABORATOIRE SMOKE FAILED")
        print("DETAIL :", str(error))
