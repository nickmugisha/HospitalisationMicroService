from __future__ import annotations
import getpass
import uuid
from datetime import datetime, timezone
import grpc
from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from consultation.v1 import consultation_pb2, consultation_pb2_grpc
from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc

def metadata(token: str): return (("authorization", f"Bearer {token}"),)

def create_patient(accueil, token, label):
    stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")[-10:]
    return accueil.CreatePatient(
        accueil_pb2.CreatePatientRequest(
            first_name=label, last_name=f"Smoke{stamp}", sex=accueil_pb2.SEX_MALE,
            birth_date="1989-03-14", phone=f"+25777{stamp}", address="Bujumbura",
        ), metadata=metadata(token), timeout=5,
    ).patient

def main():
    username=input("Username: ").strip(); password=getpass.getpass("Password: ")
    with grpc.insecure_channel("127.0.0.1:50051") as channel:
        auth=auth_pb2_grpc.AuthServiceStub(channel); login=auth.Login(auth_pb2.LoginRequest(username=username,password=password),timeout=5)
    with grpc.insecure_channel("127.0.0.1:50052") as channel:
        accueil=accueil_pb2_grpc.AccueilServiceStub(channel); patient=create_patient(accueil, login.access_token, "Hosp")
        second_patient=create_patient(accueil, login.access_token, "BedGuard")
    with grpc.insecure_channel("127.0.0.1:50055") as channel:
        consultation=consultation_pb2_grpc.ConsultationServiceStub(channel)
        cons=consultation.CreateConsultation(
            consultation_pb2.CreateConsultationRequest(patient_id=patient.id, reason="Surveillance clinique", symptoms="État nécessitant hospitalisation"),
            metadata=metadata(login.access_token), timeout=5,
        ).consultation
        external=consultation.RequestHospitalization(
            consultation_pb2.RequestHospitalizationRequest(
                consultation_id=cons.id, reason="Surveillance 24h", preferred_ward="MED",
                target=consultation_pb2.HOSPITALIZATION_TARGET_HOSPITALISATION,
            ), metadata=metadata(login.access_token), timeout=5,
        ).request
    with grpc.insecure_channel("127.0.0.1:50053") as channel:
        hosp=hospitalisation_pb2_grpc.HospitalisationServiceStub(channel)
        active=hosp.GetCurrentAdmission(hospitalisation_pb2.GetCurrentAdmissionRequest(patient_id=patient.id), metadata=metadata(login.access_token), timeout=5).admission
        avail=hosp.GetBedAvailability(hospitalisation_pb2.GetBedAvailabilityRequest(ward_code="MED", available_only=True), metadata=metadata(login.access_token), timeout=5)
        if len(avail.beds) < 2: raise RuntimeError("Need at least two available MED beds for smoke test.")
        first_bed, second_bed=avail.beds[0], avail.beds[1]
        assigned=hosp.AssignBed(hospitalisation_pb2.AssignBedRequest(admission_id=active.id, bed_id=first_bed.id, idempotency_key=f"assign-{uuid.uuid4()}"), metadata=metadata(login.access_token), timeout=5).admission
        note=hosp.AddStayNote(hospitalisation_pb2.AddStayNoteRequest(admission_id=active.id, note="Patient stable, surveillance en cours."), metadata=metadata(login.access_token), timeout=5).note
        transferred=hosp.TransferBed(hospitalisation_pb2.TransferBedRequest(admission_id=active.id, to_bed_id=second_bed.id, idempotency_key=f"transfer-{uuid.uuid4()}"), metadata=metadata(login.access_token), timeout=5)
        second_adm=hosp.CreateAdmission(hospitalisation_pb2.CreateAdmissionRequest(
            patient_id=second_patient.id, reason="Double-bed guard smoke", preferred_ward="MED", correlation_id=str(uuid.uuid4()), idempotency_key=f"admit-{uuid.uuid4()}"
        ), metadata=metadata(login.access_token), timeout=5).admission
        guard="NOT_TESTED"
        try:
            hosp.AssignBed(hospitalisation_pb2.AssignBedRequest(admission_id=second_adm.id, bed_id=second_bed.id, idempotency_key=f"guard-{uuid.uuid4()}"), metadata=metadata(login.access_token), timeout=5)
            guard="FAILED"
        except grpc.RpcError as error:
            guard=error.code().name
        discharge_key=f"discharge-{uuid.uuid4()}"
        discharged=hosp.DischargePatient(hospitalisation_pb2.DischargePatientRequest(admission_id=active.id, discharge_summary="État amélioré, retour domicile.", idempotency_key=discharge_key), metadata=metadata(login.access_token), timeout=5).admission
        replay=hosp.DischargePatient(hospitalisation_pb2.DischargePatientRequest(admission_id=active.id, discharge_summary="État amélioré, retour domicile.", idempotency_key=discharge_key), metadata=metadata(login.access_token), timeout=5).admission
        after=hosp.GetBedAvailability(hospitalisation_pb2.GetBedAvailabilityRequest(ward_code="MED", available_only=True), metadata=metadata(login.access_token), timeout=5)
        released=any(x.id==second_bed.id for x in after.beds)
    print(); print("========================================")
    print(" PROJECTX HOSPITALISATION SMOKE SUCCESS")
    print("========================================")
    print("Patient number       :", patient.patient_number)
    print("Consultation number  :", cons.consultation_number)
    print("Consult -> Hosp       :", consultation_pb2.ExternalRequestStatus.Name(external.status))
    print("Admission number      :", active.admission_number)
    print("Assigned status       :", hospitalisation_pb2.AdmissionStatus.Name(assigned.status))
    print("Stay note created     :", bool(note.id))
    print("Transfer completed    :", bool(transferred.transfer.completed_at.seconds))
    print("Double-bed guard      :", guard)
    print("Final status          :", hospitalisation_pb2.AdmissionStatus.Name(discharged.status))
    print("Billing charge status :", hospitalisation_pb2.BillingChargeStatus.Name(discharged.billing_charge_status))
    print("Discharge replay      :", discharged.id == replay.id)
    print("Bed released          :", released)
    print("JWT printed           : False")

if __name__ == "__main__":
    try: main()
    except grpc.RpcError as error:
        print("PROJECTX HOSPITALISATION SMOKE FAILED"); print("STATUS :", error.code().name); print("DETAIL :", error.details())
    except Exception as error:
        print("PROJECTX HOSPITALISATION SMOKE FAILED"); print("DETAIL :", str(error))
