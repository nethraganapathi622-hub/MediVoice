from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.doctor import Doctor
from app.schemas.doctor import DoctorAvailabilityResponse, DoctorRead
from app.services.appointment_service import get_doctor_availability

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=List[DoctorRead], summary="List medical specialists")
def list_doctors(
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    specialty: Optional[str] = Query(None, description="Filter by specialty keyword"),
    search: Optional[str] = Query(None, description="Search doctor name or room"),
    active_only: bool = Query(True, description="Filter only active on-duty specialists"),
    db: Session = Depends(get_db),
) -> List[Doctor]:
    """Retrieve verified medical specialists with department details and search filters."""
    query = db.query(Doctor).options(joinedload(Doctor.department))
    if active_only:
        query = query.filter(Doctor.is_active == True)
    if department_id:
        query = query.filter(Doctor.department_id == department_id)
    if specialty:
        query = query.filter(Doctor.specialty.ilike(f"%{specialty.strip()}%"))
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(Doctor.name.ilike(s) | Doctor.room_number.ilike(s) | Doctor.specialty.ilike(s))

    return query.order_by(Doctor.name).all()


@router.get("/{doctor_id}", response_model=DoctorRead, summary="Get specialist profile")
def get_doctor(doctor_id: int, db: Session = Depends(get_db)) -> Doctor:
    """Retrieve detailed clinical profile for a specific doctor."""
    doctor = (
        db.query(Doctor)
        .options(joinedload(Doctor.department))
        .filter(Doctor.id == doctor_id)
        .first()
    )
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with ID {doctor_id} not found",
        )
    return doctor


@router.get(
    "/{doctor_id}/availability",
    response_model=DoctorAvailabilityResponse,
    summary="Get consultation slot availability",
)
def get_availability(
    doctor_id: int,
    target_date: Optional[date] = Query(None, alias="date", description="Query date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> DoctorAvailabilityResponse:
    """Calculate and return free and booked consultation slots for a doctor on a specific date."""
    query_date = target_date or date.today()
    return get_doctor_availability(db=db, doctor_id=doctor_id, target_date=query_date)
