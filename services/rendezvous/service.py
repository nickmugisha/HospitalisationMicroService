from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone, timedelta

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from services.common.notifications import send_system_notification
from rendezvous.v1 import rendezvous_pb2, rendezvous_pb2_grpc
from database.rendezvous_session import RendezvousSessionLocal, engine
from services.common.auth_guard import require_permission
from services.rendezvous.config import (
    ACCUEIL_GRPC_TARGET, AUTH_GRPC_TARGET, SERVICE_VERSION,
    RENDEZVOUS_REMINDER_LEAD_MINUTES,
)
from services.rendezvous.models import Appointment, AppointmentEvent, ScheduleSlot
from services.rendezvous.repository import (
    get_appointment, get_appointment_by_idempotency, get_appointment_by_number,
    get_slot, get_slot_by_idempotency,
)

logger = logging.getLogger("projectx.rendezvous.service")

SLOT_STATUS_DB_TO_PROTO = {
    "AVAILABLE": rendezvous_pb2.SCHEDULE_SLOT_STATUS_AVAILABLE,
    "BOOKED": rendezvous_pb2.SCHEDULE_SLOT_STATUS_BOOKED,
    "BLOCKED": rendezvous_pb2.SCHEDULE_SLOT_STATUS_BLOCKED,
}
APPOINTMENT_STATUS_DB_TO_PROTO = {
    "BOOKED": rendezvous_pb2.APPOINTMENT_STATUS_BOOKED,
    "CONFIRMED": rendezvous_pb2.APPOINTMENT_STATUS_CONFIRMED,
    "CHECKED_IN": rendezvous_pb2.APPOINTMENT_STATUS_CHECKED_IN,
    "COMPLETED": rendezvous_pb2.APPOINTMENT_STATUS_COMPLETED,
    "CANCELLED": rendezvous_pb2.APPOINTMENT_STATUS_CANCELLED,
    "NO_SHOW": rendezvous_pb2.APPOINTMENT_STATUS_NO_SHOW,
}
REMINDER_STATUS_DB_TO_PROTO = {
    "NOT_REQUESTED": rendezvous_pb2.REMINDER_STATUS_NOT_REQUESTED,
    "PENDING": rendezvous_pb2.REMINDER_STATUS_PENDING,
    "SENT": rendezvous_pb2.REMINDER_STATUS_SENT,
    "FAILED": rendezvous_pb2.REMINDER_STATUS_FAILED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_timestamp(value: datetime | None) -> Timestamp:
    result = Timestamp()
    if value is not None:
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        result.FromDatetime(aware)
    return result


def from_timestamp(value: Timestamp, context, field_name: str, *, required: bool = True) -> datetime | None:
    if value is None or (value.seconds == 0 and value.nanos == 0):
        if required:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"{field_name} is required.")
        return None
    try:
        return value.ToDatetime(tzinfo=timezone.utc).replace(tzinfo=None)
    except Exception:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"{field_name} is invalid.")


