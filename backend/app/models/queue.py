from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class QueueEntry(Base):
    """Patient queue and token management entry."""

    __tablename__ = "queue_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    token = Column(String(30), nullable=False, index=True)
    status = Column(
        String(50),
        default="waiting",
        nullable=False,
        index=True,
    )  # waiting, triage, called, in_consultation, completed, cancelled
    priority = Column(String(20), default="normal", nullable=False)  # normal, urgent, emergency
    check_in_time = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    called_time = Column(DateTime(timezone=True), nullable=True)
    completed_time = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    appointment = relationship("Appointment", back_populates="queue_entry")

    def __repr__(self) -> str:
        return f"<QueueEntry(token='{self.token}', status='{self.status}', apt_id={self.appointment_id})>"
