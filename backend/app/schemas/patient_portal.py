from datetime import date, datetime, time
from typing import List, Optional
from pydantic import BaseModel, Field


class PatientOtpRequest(BaseModel):
    phone: str = Field(..., min_length=7, max_length=25, description="Patient mobile phone number with country code")
    display_name: Optional[str] = Field(None, max_length=150, description="Optional patient name")


class PatientOtpVerify(BaseModel):
    phone: str = Field(..., min_length=7, max_length=25)
    otp_code: str = Field(..., min_length=4, max_length=10)


class PatientAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    phone: str
    patient_id: Optional[int] = None
    display_name: str
    expires_at: datetime


class PatientAppointmentLookupRequest(BaseModel):
    booking_reference: str = Field(..., min_length=4, max_length=50)
    phone: str = Field(..., min_length=7, max_length=25)


class PatientSelfRescheduleRequest(BaseModel):
    new_date: date
    new_start_time: time
    reason: Optional[str] = Field("Rescheduled by patient via self-service portal", max_length=255)


class PatientSelfCancelRequest(BaseModel):
    reason: Optional[str] = Field("Cancelled by patient via self-service portal", max_length=255)
