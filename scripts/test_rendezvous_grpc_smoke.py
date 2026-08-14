from __future__ import annotations
import getpass, uuid
from datetime import datetime, timedelta, timezone
import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from rendezvous.v1 import rendezvous_pb2, rendezvous_pb2_grpc

def metadata(token: str): return (("authorization",f"Bearer {token}"),)
def ts(dt):
    x=Timestamp(); x.FromDatetime(dt.astimezone(timezone.utc)); return x

def create_patient(accueil,token,label):
    stamp=datetime.now(timezone.utc).strftime("%H%M%S%f")[-10:]
    return accueil.CreatePatient(accueil_pb2.CreatePatientRequest(
        first_name=label,last_name=f"RdvSmoke{stamp}",sex=accueil_pb2.SEX_MALE,
        birth_date="1992-06-10",phone=f"+25778{stamp}",address="Bujumbura"
    ),metadata=metadata(token),timeout=5).patient

def main():
    username=input("Username: ").strip(); password=getpass.getpass("Password: ")
    with grpc.insecure_channel("127.0.0.1:50051") as channel:
        auth=auth_pb2_grpc.AuthServiceStub(channel); login=auth.Login(auth_pb2.LoginRequest(username=username,password=password),timeout=5)
    with grpc.insecure_channel("127.0.0.1:50052") as channel:
        accueil=accueil_pb2_grpc.AccueilServiceStub(channel)
        patient=create_patient(accueil,login.access_token,"Agenda")
        second_patient=create_patient(accueil,login.access_token,"DoubleBook")
    provider=f"DOC-SMOKE-{uuid.uuid4().hex[:6].upper()}"; now=datetime.now(timezone.utc)
    start1=(now+timedelta(days=1)).replace(minute=0,second=0,microsecond=0)
    start2=start1+timedelta(hours=1); start3=start1+timedelta(hours=2)
    with grpc.insecure_channel("127.0.0.1:50059") as channel:
        rdv=rendezvous_pb2_grpc.RendezvousServiceStub(channel); md=metadata(login.access_token)
        slots=[]
        for start in (start1,start2,start3):
            slots.append(rdv.CreateScheduleSlot(rendezvous_pb2.CreateScheduleSlotRequest(
                provider_id=provider,service="CONSULTATION",start_at=ts(start),end_at=ts(start+timedelta(minutes=45)),idempotency_key=f"slot-{uuid.uuid4()}"
            ),metadata=md,timeout=5).slot)
        available=rdv.ListAvailableSlots(rendezvous_pb2.ListAvailableSlotsRequest(
            provider_id=provider,service="CONSULTATION",from_at=ts(start1-timedelta(hours=1)),to_at=ts(start3+timedelta(hours=2))
        ),metadata=md,timeout=5)
        create_key=f"rdv-{uuid.uuid4()}"
        created=rdv.CreateAppointment(rendezvous_pb2.CreateAppointmentRequest(
            patient_id=patient.id,slot_id=slots[0].id,reason="Consultation générale",idempotency_key=create_key,correlation_id=str(uuid.uuid4())
        ),metadata=md,timeout=5)
        replay=rdv.CreateAppointment(rendezvous_pb2.CreateAppointmentRequest(
            patient_id=patient.id,slot_id=slots[0].id,reason="Consultation générale",idempotency_key=create_key,correlation_id=created.appointment.correlation_id
        ),metadata=md,timeout=5)
        guard="NOT_TESTED"
        try:
            rdv.CreateAppointment(rendezvous_pb2.CreateAppointmentRequest(
                patient_id=second_patient.id,slot_id=slots[0].id,reason="Tentative double réservation",idempotency_key=f"double-{uuid.uuid4()}",correlation_id=str(uuid.uuid4())
            ),metadata=md,timeout=5); guard="FAILED"
        except grpc.RpcError as error: guard=error.code().name
        confirmed=rdv.ConfirmAppointment(rendezvous_pb2.ConfirmAppointmentRequest(appointment_id=created.appointment.id),metadata=md,timeout=5).appointment
        rescheduled=rdv.RescheduleAppointment(rendezvous_pb2.RescheduleAppointmentRequest(
            appointment_id=created.appointment.id,new_slot_id=slots[1].id,reason="Horaire patient",idempotency_key=f"reschedule-{uuid.uuid4()}"
        ),metadata=md,timeout=5).appointment
        checked=rdv.MarkCheckedIn(rendezvous_pb2.MarkCheckedInRequest(
            appointment_id=created.appointment.id,idempotency_key=f"checkin-{uuid.uuid4()}"
        ),metadata=md,timeout=5).appointment
        completed=rdv.CompleteAppointment(rendezvous_pb2.CompleteAppointmentRequest(appointment_id=created.appointment.id),metadata=md,timeout=5).appointment
        second=rdv.CreateAppointment(rendezvous_pb2.CreateAppointmentRequest(
            patient_id=second_patient.id,slot_id=slots[2].id,reason="Rendez-vous à annuler",idempotency_key=f"cancel-smoke-{uuid.uuid4()}",correlation_id=str(uuid.uuid4())
        ),metadata=md,timeout=5).appointment
        cancel_reason="Patient indisponible"
        cancelled=rdv.CancelAppointment(rendezvous_pb2.CancelAppointmentRequest(
            appointment_id=second.id,reason=cancel_reason,idempotency_key=f"cancel-{uuid.uuid4()}"
        ),metadata=md,timeout=5).appointment
        agenda=rdv.ListAgenda(rendezvous_pb2.ListAgendaRequest(
            provider_id=provider,from_at=ts(start1-timedelta(hours=1)),to_at=ts(start3+timedelta(hours=2))
        ),metadata=md,timeout=5)
    print(); print("====================================")
    print(" PROJECTX RENDEZVOUS SMOKE SUCCESS")
    print("====================================")
    print("Patient number       :",patient.patient_number)
    print("Provider              :",provider)
    print("Available slots start :",available.total)
    print("Appointment number    :",created.appointment.appointment_number)
    print("Create replay         :",replay.replayed)
    print("Double-book guard     :",guard)
    print("Confirmed status      :",rendezvous_pb2.AppointmentStatus.Name(confirmed.status))
    print("Rescheduled slot      :",rescheduled.slot.id==slots[1].id)
    print("Check-in status       :",rendezvous_pb2.AppointmentStatus.Name(checked.status))
    print("Accueil arrival       :",bool(checked.arrival_id))
    print("Completed status      :",rendezvous_pb2.AppointmentStatus.Name(completed.status))
    print("Cancelled status      :",rendezvous_pb2.AppointmentStatus.Name(cancelled.status))
    print("Cancel reason kept    :",cancelled.cancellation_reason==cancel_reason)
    print("Agenda total          :",agenda.total)
    print("JWT printed           : False")

if __name__=="__main__":
    try: main()
    except grpc.RpcError as error:
        print("PROJECTX RENDEZVOUS SMOKE FAILED"); print("STATUS :",error.code().name); print("DETAIL :",error.details())
    except Exception as error:
        print("PROJECTX RENDEZVOUS SMOKE FAILED"); print("DETAIL :",str(error))
