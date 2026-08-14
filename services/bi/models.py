from __future__ import annotations
import uuid
from datetime import datetime,timezone
from sqlalchemy import BigInteger,DateTime,String,Text
from sqlalchemy.orm import Mapped,mapped_column
from database.bi_base import BIBase

def uid(): return str(uuid.uuid4())
def utc_now(): return datetime.now(timezone.utc).replace(tzinfo=None)

class MetricSnapshot(BIBase):
    __tablename__='metric_snapshots'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    metric_code: Mapped[str]=mapped_column(String(100),nullable=False,index=True)
    period_start: Mapped[str|None]=mapped_column(String(10),nullable=True,index=True)
    period_end: Mapped[str|None]=mapped_column(String(10),nullable=True,index=True)
    value: Mapped[int]=mapped_column(BigInteger,nullable=False)
    dimensions: Mapped[str|None]=mapped_column(Text,nullable=True)
    source_service: Mapped[str]=mapped_column(String(80),nullable=False,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(),nullable=False,default=utc_now,index=True)

class ReportRun(BIBase):
    __tablename__='report_runs'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    requested_by: Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    date_from: Mapped[str|None]=mapped_column(String(10),nullable=True)
    date_to: Mapped[str|None]=mapped_column(String(10),nullable=True)
    service_filter: Mapped[str|None]=mapped_column(String(80),nullable=True)
    quality: Mapped[str]=mapped_column(String(30),nullable=False,index=True)
    warnings: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(),nullable=False,default=utc_now,index=True)
