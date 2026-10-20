from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Appointment(Base):
    """Clinical outpatient appointment booking."""

    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    booking_reference = Column(String(50), unique=True, nullable=False, index=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id = Column(
        Integer,
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(
        String(50),
        default="booked",
        nullable=False,
        index=True,
    )  # booked, confirmed, checked-in, in-progress, completed, cancelled, rescheduled
    appointment_type = Column(String(50), default="Consultation", nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_appointment_doctor_date", "doctor_id", "appointment_date"),
        Index("ix_appointment_patient_date", "patient_id", "appointment_date"),
    )

    # Relationships
    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    department = relationship("Department", back_populates="appointments")
    queue_entry = relationship(
        "QueueEntry",
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    alerts = relationship("TriageAlert", back_populates="appointment")

    def __repr__(self) -> str:
        return (
            f"<Appointment(ref='{self.booking_reference}', doc={self.doctor_id}, "
            f"pat={self.patient_id}, date={self.appointment_date}, status='{self.status}')>"
        )
