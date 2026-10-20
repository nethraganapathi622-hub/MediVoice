"""SQLAlchemy models package for MediVoice."""

from app.models.department import Department
from app.models.doctor import Doctor
from app.models.schedule import DoctorSchedule
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.queue import QueueEntry
from app.models.alert import TriageAlert
from app.models.consultation import ConsultationNote

__all__ = [
    "Department",
    "Doctor",
    "DoctorSchedule",
    "Patient",
    "Appointment",
    "QueueEntry",
    "TriageAlert",
    "ConsultationNote",
]

