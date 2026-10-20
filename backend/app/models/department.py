from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Department(Base):
    """Hospital clinical department model."""

    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    location = Column(String(100), nullable=False)
    floor = Column(String(50), nullable=False)
    extension = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    doctors = relationship("Doctor", back_populates="department", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="department")
    alerts = relationship("TriageAlert", back_populates="department")

    def __repr__(self) -> str:
        return f"<Department(id={self.id}, code='{self.code}', name='{self.name}')>"
