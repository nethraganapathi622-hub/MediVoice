from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.appointment import Appointment
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentRead,
    AppointmentReschedule,
)
from app.services.appointment_service import (
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
)

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def _to_read_schema(apt: Appointment) -> AppointmentRead:
    """Format an Appointment ORM entity into the AppointmentRead schema with token string."""
    token_str = apt.queue_entry.token if apt.queue_entry else None
    return AppointmentRead(
        id=apt.id,
        booking_reference=apt.booking_reference,
        patient_id=apt.patient_id,
        doctor_id=apt.doctor_id,
        department_id=apt.department_id,
        appointment_date=apt.appointment_date,
        start_time=apt.start_time,
        end_time=apt.end_time,
        status=apt.status,
        appointment_type=apt.appointment_type,
        notes=apt.notes,
        created_at=apt.created_at,
        updated_at=apt.updated_at,
        patient=apt.patient,
        doctor=apt.doctor,
        department=apt.department,
        queue_token=token_str,
    )


@router.get("", response_model=List[AppointmentRead], summary="List appointments")
def list_appointments(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (booked, confirmed, completed, cancelled)"),
    doctor_id: Optional[int] = Query(None, description="Filter by doctor ID"),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    patient_id: Optional[int] = Query(None, description="Filter by patient ID"),
    target_date: Optional[date] = Query(None, alias="date", description="Filter by date"),
    search: Optional[str] = Query(None, description="Search by booking reference, patient name, or doctor name"),
    db: Session = Depends(get_db),
) -> List[AppointmentRead]:
    """Retrieve outpatient appointments with flexible clinical filters."""
    query = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.patient),
            joinedload(Appointment.doctor),
            joinedload(Appointment.department),
            joinedload(Appointment.queue_entry),
        )
    )

    if status_filter and status_filter.lower() != "all":
        query = query.filter(Appointment.status == status_filter.lower())
    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if department_id:
        query = query.filter(Appointment.department_id == department_id)
    if patient_id:
        query = query.filter(Appointment.patient_id == patient_id)
    if target_date:
        query = query.filter(Appointment.appointment_date == target_date)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(Appointment.booking_reference.ilike(s))

    appointments = query.order_by(Appointment.appointment_date.desc(), Appointment.start_time.asc()).all()
    return [_to_read_schema(apt) for apt in appointments]


@router.get("/{appointment_id}", response_model=AppointmentRead, summary="Get appointment by ID")
def get_appointment(appointment_id: int, db: Session = Depends(get_db)) -> AppointmentRead:
    """Retrieve details of a single appointment booking."""
    apt = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.patient),
            joinedload(Appointment.doctor),
            joinedload(Appointment.department),
            joinedload(Appointment.queue_entry),
        )
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not apt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with ID {appointment_id} not found",
        )
    return _to_read_schema(apt)


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED, summary="Book an appointment")
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)) -> AppointmentRead:
    """Book a new clinical consultation slot with strict schedule and overlap integrity rules."""
    appointment = book_appointment(db=db, payload=payload)
    # Refresh relations
    db.refresh(appointment)
    return _to_read_schema(appointment)


@router.patch("/{appointment_id}/reschedule", response_model=AppointmentRead, summary="Reschedule appointment")
def reschedule(
    appointment_id: int,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
) -> AppointmentRead:
    """Atomically validate new slot and reschedule existing appointment."""
    appointment = reschedule_appointment(
        db=db,
        appointment_id=appointment_id,
        new_date=payload.new_date,
        new_start_time=payload.new_start_time,
    )
    return _to_read_schema(appointment)


@router.post("/{appointment_id}/cancel", response_model=AppointmentRead, summary="Cancel appointment")
def cancel(
    appointment_id: int,
    payload: Optional[AppointmentCancel] = None,
    db: Session = Depends(get_db),
) -> AppointmentRead:
    """Cancel an appointment and free its consultation slot."""
    reason = payload.reason if payload else None
    appointment = cancel_appointment(db=db, appointment_id=appointment_id, reason=reason)
    return _to_read_schema(appointment)
