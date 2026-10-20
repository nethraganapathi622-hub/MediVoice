from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.department import Department
from app.models.queue import QueueEntry
from app.schemas.queue import QueueCheckInRequest, QueueEntryRead

router = APIRouter(prefix="/queue", tags=["Queue"])


@router.get("", response_model=List[QueueEntryRead], summary="List patient queue")
def list_queue(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by queue status"),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    priority: Optional[str] = Query(None, description="Filter by priority (normal, urgent, emergency)"),
    db: Session = Depends(get_db),
) -> List[QueueEntry]:
    """Retrieve outpatient queue entries for staff triage coordination."""
    query = (
        db.query(QueueEntry)
        .join(Appointment)
        .options(
            joinedload(QueueEntry.appointment).joinedload(Appointment.patient),
            joinedload(QueueEntry.appointment).joinedload(Appointment.doctor),
            joinedload(QueueEntry.appointment).joinedload(Appointment.department),
        )
    )

    if status_filter and status_filter.lower() != "all":
        query = query.filter(QueueEntry.status == status_filter.lower())
    if department_id:
        query = query.filter(Appointment.department_id == department_id)
    if priority:
        query = query.filter(QueueEntry.priority == priority.lower())

    return query.order_by(QueueEntry.check_in_time.asc()).all()


@router.post("/check-in", response_model=QueueEntryRead, status_code=status.HTTP_201_CREATED, summary="Patient check-in")
def check_in(payload: QueueCheckInRequest, db: Session = Depends(get_db)) -> QueueEntry:
    """Check in a patient for their scheduled appointment and generate a queue token."""
    query = db.query(Appointment)
    if payload.appointment_id:
        query = query.filter(Appointment.id == payload.appointment_id)
    elif payload.booking_reference:
        query = query.filter(Appointment.booking_reference == payload.booking_reference)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must supply either appointment_id or booking_reference to check in",
        )

    appointment = query.first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if appointment.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot check in for a cancelled appointment",
        )

    # Check if queue entry already exists
    existing_entry = db.query(QueueEntry).filter(QueueEntry.appointment_id == appointment.id).first()
    if existing_entry:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Appointment {appointment.booking_reference} is already checked in with token {existing_entry.token}",
        )

    # Generate token safely and avoid duplicates for the department
    dept = db.query(Department).filter(Department.id == appointment.department_id).first()
    dept_code = dept.code if dept else "GEN"
    existing_tokens = (
        db.query(QueueEntry.token)
        .filter(QueueEntry.token.like(f"{dept_code}-%"))
        .all()
    )
    max_num = 100
    for (tok,) in existing_tokens:
        try:
            num = int(tok.split("-")[-1])
            if num > max_num:
                max_num = num
        except (ValueError, IndexError):
            pass
    token_str = f"{dept_code}-{max_num + 1}"

    queue_entry = QueueEntry(
        appointment_id=appointment.id,
        token=token_str,
        status="waiting",
        priority=payload.priority,
        check_in_time=datetime.now(timezone.utc),
    )
    appointment.status = "checked-in"

    db.add(queue_entry)
    db.commit()
    db.refresh(queue_entry)

    # Broadcast queue.checked_in strictly after commit
    from app.ws.events import emit_queue_checked_in
    emit_queue_checked_in(
        queue_id=queue_entry.id,
        token=queue_entry.token,
        appointment_id=queue_entry.appointment_id,
        department_id=appointment.department_id,
        priority=queue_entry.priority,
        check_in_time=str(queue_entry.check_in_time),
    )

    # Dispatch queue token notification
    try:
        from app.services.notification_service import notification_service
        if appointment.patient and appointment.patient.phone:
            dept_name = dept.name if dept else "OPD Department"
            notification_service.send_queue_token_issued(
                phone=appointment.patient.phone,
                token=queue_entry.token,
                dept_name=dept_name,
            )
    except Exception as n_err:
        pass

    return queue_entry


@router.post("/{queue_id}/call", response_model=QueueEntryRead, summary="Call patient to consultation room")
def call_patient(queue_id: int, db: Session = Depends(get_db)) -> QueueEntry:
    """Mark a patient as called into the consultation room."""
    entry = (
        db.query(QueueEntry)
        .options(
            joinedload(QueueEntry.appointment).joinedload(Appointment.doctor),
            joinedload(QueueEntry.appointment).joinedload(Appointment.department),
        )
        .filter(QueueEntry.id == queue_id)
        .first()
    )
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry with ID {queue_id} not found",
        )

    entry.status = "called"
    entry.called_time = datetime.now(timezone.utc)
    if entry.appointment:
        entry.appointment.status = "in-progress"

    db.commit()
    db.refresh(entry)

    # Broadcast queue.patient_called strictly after commit
    from app.ws.events import emit_queue_patient_called

    doc_name = None
    room_no = None
    dept_name = None
    if entry.appointment:
        if entry.appointment.doctor:
            doc_name = entry.appointment.doctor.name
            room_no = entry.appointment.doctor.room_number
        if entry.appointment.department:
            dept_name = entry.appointment.department.name

    emit_queue_patient_called(
        queue_id=entry.id,
        token=entry.token,
        appointment_id=entry.appointment_id,
        called_time=str(entry.called_time),
        department_name=dept_name,
        doctor_name=doc_name,
        room_number=room_no,
    )

    return entry


@router.post("/{queue_id}/complete", response_model=QueueEntryRead, summary="Mark consultation completed")
def complete_consultation(queue_id: int, db: Session = Depends(get_db)) -> QueueEntry:
    """Mark a patient's consultation as completed and discharge from active queue."""
    entry = db.query(QueueEntry).filter(QueueEntry.id == queue_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry with ID {queue_id} not found",
        )

    entry.status = "completed"
    entry.completed_time = datetime.now(timezone.utc)
    if entry.appointment:
        entry.appointment.status = "completed"

    db.commit()
    db.refresh(entry)

    # Broadcast queue.completed strictly after commit
    from app.ws.events import emit_queue_completed
    emit_queue_completed(
        queue_id=entry.id,
        token=entry.token,
        appointment_id=entry.appointment_id,
        completed_time=str(entry.completed_time),
    )

    return entry
