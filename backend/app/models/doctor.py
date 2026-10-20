from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Doctor(Base):
    """Medical doctor and specialist model."""

    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False, index=True)
    department_id = Column(
        Integer,
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    specialty = Column(String(150), nullable=False, index=True)
    qualifications = Column(String(255), nullable=False)
    experience = Column(String(50), nullable=False)
    consultation_fee = Column(Numeric(10, 2), nullable=False, default=500.00)
    room_number = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    department = relationship("Department", back_populates="doctors")
    schedules = relationship(
        "DoctorSchedule",
        back_populates="doctor",
        cascade="all, delete-orphan",
    )
    appointments = relationship("Appointment", back_populates="doctor")

    def __repr__(self) -> str:
        return f"<Doctor(id={self.id}, name='{self.name}', specialty='{self.specialty}')>"
