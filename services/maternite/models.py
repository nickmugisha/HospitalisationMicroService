from __future__ import annotations
import uuid
from datetime import datetime,timezone
from sqlalchemy import DateTime,ForeignKey,Integer,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column,relationship
from database.maternite_base import MaterniteBase

def uid(): return str(uuid.uuid4())
def utc_now(): return datetime.now(timezone.utc).replace(tzinfo=None)

class Pregnancy(MaterniteBase):
    __tablename__="pregnancies"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    pregnancy_number: Mapped[str]=mapped_column(String(60),unique=True,index=True,nullable=False)
    patient_id: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    active_patient_key: Mapped[str|None]=mapped_column(String(36),unique=True,index=True,nullable=True)
    consultation_id: Mapped[str|None]=mapped_column(String(36),index=True,nullable=True)
    gravida: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    para: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    lmp_date: Mapped[str|None]=mapped_column(String(10),nullable=True)
    edd: Mapped[str|None]=mapped_column(String(10),nullable=True)
    risk_level: Mapped[str]=mapped_column(String(20),nullable=False,default="LOW")
    risk_factors: Mapped[str|None]=mapped_column(Text,nullable=True)
    referral_reason: Mapped[str|None]=mapped_column(Text,nullable=True)
    status: Mapped[str]=mapped_column(String(20),index=True,nullable=False,default="ACTIVE")
    correlation_id: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    idempotency_key: Mapped[str]=mapped_column(String(160),unique=True,index=True,nullable=False)
    created_by: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utc_now)
    updated_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utc_now,onupdate=utc_now)
    labor_admitted_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    labor_admit_key: Mapped[str|None]=mapped_column(String(160),unique=True,nullable=True)
    prenatal_visits: Mapped[list['PrenatalVisit']]=relationship(back_populates='pregnancy',cascade='all, delete-orphan',order_by='PrenatalVisit.visit_at')
    labor_events: Mapped[list['LaborEvent']]=relationship(back_populates='pregnancy',cascade='all, delete-orphan',order_by='LaborEvent.event_at')
    deliveries: Mapped[list['Delivery']]=relationship(back_populates='pregnancy',cascade='all, delete-orphan',order_by='Delivery.delivered_at')

class PrenatalVisit(MaterniteBase):
    __tablename__="prenatal_visits"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    pregnancy_id: Mapped[str]=mapped_column(String(36),ForeignKey('pregnancies.id',ondelete='CASCADE'),index=True,nullable=False)
    visit_at: Mapped[datetime]=mapped_column(DateTime,index=True,nullable=False)
    gestational_age_weeks: Mapped[int]=mapped_column(Integer,nullable=False)
    observations: Mapped[str|None]=mapped_column(Text,nullable=True)
    systolic_bp: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    diastolic_bp: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    weight_kg_x100: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    fetal_heart_bpm: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    recorded_by: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    idempotency_key: Mapped[str]=mapped_column(String(160),unique=True,index=True,nullable=False)
    pregnancy: Mapped[Pregnancy]=relationship(back_populates='prenatal_visits')

class LaborEvent(MaterniteBase):
    __tablename__="labor_events"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    pregnancy_id: Mapped[str]=mapped_column(String(36),ForeignKey('pregnancies.id',ondelete='CASCADE'),index=True,nullable=False)
    event_type: Mapped[str]=mapped_column(String(30),index=True,nullable=False)
    event_at: Mapped[datetime]=mapped_column(DateTime,index=True,nullable=False)
    description: Mapped[str|None]=mapped_column(Text,nullable=True)
    cervical_dilation_x10: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    fetal_heart_bpm: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    recorded_by: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    idempotency_key: Mapped[str]=mapped_column(String(160),unique=True,index=True,nullable=False)
    pregnancy: Mapped[Pregnancy]=relationship(back_populates='labor_events')

class Delivery(MaterniteBase):
    __tablename__="deliveries"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    delivery_number: Mapped[str]=mapped_column(String(60),unique=True,index=True,nullable=False)
    pregnancy_id: Mapped[str]=mapped_column(String(36),ForeignKey('pregnancies.id',ondelete='RESTRICT'),index=True,nullable=False)
    patient_id: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    delivered_at: Mapped[datetime]=mapped_column(DateTime,index=True,nullable=False)
    mode: Mapped[str]=mapped_column(String(30),nullable=False)
    outcome: Mapped[str]=mapped_column(String(30),nullable=False)
    complications: Mapped[str|None]=mapped_column(Text,nullable=True)
    attendant_id: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    idempotency_key: Mapped[str]=mapped_column(String(160),unique=True,index=True,nullable=False)
    billing_status: Mapped[str]=mapped_column(String(30),index=True,nullable=False,default='PENDING_DELIVERY')
    billing_charge_id: Mapped[str|None]=mapped_column(String(36),nullable=True)
    billed_amount_minor: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    currency_code: Mapped[str]=mapped_column(String(3),nullable=False,default='BIF')
    created_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utc_now)
    pregnancy: Mapped[Pregnancy]=relationship(back_populates='deliveries')
    newborns: Mapped[list['Newborn']]=relationship(back_populates='delivery',cascade='all, delete-orphan',order_by='Newborn.created_at')

class Newborn(MaterniteBase):
    __tablename__="newborns"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    newborn_number: Mapped[str]=mapped_column(String(60),unique=True,index=True,nullable=False)
    delivery_id: Mapped[str]=mapped_column(String(36),ForeignKey('deliveries.id',ondelete='CASCADE'),index=True,nullable=False)
    mother_patient_id: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    sex: Mapped[str]=mapped_column(String(20),nullable=False)
    weight_g: Mapped[int]=mapped_column(Integer,nullable=False)
    apgar_1: Mapped[int]=mapped_column(Integer,nullable=False)
    apgar_5: Mapped[int]=mapped_column(Integer,nullable=False)
    status: Mapped[str]=mapped_column(String(20),nullable=False)
    registered_by: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    idempotency_key: Mapped[str]=mapped_column(String(160),unique=True,index=True,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utc_now)
    delivery: Mapped[Delivery]=relationship(back_populates='newborns')

class BillingOutbox(MaterniteBase):
    __tablename__="billing_outbox"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    delivery_id: Mapped[str]=mapped_column(String(36),index=True,unique=True,nullable=False)
    patient_id: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    amount_minor: Mapped[int]=mapped_column(Integer,nullable=False)
    currency_code: Mapped[str]=mapped_column(String(3),nullable=False)
    correlation_id: Mapped[str]=mapped_column(String(36),index=True,nullable=False)
    idempotency_key: Mapped[str]=mapped_column(String(160),unique=True,index=True,nullable=False)
    status: Mapped[str]=mapped_column(String(30),index=True,nullable=False,default='PENDING_DELIVERY')
    billing_charge_id: Mapped[str|None]=mapped_column(String(36),nullable=True)
    last_error: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utc_now)
    updated_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utc_now,onupdate=utc_now)
