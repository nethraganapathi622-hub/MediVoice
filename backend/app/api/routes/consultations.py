from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import StaffUser, get_current_staff, require_staff_roles
from app.models.appointment import Appointment
from app.models.consultation import ConsultationNote
from app.schemas.consultation import (
    ConsultationNoteCreate,
    ConsultationNoteRead,
    ConsultationNoteUpdate,
)

router = APIRouter(prefix="/consultations", tags=["Clinical Staff EHR"])


@router.post(
    "",
    response_model=ConsultationNoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record clinical consultation note and digital prescriptions",
)
def create_consultation_note(
    payload: ConsultationNoteCreate,
    current_staff: StaffUser = Depends(require_staff_roles(["Doctor", "TriageLead", "Admin"])),
    db: Session = Depends(get_db),
):
    """Doctor or clinical lead creates an EHR consultation note and completes the appointment."""
    apt = db.query(Appointment).filter(Appointment.id == payload.appointment_id).first()
    if not apt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment {payload.appointment_id} not found",
        )

    # Check if a consultation note already exists for this appointment
    existing = db.query(ConsultationNote).filter(ConsultationNote.appointment_id == payload.appointment_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Consultation note already exists for appointment {payload.appointment_id}",
        )

    prescriptions_data = [item.model_dump() for item in (payload.prescriptions or [])]

    note = ConsultationNote(
        appointment_id=apt.id,
        doctor_id=apt.doctor_id,
        patient_id=apt.patient_id,
        chief_complaint=payload.chief_complaint,
        diagnosis=payload.diagnosis,
        clinical_notes=payload.clinical_notes,
        prescriptions=prescriptions_data,
        follow_up_date=payload.follow_up_date,
    )
    db.add(note)

    # Automatically progress appointment to completed
    apt.status = "completed"
    apt.updated_at = datetime.now(timezone.utc)

    # If active queue entry, mark completed
    if apt.queue_entry:
        apt.queue_entry.status = "completed"
        apt.queue_entry.completed_time = datetime.now(timezone.utc)

    db.commit()
    db.refresh(note)

    return note


@router.get(
    "/appointment/{appointment_id}",
    response_model=ConsultationNoteRead,
    summary="Get consultation note for appointment",
)
def get_appointment_consultation_note(
    appointment_id: int,
    current_staff: StaffUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """Retrieve consultation record and digital prescriptions for an appointment (staff only)."""
    note = db.query(ConsultationNote).filter(ConsultationNote.appointment_id == appointment_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No consultation note found for appointment {appointment_id}",
        )
    return note


@router.get(
    "/patient/{patient_id}",
    response_model=List[ConsultationNoteRead],
    summary="Get longitudinal clinical history for patient",
)
def get_patient_consultation_history(
    patient_id: int,
    current_staff: StaffUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """Retrieve all chronological EHR records for a patient (staff only)."""
    notes = (
        db.query(ConsultationNote)
        .filter(ConsultationNote.patient_id == patient_id)
        .order_by(ConsultationNote.created_at.desc())
        .all()
    )
    return notes


@router.put(
    "/{note_id}",
    response_model=ConsultationNoteRead,
    summary="Update clinical consultation note",
)
def update_consultation_note(
    note_id: int,
    payload: ConsultationNoteUpdate,
    current_staff: StaffUser = Depends(require_staff_roles(["Doctor", "Admin"])),
    db: Session = Depends(get_db),
):
    """Update clinical findings or add prescription revisions."""
    note = db.query(ConsultationNote).filter(ConsultationNote.id == note_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation note {note_id} not found",
        )

    if payload.chief_complaint is not None:
        note.chief_complaint = payload.chief_complaint
    if payload.diagnosis is not None:
        note.diagnosis = payload.diagnosis
    if payload.clinical_notes is not None:
        note.clinical_notes = payload.clinical_notes
    if payload.prescriptions is not None:
        note.prescriptions = [p.model_dump() for p in payload.prescriptions]
    if payload.follow_up_date is not None:
        note.follow_up_date = payload.follow_up_date

    note.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(note)

    return note
