from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload
from services.hospitalisation.models import Admission, Bed, Room, Transfer, Ward


def admission_options():
    return (joinedload(Admission.current_bed).joinedload(Bed.room).joinedload(Room.ward),)


def get_admission(session: Session, admission_id: str):
    return session.scalar(select(Admission).options(*admission_options()).where(Admission.id == admission_id))


def get_admission_by_key(session: Session, key: str):
    return session.scalar(select(Admission).options(*admission_options()).where(Admission.idempotency_key == key))


def get_current_admission(session: Session, patient_id: str):
    return session.scalar(select(Admission).options(*admission_options()).where(Admission.active_patient_key == patient_id))


def get_bed(session: Session, bed_id: str):
    return session.scalar(select(Bed).options(joinedload(Bed.room).joinedload(Room.ward)).where(Bed.id == bed_id))


def get_transfer_by_key(session: Session, key: str):
    return session.scalar(
        select(Transfer)
        .options(joinedload(Transfer.from_bed), joinedload(Transfer.to_bed))
        .where(Transfer.idempotency_key == key)
    )


def list_beds(session: Session, ward_code: str, available_only: bool):
    stmt = select(Bed).options(joinedload(Bed.room).joinedload(Room.ward)).join(Room).join(Ward).order_by(Ward.code, Room.code, Bed.code)
    if ward_code:
        stmt = stmt.where(Ward.code == ward_code)
    if available_only:
        stmt = stmt.where(Bed.status == "AVAILABLE")
    return list(session.scalars(stmt).unique().all())
