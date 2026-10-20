from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.department import DepartmentRead


class DoctorBase(BaseModel):
    name: str
    department_id: int
    specialty: str
    qualifications: str
    experience: str
    consultation_fee: Decimal
    room_number: str
    is_active: bool = True


class DoctorCreate(DoctorBase):
    pass


class DoctorRead(DoctorBase):
    id: int
    created_at: datetime
    department: Optional[DepartmentRead] = None

    model_config = ConfigDict(from_attributes=True)


class SlotInfo(BaseModel):
    start_time: str
    end_time: str
    is_available: bool


class DoctorAvailabilityResponse(BaseModel):
    doctor_id: int
    doctor_name: str
    date: str
    is_on_duty: bool
    working_hours: Optional[str] = None
    available_slots: list[SlotInfo]
