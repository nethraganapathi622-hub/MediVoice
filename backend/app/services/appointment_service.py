import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.queue import QueueEntry
from app.models.schedule import DoctorSchedule
from app.schemas.appointment import AppointmentCreate, AppointmentRead
from app.schemas.doctor import DoctorAvailabilityResponse, SlotInfo

ACTIVE_STATUSES = ["booked", "confirmed", "checked-in", "in-progress"]


def _add_minutes_to_time(t: time, minutes: int) -> time:
    """Helper to add minutes to a python time object."""
    dt = datetime.combine(date.min, t) + timedelta(minutes=minutes)
    return dt.time()


def get_doctor_availability(
    db: Session, doctor_id: int, target_date: date
) -> DoctorAvailabilityResponse:
    """Calculate and return free and booked consultation slots for a doctor on a specific date."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor or not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found or currently inactive",
        )

    # Check for past date
    today = date.today()
    if target_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot query slot availability for dates in the past",
        )

    schedule = (
        db.query(DoctorSchedule)
        .filter(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.working_date == target_date,
        )
        .first()
    )

    if not schedule or not schedule.is_available:
        return DoctorAvailabilityResponse(
            doctor_id=doctor.id,
            doctor_name=doctor.name,
            date=str(target_date),
            is_on_duty=False,
            working_hours=None,
            available_slots=[],
        )

    # Fetch active booked appointments for this doctor on target_date
    booked_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == target_date,
            Appointment.status.in_(ACTIVE_STATUSES),
        )
        .all()
    )

    booked_ranges = [(apt.start_time, apt.end_time) for apt in booked_appointments]

    # Generate discrete slots based on slot_duration_minutes
    slot_minutes = schedule.slot_duration_minutes or 30
    current_time = schedule.start_time
    slots: List[SlotInfo] = []

    now_time = datetime.now().time()

    while current_time < schedule.end_time:
        slot_end = _add_minutes_to_time(current_time, slot_minutes)
        if slot_end > schedule.end_time:
            break

        # Check past time if target_date is today
        is_past = (target_date == today) and (current_time <= now_time)

        # Check collision with existing active appointments
        is_overlapping = any(
            (current_time < b_end and slot_end > b_start)
            for b_start, b_end in booked_ranges
        )

        slots.append(
            SlotInfo(
                start_time=current_time.strftime("%H:%M"),
                end_time=slot_end.strftime("%H:%M"),
                is_available=(not is_past) and (not is_overlapping),
            )
        )

        current_time = slot_end

    return DoctorAvailabilityResponse(
        doctor_id=doctor.id,
        doctor_name=doctor.name,
        date=str(target_date),
        is_on_duty=True,
        working_hours=f"{schedule.start_time.strftime('%H:%M')} - {schedule.end_time.strftime('%H:%M')}",
        available_slots=slots,
    )


def book_appointment(db: Session, payload: AppointmentCreate) -> Appointment:
    """Create a new appointment with strict schedule validation and collision rejection."""
    today = date.today()
    if payload.appointment_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment date cannot be in the past",
        )

    # 1. Verify doctor
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor or not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found or inactive",
        )

    # 2. Verify department
    department = db.query(Department).filter(Department.id == payload.department_id).first()
    if not department or not department.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found or inactive",
        )

    # 3. Verify doctor's working schedule
    schedule = (
        db.query(DoctorSchedule)
        .filter(
            DoctorSchedule.doctor_id == payload.doctor_id,
            DoctorSchedule.working_date == payload.appointment_date,
        )
        .first()
    )

    if not schedule or not schedule.is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Doctor is not scheduled or unavailable on {payload.appointment_date}",
        )

    slot_duration = schedule.slot_duration_minutes or 30
    slot_end_time = _add_minutes_to_time(payload.start_time, slot_duration)

    # Schedule boundary check
    if payload.start_time < schedule.start_time or slot_end_time > schedule.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Requested slot ({payload.start_time.strftime('%H:%M')} - {slot_end_time.strftime('%H:%M')}) "
                f"falls outside doctor working hours ({schedule.start_time.strftime('%H:%M')} - {schedule.end_time.strftime('%H:%M')})"
            ),
        )

    # Past time check if today
    if payload.appointment_date == today and payload.start_time <= datetime.now().time():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book an appointment slot that has already passed",
        )

    # 4. Resolve or create patient
    patient = None
    if payload.patient_id:
        patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient and payload.patient_phone:
        patient = db.query(Patient).filter(Patient.phone == payload.patient_phone).first()
    if not patient:
        patient = Patient(
            display_name=payload.patient_name,
            phone=payload.patient_phone,
            email=payload.patient_email,
        )
        db.add(patient)
        db.flush()

    # 5. Overlap checks inside transaction
    # A) Check doctor collision
    doc_overlap = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == payload.doctor_id,
            Appointment.appointment_date == payload.appointment_date,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.start_time < slot_end_time,
            Appointment.end_time > payload.start_time,
        )
        .first()
    )
    if doc_overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The requested time slot is already booked for this doctor",
        )

    # B) Check patient collision
    patient_overlap = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.id,
            Appointment.appointment_date == payload.appointment_date,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.start_time < slot_end_time,
            Appointment.end_time > payload.start_time,
        )
        .first()
    )
    if patient_overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The patient already has an active overlapping appointment during this time window",
        )

    # 6. Generate unique booking reference
    date_str = payload.appointment_date.strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    booking_ref = f"APT-{date_str}-{unique_suffix}"

    appointment = Appointment(
        booking_reference=booking_ref,
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=department.id,
        appointment_date=payload.appointment_date,
        start_time=payload.start_time,
        end_time=slot_end_time,
        status="booked",
        appointment_type=payload.appointment_type,
        notes=payload.notes,
    )
    db.add(appointment)
    db.flush()

    # 7. Generate queue entry if appointment is for today
    if payload.appointment_date == today:
        dept_code = department.code
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
            priority="normal",
        )
        db.add(queue_entry)

    db.commit()
    db.refresh(appointment)

    # Broadcast appointment.created event strictly after commit
    from app.ws.events import emit_appointment_created
    emit_appointment_created(
        appointment_id=appointment.id,
        booking_reference=appointment.booking_reference,
        doctor_id=appointment.doctor_id,
        department_id=appointment.department_id,
        appointment_date=str(appointment.appointment_date),
        start_time=str(appointment.start_time),
        end_time=str(appointment.end_time),
        status=appointment.status,
    )

    # Dispatch appointment confirmation notification
    try:
        from app.services.notification_service import notification_service
        phone_to_notify = patient.phone or payload.patient_phone
        if phone_to_notify:
            notification_service.send_appointment_confirmed(
                phone=phone_to_notify,
                patient_name=patient.display_name,
                booking_ref=appointment.booking_reference,
                doctor_name=doctor.name,
                dept_name=department.name,
                apt_date=str(appointment.appointment_date),
                start_time=str(appointment.start_time),
                room_number=doctor.room_number or "OPD Consultation Room",
            )
    except Exception as n_err:
        logger.warning("Could not dispatch appointment confirmation notification: %s", n_err)

    return appointment


def reschedule_appointment(
    db: Session, appointment_id: int, new_date: date, new_start_time: time
) -> Appointment:
    """Atomically validate new slot and reschedule existing appointment without corrupting original state."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if appointment.status in ["completed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reschedule an appointment with status '{appointment.status}'",
        )

    today = date.today()
    if new_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New appointment date cannot be in the past",
        )

    schedule = (
        db.query(DoctorSchedule)
        .filter(
            DoctorSchedule.doctor_id == appointment.doctor_id,
            DoctorSchedule.working_date == new_date,
        )
        .first()
    )

    if not schedule or not schedule.is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Doctor is unavailable on {new_date}",
        )

    slot_duration = schedule.slot_duration_minutes or 30
    new_end_time = _add_minutes_to_time(new_start_time, slot_duration)

    if new_start_time < schedule.start_time or new_end_time > schedule.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New time slot is outside doctor scheduled working hours",
        )

    if new_date == today and new_start_time <= datetime.now().time():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New time slot has already passed",
        )

    # Check doctor overlap (excluding current appointment)
    doc_overlap = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == appointment.doctor_id,
            Appointment.appointment_date == new_date,
            Appointment.id != appointment.id,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.start_time < new_end_time,
            Appointment.end_time > new_start_time,
        )
        .first()
    )
    if doc_overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor already has an overlapping appointment in the new time slot",
        )

    # Check patient overlap (excluding current appointment)
    patient_overlap = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == appointment.patient_id,
            Appointment.appointment_date == new_date,
            Appointment.id != appointment.id,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.start_time < new_end_time,
            Appointment.end_time > new_start_time,
        )
        .first()
    )
    if patient_overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient has another overlapping appointment in the new time slot",
        )

    # Apply changes atomically
    appointment.appointment_date = new_date
    appointment.start_time = new_start_time
    appointment.end_time = new_end_time
    appointment.status = "rescheduled"
    appointment.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(appointment)

    # Broadcast appointment.rescheduled event strictly after commit
    from app.ws.events import emit_appointment_rescheduled
    emit_appointment_rescheduled(
        appointment_id=appointment.id,
        booking_reference=appointment.booking_reference,
        doctor_id=appointment.doctor_id,
        department_id=appointment.department_id,
        appointment_date=str(appointment.appointment_date),
        start_time=str(appointment.start_time),
        end_time=str(appointment.end_time),
    )

    # Dispatch reschedule notification
    try:
        from app.services.notification_service import notification_service
        if appointment.patient and appointment.patient.phone:
            notification_service.send_appointment_rescheduled(
                phone=appointment.patient.phone,
                patient_name=appointment.patient.display_name,
                booking_ref=appointment.booking_reference,
                doctor_name=appointment.doctor.name if appointment.doctor else "Doctor",
                new_date=str(new_date),
                new_time=str(new_start_time),
            )
    except Exception as n_err:
        logger.warning("Could not dispatch reschedule notification: %s", n_err)

    return appointment


def cancel_appointment(db: Session, appointment_id: int, reason: Optional[str] = None) -> Appointment:
    """Cancel an appointment and free up its booked slot."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if appointment.status == "cancelled":
        return appointment

    appointment.status = "cancelled"
    appointment.updated_at = datetime.now(timezone.utc)
    if reason:
        appointment.notes = (appointment.notes or "") + f" [Cancelled: {reason}]"

    # Also update associated queue entry if present
    if appointment.queue_entry:
        appointment.queue_entry.status = "cancelled"

    db.commit()
    db.refresh(appointment)

    # Broadcast appointment.cancelled event strictly after commit
    from app.ws.events import emit_appointment_cancelled
    emit_appointment_cancelled(
        appointment_id=appointment.id,
        booking_reference=appointment.booking_reference,
        doctor_id=appointment.doctor_id,
        department_id=appointment.department_id,
    )

    # Dispatch cancellation notification
    try:
        from app.services.notification_service import notification_service
        if appointment.patient and appointment.patient.phone:
            notification_service.send_appointment_cancelled(
                phone=appointment.patient.phone,
                booking_ref=appointment.booking_reference,
            )
    except Exception as n_err:
        logger.warning("Could not dispatch cancellation notification: %s", n_err)

    return appointment
