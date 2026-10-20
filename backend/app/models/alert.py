from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class TriageAlert(Base):
    """Clinical triage, emergency warning, and operational alert."""

    __tablename__ = "triage_alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    priority = Column(String(20), nullable=False, index=True)  # critical, moderate, advisory
    alert_type = Column(
        String(50),
        nullable=False,
        index=True,
    )  # trauma_priority, queue_capacity, schedule_advisory, clinical_review
    description = Column(Text, nullable=False)
    department_id = Column(
        Integer,
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location = Column(String(100), nullable=True)
    status = Column(
        String(30),
        default="active",
        nullable=False,
        index=True,
    )  # active, acknowledged, resolved
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)

    # Relationships
    department = relationship("Department", back_populates="alerts")
    patient = relationship("Patient", back_populates="alerts")
    appointment = relationship("Appointment", back_populates="alerts")

    def __repr__(self) -> str:
        return f"<TriageAlert(id={self.id}, priority='{self.priority}', type='{self.alert_type}')>"
