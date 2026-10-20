from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Patient(Base):
    """Patient registration record."""

    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    display_name = Column(String(150), nullable=False, index=True)
    phone = Column(String(30), nullable=True, index=True)
    email = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    appointments = relationship("Appointment", back_populates="patient")
    alerts = relationship("TriageAlert", back_populates="patient")

    def __repr__(self) -> str:
        return f"<Patient(id={self.id}, name='{self.display_name}')>"
