from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ConsultationNote(Base):
    """Electronic Health Record (EHR) consultation note and prescription record."""

    __tablename__ = "consultation_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chief_complaint = Column(Text, nullable=False)
    diagnosis = Column(String(255), nullable=False, index=True)
    clinical_notes = Column(Text, nullable=True)
    prescriptions = Column(JSON, nullable=True)  # List of { medication, dosage, frequency, duration, instructions }
    follow_up_date = Column(Date, nullable=True)
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

    # Relationships
    appointment = relationship("Appointment", backref="consultation_note")
    doctor = relationship("Doctor", backref="consultation_notes")
    patient = relationship("Patient", backref="consultation_notes")

    def __repr__(self) -> str:
        return f"<ConsultationNote(id={self.id}, apt={self.appointment_id}, diag='{self.diagnosis}')>"
