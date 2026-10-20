from datetime import date, datetime, time
from pydantic import BaseModel, ConfigDict


class DoctorScheduleBase(BaseModel):
    doctor_id: int
    working_date: date
    start_time: time
    end_time: time
    slot_duration_minutes: int = 15
    is_available: bool = True


class DoctorScheduleCreate(DoctorScheduleBase):
    pass


class DoctorScheduleRead(DoctorScheduleBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
