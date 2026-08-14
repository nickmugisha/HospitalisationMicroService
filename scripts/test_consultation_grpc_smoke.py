from __future__ import annotations

import getpass
from datetime import datetime, timezone

import grpc

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from consultation.v1 import consultation_pb2, consultation_pb2_grpc


def metadata(token: str):
    return (("authorization", f"Bearer {token}"),)


def main():
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    with grpc.insecure_channel("127.0.0.1:50051") as auth_channel:
        auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)
        login = auth_stub.Login(
            auth_pb2.LoginRequest(username=username, password=password),
            timeout=5,
        )

    stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")[-10:]
    with grpc.insecure_channel("127.0.0.1:50052") as accueil_channel:
        accueil_stub = accueil_pb2_grpc.AccueilServiceStub(accueil_channel)
        patient = accueil_stub.CreatePatient(
            accueil_pb2.CreatePatientRequest(
                first_name="Consult",
                last_name=f"Smoke{stamp}",
                sex=accueil_pb2.SEX_FEMALE,
                birth_date="1992-05-10",
                phone=f"+25778{stamp}",
                address="Bujumbura",
            ),
            metadata=metadata(login.access_token),
            timeout=5,
        ).patient

    with grpc.insecure_channel("127.0.0.1:50055") as channel:
        stub = consultation_pb2_grpc.ConsultationServiceStub(channel)

        created = stub.CreateConsultation(
            consultation_pb2.CreateConsultationRequest(
                patient_id=patient.id,
                reason="Fièvre et fatigue",
                symptoms="Fièvre depuis deux jours",
            ),
            metadata=metadata(login.access_token),
            timeout=5,
        ).consultation

        updated = stub.UpdateClinicalNotes(
            consultation_pb2.UpdateClinicalNotesRequest(
                consultation_id=created.id,
                observations="Patient conscient, état général stable",
                notes="Hydratation recommandée",
                vitals=consultation_pb2.Vitals(
                    temperature_c=38.4,
                    systolic_bp=118,
                    diastolic_bp=76,
                    pulse_bpm=92,
                    spo2_percent=98,
                ),
                diagnoses=[
                    consultation_pb2.DiagnosisInput(
                        text="Syndrome fébrile",
                        code="R50.9",
                        is_primary=True,
                    )
                ],
            ),
            metadata=metadata(login.access_token),
            timeout=5,
        ).consultation

        prescription = stub.IssuePrescription(
            consultation_pb2.IssuePrescriptionRequest(
                consultation_id=created.id,
                items=[
                    consultation_pb2.PrescriptionItemInput(
                        medicine_ref="PARACETAMOL-500MG",
                        dose="500 mg",
                        frequency="3 fois/jour",
                        duration="3 jours",
                        instructions="Après repas si possible",
                    )
                ],
            ),
            metadata=metadata(login.access_token),
            timeout=5,
        ).prescription

        lab_request = stub.RequestLabTest(
            consultation_pb2.RequestLabTestRequest(
                consultation_id=created.id,
                test_code="CBC",
                test_name="Numération formule sanguine",
                clinical_information="Syndrome fébrile",
            ),
            metadata=metadata(login.access_token),
            timeout=5,
        ).request

        hospitalization_request = stub.RequestHospitalization(
            consultation_pb2.RequestHospitalizationRequest(
                consultation_id=created.id,
                reason="Observation clinique si aggravation",
                preferred_ward="Médecine interne",
                target=consultation_pb2.HOSPITALIZATION_TARGET_HOSPITALISATION,
            ),
            metadata=metadata(login.access_token),
            timeout=5,
        ).request

        closed = stub.CloseConsultation(
            consultation_pb2.CloseConsultationRequest(
                consultation_id=created.id,
                closing_notes="Consultation clôturée après plan de prise en charge.",
            ),
            metadata=metadata(login.access_token),
            timeout=5,
        ).consultation

        history = stub.ListPatientConsultations(
            consultation_pb2.ListPatientConsultationsRequest(patient_id=patient.id, limit=20),
            metadata=metadata(login.access_token),
            timeout=5,
        )

        closed_guard = "NOT_TESTED"
        try:
            stub.UpdateClinicalNotes(
                consultation_pb2.UpdateClinicalNotesRequest(
                    consultation_id=created.id,
                    notes="This must not be accepted after close",
                ),
                metadata=metadata(login.access_token),
                timeout=5,
            )
            closed_guard = "FAILED"
        except grpc.RpcError as error:
            closed_guard = error.code().name

    print()
    print("====================================")
    print(" PROJECTX CONSULTATION SMOKE SUCCESS")
    print("====================================")
    print("Patient number      :", patient.patient_number)
    print("Consultation number :", created.consultation_number)
    print("Diagnosis count     :", len(updated.diagnoses))
    print("Prescription number :", prescription.prescription_number)
    print("Lab correlation     :", bool(lab_request.correlation_id))
    print("Hosp correlation    :", bool(hospitalization_request.correlation_id))
    print("Final status        :", consultation_pb2.ConsultationStatus.Name(closed.status))
    print("History total       :", history.total)
    print("Closed update guard :", closed_guard)
    print("JWT printed         : False")


if __name__ == "__main__":
    try:
        main()
    except grpc.RpcError as error:
        print("PROJECTX CONSULTATION SMOKE FAILED")
        print("STATUS :", error.code().name)
        print("DETAIL :", error.details())
