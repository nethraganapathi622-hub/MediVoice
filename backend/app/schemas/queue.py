from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.appointment import AppointmentRead


class QueueCheckInRequest(BaseModel):
    appointment_id: Optional[int] = None
    booking_reference: Optional[str] = None
    priority: str = "normal"  # normal, urgent, emergency


class QueueEntryRead(BaseModel):
    id: int
    appointment_id: int
    token: str
    status: str
    priority: str
    check_in_time: datetime
    called_time: Optional[datetime] = None
    completed_time: Optional[datetime] = None
    appointment: Optional[AppointmentRead] = None

    model_config = ConfigDict(from_attributes=True)
