from sqlalchemy import select
from sqlalchemy.orm import Session,selectinload
from services.maternite.models import Pregnancy,Delivery,Newborn

def pregnancy_options(stmt):
    return stmt.options(
        selectinload(Pregnancy.prenatal_visits),
        selectinload(Pregnancy.labor_events),
        selectinload(Pregnancy.deliveries).selectinload(Delivery.newborns),
    )
def get_pregnancy(session: Session,pregnancy_id: str):
    return session.scalar(pregnancy_options(select(Pregnancy).where(Pregnancy.id==pregnancy_id)))
def get_active_by_patient(session: Session,patient_id: str):
    return session.scalar(pregnancy_options(select(Pregnancy).where(Pregnancy.active_patient_key==patient_id)))
def get_latest_by_patient(session: Session,patient_id: str):
    return session.scalar(pregnancy_options(select(Pregnancy).where(Pregnancy.patient_id==patient_id).order_by(Pregnancy.created_at.desc()).limit(1)))
def get_delivery(session: Session,delivery_id: str):
    return session.scalar(select(Delivery).options(selectinload(Delivery.newborns)).where(Delivery.id==delivery_id))
