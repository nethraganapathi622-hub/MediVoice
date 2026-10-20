from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class AlertCreate(BaseModel):
    priority: str = Field(..., pattern="^(critical|moderate|advisory)$")
    alert_type: str = Field(..., min_length=2, max_length=50)
    description: str = Field(..., min_length=5)
    department_id: Optional[int] = None
    patient_id: Optional[int] = None
    appointment_id: Optional[int] = None
    location: Optional[str] = None


class AlertAcknowledgeRequest(BaseModel):
    staff_id: str = Field(..., min_length=2, max_length=50, description="Staff employee identifier")
    staff_name: str = Field(..., min_length=2, max_length=100, description="Full name of staff acknowledging alert")


class AlertRead(BaseModel):
    id: int
    priority: str
    alert_type: str
    description: str
    department_id: Optional[int] = None
    patient_id: Optional[int] = None
    appointment_id: Optional[int] = None
    location: Optional[str] = None
    status: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
