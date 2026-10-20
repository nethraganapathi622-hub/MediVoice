from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PrescriptionItem(BaseModel):
    medication_name: str = Field(..., min_length=2, max_length=150)
    dosage: str = Field(..., max_length=50)  # e.g., "500mg"
    frequency: str = Field(..., max_length=50)  # e.g., "Twice daily after meals"
    duration_days: int = Field(..., ge=1, le=365)
    instructions: Optional[str] = Field(None, max_length=255)


class ConsultationNoteBase(BaseModel):
    chief_complaint: str = Field(..., min_length=3, description="Patient presenting clinical symptoms")
    diagnosis: str = Field(..., min_length=2, max_length=255, description="Clinical diagnosis or ICD assessment")
    clinical_notes: Optional[str] = Field(None, description="Detailed physical examination notes and vitals")
    prescriptions: Optional[List[PrescriptionItem]] = Field(default_factory=list)
    follow_up_date: Optional[date] = None


class ConsultationNoteCreate(ConsultationNoteBase):
    appointment_id: int


class ConsultationNoteUpdate(BaseModel):
    chief_complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    clinical_notes: Optional[str] = None
    prescriptions: Optional[List[PrescriptionItem]] = None
    follow_up_date: Optional[date] = None


class ConsultationNoteRead(ConsultationNoteBase):
    id: int
    appointment_id: int
    doctor_id: int
    patient_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
