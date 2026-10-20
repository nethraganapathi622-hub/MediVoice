"""Pydantic schemas package for MediVoice."""

from app.schemas.department import DepartmentRead, DepartmentCreate
from app.schemas.doctor import DoctorRead, DoctorCreate, DoctorAvailabilityResponse
from app.schemas.schedule import DoctorScheduleRead, DoctorScheduleCreate
from app.schemas.patient import PatientRead, PatientCreate
from app.schemas.appointment import (
    AppointmentRead,
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentCancel,
)
from app.schemas.queue import QueueEntryRead, QueueCheckInRequest
from app.schemas.alert import AlertRead, AlertCreate, AlertAcknowledgeRequest

__all__ = [
    "DepartmentRead",
    "DepartmentCreate",
    "DoctorRead",
    "DoctorCreate",
    "DoctorAvailabilityResponse",
    "DoctorScheduleRead",
    "DoctorScheduleCreate",
    "PatientRead",
    "PatientCreate",
    "AppointmentRead",
    "AppointmentCreate",
    "AppointmentReschedule",
    "AppointmentCancel",
    "QueueEntryRead",
    "QueueCheckInRequest",
    "AlertRead",
    "AlertCreate",
    "AlertAcknowledgeRequest",
]
