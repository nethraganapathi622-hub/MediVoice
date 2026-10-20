from datetime import date, datetime, time
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.patient import PatientRead
from app.schemas.doctor import DoctorRead
from app.schemas.department import DepartmentRead


class AppointmentBase(BaseModel):
    doctor_id: int
    department_id: int
    appointment_date: date
    start_time: time
    appointment_type: str = "Consultation"
    notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    patient_id: Optional[int] = None
    patient_name: str = Field(..., min_length=2, max_length=150)
    patient_phone: Optional[str] = None
    patient_email: Optional[str] = None


class AppointmentReschedule(BaseModel):
    new_date: date
    new_start_time: time


class AppointmentCancel(BaseModel):
    reason: Optional[str] = None


class AppointmentRead(BaseModel):
    id: int
    booking_reference: str
    patient_id: int
    doctor_id: int
    department_id: int
    appointment_date: date
    start_time: time
    end_time: time
    status: str
    appointment_type: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    patient: Optional[PatientRead] = None
    doctor: Optional[DoctorRead] = None
    department: Optional[DepartmentRead] = None
    queue_token: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
