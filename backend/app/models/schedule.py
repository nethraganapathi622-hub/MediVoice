from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class DoctorSchedule(Base):
    """Doctor working shift and slot configuration."""

    __tablename__ = "doctor_schedules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    working_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    slot_duration_minutes = Column(Integer, default=15, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("doctor_id", "working_date", name="uq_doctor_working_date"),
    )

    # Relationships
    doctor = relationship("Doctor", back_populates="schedules")

    def __repr__(self) -> str:
        return (
            f"<DoctorSchedule(id={self.id}, doctor_id={self.doctor_id}, "
            f"date={self.working_date}, {self.start_time}-{self.end_time})>"
        )