def generate_number(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def auth_metadata(context):
    for item in context.invocation_metadata():
        if item.key.lower() == "authorization":
            return (("authorization", item.value),)
    return tuple()


def slot_to_proto(item: ScheduleSlot):
    return rendezvous_pb2.ScheduleSlot(
        id=item.id, provider_id=item.provider_id, service=item.service,
        start_at=to_timestamp(item.start_at), end_at=to_timestamp(item.end_at),
        status=SLOT_STATUS_DB_TO_PROTO.get(item.status, rendezvous_pb2.SCHEDULE_SLOT_STATUS_UNSPECIFIED),
        created_at=to_timestamp(item.created_at),
    )


def appointment_to_proto(item: Appointment):
    return rendezvous_pb2.Appointment(
        id=item.id, appointment_number=item.appointment_number, patient_id=item.patient_id,
        provider_id=item.provider_id, service=item.service, reason=item.reason,
        status=APPOINTMENT_STATUS_DB_TO_PROTO.get(item.status, rendezvous_pb2.APPOINTMENT_STATUS_UNSPECIFIED),
        slot=slot_to_proto(item.slot), cancellation_reason=item.cancellation_reason or "",
        arrival_id=item.arrival_id or "",
        reminder_status=REMINDER_STATUS_DB_TO_PROTO.get(item.reminder_status, rendezvous_pb2.REMINDER_STATUS_UNSPECIFIED),
        reminder_recipient_user_id=item.reminder_recipient_user_id or "",
        correlation_id=item.correlation_id,
        created_at=to_timestamp(item.created_at), updated_at=to_timestamp(item.updated_at),
        checked_in_at=to_timestamp(item.checked_in_at), completed_at=to_timestamp(item.completed_at),
        reminder_due_at=to_timestamp(item.reminder_due_at), reminder_sent_at=to_timestamp(item.reminder_sent_at),
    )


def build_health_response(desired: str, message: str):
    return build_health_response_compat("rendezvous", desired, message, SERVICE_VERSION)

def validate_patient(context, patient_id: str):
    try:
        with grpc.insecure_channel(ACCUEIL_GRPC_TARGET) as channel:
            stub = accueil_pb2_grpc.AccueilServiceStub(channel)
            return stub.GetPatient(
                accueil_pb2.GetPatientRequest(patient_id=patient_id),
                metadata=auth_metadata(context), timeout=3,
            ).patient
    except grpc.RpcError as error:
        if error.code() == grpc.StatusCode.NOT_FOUND:
            context.abort(grpc.StatusCode.NOT_FOUND, "Patient not found in Accueil.")
        if error.code() in (grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED):
            context.abort(error.code(), error.details() or "Patient validation denied.")
        context.abort(grpc.StatusCode.UNAVAILABLE, f"Accueil service unavailable: {error.code().name}")


def reminder_due_for(slot_start: datetime, lead_minutes: int | None = None) -> datetime:
    lead = lead_minutes if lead_minutes and lead_minutes > 0 else RENDEZVOUS_REMINDER_LEAD_MINUTES
    lead = min(max(int(lead), 5), 60 * 24 * 30)
    due = slot_start - timedelta(minutes=lead)
    return max(due, utc_now())


def dispatch_due_reminders_once(limit: int = 50) -> tuple[int, int]:
    """Best-effort timed reminder dispatch. Never mutates appointment business status."""
    session = RendezvousSessionLocal()
    sent = failed = 0
    try:
        now = utc_now()
        items = session.scalars(
            select(Appointment)
            .join(ScheduleSlot)
            .where(
                Appointment.reminder_requested.is_(True),
                Appointment.reminder_recipient_user_id.is_not(None),
                Appointment.reminder_status.in_(("PENDING", "FAILED")),
                Appointment.reminder_due_at.is_not(None),
                Appointment.reminder_due_at <= now,
                Appointment.status.in_(("BOOKED", "CONFIRMED")),
                ScheduleSlot.start_at > now,
            )
            .order_by(Appointment.reminder_due_at)
            .limit(max(1, min(int(limit), 200)))
        ).all()
        for item in items:
            _ = item.slot
            ok = send_system_notification(
                auth_target=AUTH_GRPC_TARGET,
                recipient_id=item.reminder_recipient_user_id or "",
                notification_type="APPOINTMENT_REMINDER",
                title="Rappel de rendez-vous / Appointment reminder",
                body=(f"Rendez-vous {item.appointment_number} / Appointment {item.appointment_number} "
                      f"prévu le / scheduled for {item.slot.start_at.isoformat()} UTC."),
                source_service="rendezvous",
                correlation_id=item.correlation_id or "",
            )
            if ok:
                item.reminder_status = "SENT"
                item.reminder_sent_at = now
                item.reminder_error = None
                sent += 1
            else:
                item.reminder_status = "FAILED"
                item.reminder_error = "Notification delivery failed; worker will retry before the appointment."
                failed += 1
        if items:
            session.commit()
        return sent, failed
    except Exception:
        session.rollback()
        logger.exception("Timed appointment reminder dispatch failed")
        return sent, failed + 1
    finally:
        session.close()


def record_event(session, appointment: Appointment, actor_id: str, event_type: str,
                 *, from_status: str | None = None, to_status: str | None = None,
                 old_slot_id: str | None = None, new_slot_id: str | None = None,
                 reason: str | None = None):
    session.add(AppointmentEvent(
        appointment_id=appointment.id, event_type=event_type,
        from_status=from_status, to_status=to_status,
        old_slot_id=old_slot_id, new_slot_id=new_slot_id,
        reason=reason, actor_id=actor_id,
    ))


class RendezvousService(rendezvous_pb2_grpc.RendezvousServiceServicer):
    def CreateScheduleSlot(self, request, context):
        actor = require_permission(context, "appointment.manage")
        provider_id=request.provider_id.strip(); service=request.service.strip().upper(); idem=request.idempotency_key.strip()
        start=from_timestamp(request.start_at, context, "start_at"); end=from_timestamp(request.end_at, context, "end_at")
        if not provider_id or not service or not idem:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "provider_id, service and idempotency_key are required.")
        if end <= start:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "end_at must be after start_at.")
        session=RendezvousSessionLocal()
        try:
            existing=get_slot_by_idempotency(session, idem)
            if existing is not None:
                return rendezvous_pb2.ScheduleSlotResponse(slot=slot_to_proto(existing))
            overlap=session.scalar(select(ScheduleSlot).where(
                ScheduleSlot.provider_id==provider_id,
                ScheduleSlot.status!="BLOCKED",
                ScheduleSlot.start_at < end,
                ScheduleSlot.end_at > start,
            ).limit(1))
            if overlap is not None:
                context.abort(grpc.StatusCode.ALREADY_EXISTS, "Provider already has an overlapping schedule slot.")
            item=ScheduleSlot(provider_id=provider_id,service=service,start_at=start,end_at=end,status="AVAILABLE",idempotency_key=idem)
            session.add(item); session.commit(); session.refresh(item)
            logger.info("rpc=CreateScheduleSlot peer=%s actor=%s slot=%s provider=%s outcome=OK",context.peer(),actor.id,item.id,provider_id)
            return rendezvous_pb2.ScheduleSlotResponse(slot=slot_to_proto(item))
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.ALREADY_EXISTS,"Schedule slot already exists.")
        finally: session.close()

    def UpdateScheduleSlot(self, request, context):
        actor = require_permission(context, "appointment.manage")
        slot_id=request.slot_id.strip(); provider=request.provider_id.strip(); service=request.service.strip().upper(); reason=request.reason.strip()
        start=from_timestamp(request.start_at, context, "start_at"); end=from_timestamp(request.end_at, context, "end_at")
        if not slot_id or not provider or not service or not reason:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "slot_id, provider_id, service and reason are required.")
        if end <= start:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "end_at must be after start_at.")
        session=RendezvousSessionLocal()
        try:
            item=session.scalar(select(ScheduleSlot).where(ScheduleSlot.id==slot_id).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND, "Schedule slot not found.")
            if item.status != "AVAILABLE": context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Only AVAILABLE slots can be updated.")
            overlap=session.scalar(select(ScheduleSlot).where(
                ScheduleSlot.id!=item.id, ScheduleSlot.provider_id==provider, ScheduleSlot.status!="BLOCKED",
                ScheduleSlot.start_at < end, ScheduleSlot.end_at > start,
            ).limit(1))
            if overlap is not None: context.abort(grpc.StatusCode.ALREADY_EXISTS, "Provider already has an overlapping schedule slot.")
            old=f"{item.provider_id}|{item.service}|{item.start_at.isoformat()}|{item.end_at.isoformat()}"
            item.provider_id=provider; item.service=service; item.start_at=start; item.end_at=end
            session.commit(); session.refresh(item)
            logger.info("rpc=UpdateScheduleSlot peer=%s actor=%s slot=%s reason=%s old=%s outcome=OK",context.peer(),actor.id,item.id,reason,old)
            return rendezvous_pb2.ScheduleSlotResponse(slot=slot_to_proto(item))
        finally: session.close()

    def BlockScheduleSlot(self, request, context):
        actor=require_permission(context, "appointment.manage")
        slot_id=request.slot_id.strip(); reason=request.reason.strip()
        if not slot_id or not reason: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "slot_id and reason are required.")
        session=RendezvousSessionLocal()
        try:
            item=session.scalar(select(ScheduleSlot).where(ScheduleSlot.id==slot_id).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND, "Schedule slot not found.")
            if item.status=="BOOKED": context.abort(grpc.StatusCode.FAILED_PRECONDITION, "A booked slot cannot be blocked. Cancel/reschedule the appointment first.")
            if item.status=="BLOCKED": return rendezvous_pb2.ScheduleSlotResponse(slot=slot_to_proto(item))
            item.status="BLOCKED"; session.commit(); session.refresh(item)
            logger.info("rpc=BlockScheduleSlot peer=%s actor=%s slot=%s reason=%s outcome=OK",context.peer(),actor.id,item.id,reason)
            return rendezvous_pb2.ScheduleSlotResponse(slot=slot_to_proto(item))
        finally: session.close()

    def ListAvailableSlots(self, request, context):
        actor=require_permission(context,"appointment.read")
        provider=request.provider_id.strip(); service=request.service.strip().upper()
        from_at=from_timestamp(request.from_at, context, "from_at", required=False)
        to_at=from_timestamp(request.to_at, context, "to_at", required=False)
        limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
        session=RendezvousSessionLocal()
        try:
            filters=[ScheduleSlot.status=="AVAILABLE"]
            if provider: filters.append(ScheduleSlot.provider_id==provider)
            if service: filters.append(ScheduleSlot.service==service)
            if from_at: filters.append(ScheduleSlot.start_at>=from_at)
            if to_at: filters.append(ScheduleSlot.start_at<to_at)
            total=session.scalar(select(func.count()).select_from(ScheduleSlot).where(*filters)) or 0
            items=session.scalars(select(ScheduleSlot).where(*filters).order_by(ScheduleSlot.start_at).limit(limit).offset(offset)).all()
            logger.info("rpc=ListAvailableSlots peer=%s actor=%s count=%s outcome=OK",context.peer(),actor.id,len(items))
            return rendezvous_pb2.ListAvailableSlotsResponse(slots=[slot_to_proto(x) for x in items],total=total)
        finally: session.close()

    def CreateAppointment(self, request, context):
        actor=require_permission(context,"appointment.manage")
        patient_id=request.patient_id.strip(); slot_id=request.slot_id.strip(); reason=request.reason.strip(); idem=request.idempotency_key.strip()
        correlation=(request.correlation_id.strip() or str(uuid.uuid4()))
        if not patient_id or not slot_id or not reason or not idem:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,"patient_id, slot_id, reason and idempotency_key are required.")
        if request.request_reminder and not request.reminder_recipient_user_id.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,"reminder_recipient_user_id is required when request_reminder=true because patient-to-Auth identity mapping is not implicit.")
        validate_patient(context, patient_id)
        session=RendezvousSessionLocal()
        try:
            existing=get_appointment_by_idempotency(session, idem)
            if existing is not None:
                return rendezvous_pb2.CreateAppointmentResponse(appointment=appointment_to_proto(existing),replayed=True)
            slot=get_slot(session, slot_id, for_update=True)
            if slot is None: context.abort(grpc.StatusCode.NOT_FOUND,"Schedule slot not found.")
            if slot.status!="AVAILABLE": context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Schedule slot is not available.")
            if slot.start_at <= utc_now(): context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Cannot book a past schedule slot.")
            item=Appointment(
                appointment_number=generate_number("RDV"),patient_id=patient_id,provider_id=slot.provider_id,
                service=slot.service,reason=reason,status="BOOKED",slot_id=slot.id,active_slot_key=slot.id,
                idempotency_key=idem,correlation_id=correlation,created_by=actor.id,
                reminder_requested=bool(request.request_reminder),
                reminder_recipient_user_id=request.reminder_recipient_user_id.strip() or None,
                reminder_status="PENDING" if request.request_reminder else "NOT_REQUESTED",
                reminder_due_at=(reminder_due_for(slot.start_at, request.reminder_lead_minutes) if request.request_reminder else None),
            )
            slot.status="BOOKED"; session.add(item); session.flush()
            record_event(session,item,actor.id,"CREATED",to_status="BOOKED",new_slot_id=slot.id)
            session.commit(); saved=get_appointment(session,item.id)
            logger.info("rpc=CreateAppointment peer=%s actor=%s appointment=%s patient=%s reminder_due=%s outcome=OK",context.peer(),actor.id,saved.id,patient_id,saved.reminder_due_at)
            return rendezvous_pb2.CreateAppointmentResponse(appointment=appointment_to_proto(saved),replayed=False)
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Schedule slot was booked concurrently or idempotency key already exists.")
        finally: session.close()

    def GetAppointment(self, request, context):
        require_permission(context,"appointment.read")
        session=RendezvousSessionLocal()
        try:
            item=get_appointment(session,request.appointment_id.strip()) if request.appointment_id.strip() else get_appointment_by_number(session,request.appointment_number.strip())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Appointment not found.")
            return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(item))
        finally: session.close()

    def ListAgenda(self, request, context):
        actor=require_permission(context,"appointment.read")
        provider=request.provider_id.strip(); service=request.service.strip().upper()
        from_at=from_timestamp(request.from_at, context, "from_at", required=False)
        to_at=from_timestamp(request.to_at, context, "to_at", required=False)
        limit=min(max(request.limit or 100,1),300); offset=max(request.offset,0)
        session=RendezvousSessionLocal()
        try:
            filters=[]
            if provider: filters.append(Appointment.provider_id==provider)
            if service: filters.append(Appointment.service==service)
            stmt=select(Appointment).join(ScheduleSlot).options()
            if from_at: filters.append(ScheduleSlot.start_at>=from_at)
            if to_at: filters.append(ScheduleSlot.start_at<to_at)
            total=session.scalar(select(func.count()).select_from(Appointment).join(ScheduleSlot).where(*filters)) or 0
            items=session.scalars(select(Appointment).join(ScheduleSlot).where(*filters).order_by(ScheduleSlot.start_at).limit(limit).offset(offset)).all()
            # Load slot relation safely in this session.
            for item in items: _ = item.slot
            logger.info("rpc=ListAgenda peer=%s actor=%s count=%s outcome=OK",context.peer(),actor.id,len(items))
            return rendezvous_pb2.ListAgendaResponse(appointments=[appointment_to_proto(x) for x in items],total=total)
        finally: session.close()

    def ListPatientAppointments(self, request, context):
        actor=require_permission(context, "appointment.read")
        patient_id=request.patient_id.strip(); limit=min(max(request.limit or 100,1),300); offset=max(request.offset,0)
        if not patient_id: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "patient_id is required.")
        session=RendezvousSessionLocal()
        try:
            filters=[Appointment.patient_id==patient_id]
            if request.status != rendezvous_pb2.APPOINTMENT_STATUS_UNSPECIFIED:
                desired = next((db for db,proto in APPOINTMENT_STATUS_DB_TO_PROTO.items() if proto==request.status), None)
                if desired is None: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid appointment status.")
                filters.append(Appointment.status==desired)
            total=session.scalar(select(func.count()).select_from(Appointment).where(*filters)) or 0
            items=session.scalars(select(Appointment).join(ScheduleSlot).where(*filters).order_by(ScheduleSlot.start_at.desc()).limit(limit).offset(offset)).all()
            for item in items: _=item.slot
            logger.info("rpc=ListPatientAppointments peer=%s actor=%s patient=%s count=%s outcome=OK",context.peer(),actor.id,patient_id,len(items))
            return rendezvous_pb2.ListAgendaResponse(appointments=[appointment_to_proto(x) for x in items],total=int(total))
        finally: session.close()

    def ConfirmAppointment(self, request, context):
        actor=require_permission(context,"appointment.manage")
        session=RendezvousSessionLocal()
        try:
            item=session.scalar(select(Appointment).where(Appointment.id==request.appointment_id.strip()).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Appointment not found.")
            if item.status=="CONFIRMED":
                _=item.slot; return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(item))
            if item.status!="BOOKED": context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Only BOOKED appointments can be confirmed.")
            old=item.status; item.status="CONFIRMED"; record_event(session,item,actor.id,"CONFIRMED",from_status=old,to_status=item.status)
            session.commit(); saved=get_appointment(session,item.id)
            return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(saved))
        finally: session.close()

    def RescheduleAppointment(self, request, context):
        actor=require_permission(context,"appointment.manage")
        appointment_id=request.appointment_id.strip(); new_slot_id=request.new_slot_id.strip(); idem=request.idempotency_key.strip(); reason=request.reason.strip()
        if not appointment_id or not new_slot_id or not idem: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"appointment_id, new_slot_id and idempotency_key are required.")
        session=RendezvousSessionLocal()
        try:
            item=session.scalar(select(Appointment).where(Appointment.id==appointment_id).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Appointment not found.")
            if item.last_reschedule_key==idem:
                _=item.slot; return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(item))
            if item.status not in {"BOOKED","CONFIRMED"}: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Only BOOKED or CONFIRMED appointments can be rescheduled.")
            old_slot=get_slot(session,item.slot_id,for_update=True); new_slot=get_slot(session,new_slot_id,for_update=True)
            if new_slot is None: context.abort(grpc.StatusCode.NOT_FOUND,"New schedule slot not found.")
            if new_slot.status!="AVAILABLE": context.abort(grpc.StatusCode.FAILED_PRECONDITION,"New schedule slot is not available.")
            if new_slot.provider_id != item.provider_id: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"New slot must belong to the same provider for this MVP.")
            if new_slot.service != item.service: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"New slot must belong to the same service.")
            old_id=item.slot_id
            old_slot.status="AVAILABLE"; new_slot.status="BOOKED"
            item.slot_id=new_slot.id; item.active_slot_key=new_slot.id; item.last_reschedule_key=idem; item.updated_at=utc_now()
            if item.reminder_requested and item.reminder_recipient_user_id:
                item.reminder_due_at=reminder_due_for(new_slot.start_at)
                item.reminder_sent_at=None
                item.reminder_status="PENDING"; item.reminder_error=None
            record_event(session,item,actor.id,"RESCHEDULED",from_status=item.status,to_status=item.status,old_slot_id=old_id,new_slot_id=new_slot.id,reason=reason or None)
            session.commit(); saved=get_appointment(session,item.id)
            logger.info("rpc=RescheduleAppointment peer=%s actor=%s appointment=%s outcome=OK",context.peer(),actor.id,item.id)
            return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(saved))
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.FAILED_PRECONDITION,"New slot was booked concurrently.")
        finally: session.close()

    def CancelAppointment(self, request, context):
        actor=require_permission(context,"appointment.manage")
        appointment_id=request.appointment_id.strip(); reason=request.reason.strip(); idem=request.idempotency_key.strip()
        if not reason or not idem: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"reason and idempotency_key are required.")
        session=RendezvousSessionLocal()
        try:
            item=session.scalar(select(Appointment).where(Appointment.id==appointment_id).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Appointment not found.")
            if item.status=="CANCELLED" and item.cancel_idempotency_key==idem:
                _=item.slot; return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(item))
            if item.status not in {"BOOKED","CONFIRMED"}: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Appointment can no longer be cancelled.")
            slot=get_slot(session,item.slot_id,for_update=True); old=item.status
            item.status="CANCELLED"; item.cancellation_reason=reason; item.cancel_idempotency_key=idem; item.active_slot_key=None; item.updated_at=utc_now()
            if item.reminder_status in {"PENDING","FAILED"}: item.reminder_status="NOT_REQUESTED"; item.reminder_error=None
            if slot and slot.start_at > utc_now(): slot.status="AVAILABLE"
            record_event(session,item,actor.id,"CANCELLED",from_status=old,to_status="CANCELLED",old_slot_id=item.slot_id,reason=reason)
            session.commit(); saved=get_appointment(session,item.id)
            return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(saved))
        finally: session.close()

    def MarkCheckedIn(self, request, context):
        actor=require_permission(context,"appointment.manage")
        appointment_id=request.appointment_id.strip(); idem=request.idempotency_key.strip()
        if not appointment_id or not idem: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"appointment_id and idempotency_key are required.")
        session=RendezvousSessionLocal()
        try:
            item=session.scalar(select(Appointment).where(Appointment.id==appointment_id).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Appointment not found.")
            if item.status=="CHECKED_IN" and item.checkin_idempotency_key==idem:
                _=item.slot; return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(item))
            if item.status not in {"BOOKED","CONFIRMED"}: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Appointment cannot be checked in from its current state.")
            try:
                with grpc.insecure_channel(ACCUEIL_GRPC_TARGET) as channel:
                    stub=accueil_pb2_grpc.AccueilServiceStub(channel)
                    arrival=stub.RegisterArrival(
                        accueil_pb2.RegisterArrivalRequest(
                            patient_id=item.patient_id, reason=f"Rendez-vous {item.appointment_number}: {item.reason}",
                            target_service=item.service, priority=accueil_pb2.ARRIVAL_PRIORITY_ROUTINE,
                        ), metadata=auth_metadata(context), timeout=5,
                    ).arrival
            except grpc.RpcError as error:
                context.abort(grpc.StatusCode.UNAVAILABLE,f"Accueil check-in failed: {error.code().name}")
            old=item.status; item.status="CHECKED_IN"; item.arrival_id=arrival.id; item.checkin_idempotency_key=idem; item.checked_in_at=utc_now(); item.updated_at=utc_now()
            record_event(session,item,actor.id,"CHECKED_IN",from_status=old,to_status="CHECKED_IN",reason=f"arrival_id={arrival.id}")
            session.commit(); saved=get_appointment(session,item.id)
            logger.info("rpc=MarkCheckedIn peer=%s actor=%s appointment=%s arrival=%s outcome=OK",context.peer(),actor.id,item.id,arrival.id)
            return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(saved))
        finally: session.close()

    def CompleteAppointment(self, request, context):
        actor=require_permission(context,"appointment.manage")
        session=RendezvousSessionLocal()
        try:
            item=session.scalar(select(Appointment).where(Appointment.id==request.appointment_id.strip()).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Appointment not found.")
            if item.status=="COMPLETED":
                _=item.slot; return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(item))
            if item.status!="CHECKED_IN": context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Only CHECKED_IN appointments can be completed.")
            old=item.status; item.status="COMPLETED"; item.active_slot_key=None; item.completed_at=utc_now(); item.updated_at=utc_now()
            record_event(session,item,actor.id,"COMPLETED",from_status=old,to_status="COMPLETED")
            session.commit(); saved=get_appointment(session,item.id)
            return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(saved))
        finally: session.close()

    def MarkNoShow(self, request, context):
        actor=require_permission(context, "appointment.manage")
        appointment_id=request.appointment_id.strip(); reason=request.reason.strip()
        if not appointment_id or not reason: context.abort(grpc.StatusCode.INVALID_ARGUMENT, "appointment_id and reason are required.")
        session=RendezvousSessionLocal()
        try:
            item=session.scalar(select(Appointment).where(Appointment.id==appointment_id).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND, "Appointment not found.")
            _=item.slot
            if item.status=="NO_SHOW": return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(item))
            if item.status not in {"BOOKED","CONFIRMED"}: context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Only BOOKED or CONFIRMED appointments can become NO_SHOW.")
            if item.slot.end_at > utc_now(): context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Appointment cannot be marked NO_SHOW before its slot has ended.")
            old=item.status; item.status="NO_SHOW"; item.active_slot_key=None; item.updated_at=utc_now()
            if item.reminder_status in {"PENDING","FAILED"}: item.reminder_status="NOT_REQUESTED"; item.reminder_error=None
            record_event(session,item,actor.id,"NO_SHOW",from_status=old,to_status="NO_SHOW",reason=reason)
            session.commit(); saved=get_appointment(session,item.id)
            logger.info("rpc=MarkNoShow peer=%s actor=%s appointment=%s outcome=OK",context.peer(),actor.id,item.id)
            return rendezvous_pb2.AppointmentResponse(appointment=appointment_to_proto(saved))
        finally: session.close()

    def HealthCheck(self, request, context):
        try:
            with engine.connect() as connection: connection.execute(text("SELECT 1"))
            return build_health_response("ONLINE","Rendezvous service and MySQL are available.")
        except Exception:
            logger.exception("rpc=HealthCheck peer=%s outcome=DEGRADED",context.peer())
            return build_health_response("DEGRADED","Rendezvous service is running but MySQL is unavailable.")
