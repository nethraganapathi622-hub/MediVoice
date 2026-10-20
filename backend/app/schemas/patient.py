from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PatientBase(BaseModel):
    display_name: str
    phone: Optional[str] = None
    email: Optional[str] = None


class PatientCreate(PatientBase):
    pass


class PatientRead(PatientBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
