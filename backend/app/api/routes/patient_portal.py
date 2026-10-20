from datetime import date, datetime, timedelta, timezone
import secrets
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    PatientUser,
    create_patient_access_token,
    get_current_patient,
)
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.schemas.appointment import AppointmentRead
from app.schemas.patient_portal import (
    PatientAppointmentLookupRequest,
    PatientAuthResponse,
    PatientOtpRequest,
    PatientOtpVerify,
    PatientSelfCancelRequest,
    PatientSelfRescheduleRequest,
)
from app.schemas.queue import QueueCheckInRequest, QueueEntryRead
from app.services.appointment_service import cancel_appointment, reschedule_appointment
from app.api.routes.queue import check_in
from app.services.notification_service import notification_service

router = APIRouter(prefix="/patient", tags=["Patient Self-Service Portal"])

# In-memory OTP store with 10-minute expiry: phone -> {"code": "123456", "expires_at": datetime, "attempts": int}
_OTP_CACHE: Dict[str, Dict] = {}


def _clean_phone(raw: str) -> str:
    """Normalize phone number to digits and leading plus."""
    cleaned = "".join(c for c in raw if c.isdigit() or c == "+")
    return cleaned.strip()


def _format_appointment_read(apt: Appointment) -> AppointmentRead:
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


@router.post("/auth/request-otp", summary="Request verification OTP for patient self-service")
def request_patient_otp(payload: PatientOtpRequest, db: Session = Depends(get_db)):
    """Generate a 6-digit OTP for patient phone authentication.

    In local/test development, the code '123456' is accepted for ease of automated testing and rapid review.
    In staging/production, a cryptographically secure random 6-digit code is generated.
    """
    settings = get_settings()
    clean = _clean_phone(payload.phone)
    if not clean or len(clean) < 7:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A valid phone number with at least 7 digits is required",
        )

    # Cryptographically random OTP in production, dev fallback in development
    if settings.is_development:
        code = "123456"
    else:
        code = f"{secrets.randbelow(900000) + 100000}"

    expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
    _OTP_CACHE[clean] = {"code": code, "expires_at": expiry, "attempts": 0}

    # Record notification in hospital notification audit trail
    notification_service._record(
        clean,
        "sms",
        "otp_verification",
        "en",
        f"Your MediVoice verification code is {code}. It expires in 10 minutes. Do not share this code.",
    )

    response_data = {
        "success": True,
        "message": f"Verification code sent to {clean}",
        "phone": clean,
    }
    if settings.is_development:
        response_data["demo_otp"] = code

    return response_data


@router.post("/auth/verify-otp", response_model=PatientAuthResponse, summary="Verify OTP and issue patient JWT token")
def verify_patient_otp(payload: PatientOtpVerify, db: Session = Depends(get_db)):
    """Validate OTP and issue a patient session JWT token.

    Enforces:
    - Expiration (10 minutes)
    - One-time use (consumed upon successful validation)
    - Maximum 5 failed attempts lockout
    """
    settings = get_settings()
    clean = _clean_phone(payload.phone)
    entry = _OTP_CACHE.get(clean)

    if not entry:
        if settings.is_development and payload.otp_code == "123456":
            entry = {
                "code": "123456",
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
                "attempts": 0,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active verification code found for this phone number. Please request a new OTP.",
            )

    # Check attempt limit
    if entry.get("attempts", 0) >= 5:
        _OTP_CACHE.pop(clean, None)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many invalid attempts. Please request a new verification code.",
        )

    now = datetime.now(timezone.utc)
    if entry["expires_at"] < now:
        _OTP_CACHE.pop(clean, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new OTP.",
        )

    # Validate code
    valid = False
    if entry["code"] == payload.otp_code:
        valid = True
    elif settings.is_development and payload.otp_code == "123456":
        valid = True

    if not valid:
        entry["attempts"] = entry.get("attempts", 0) + 1
        remaining = 5 - entry["attempts"]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempt(s) remaining.",
        )

    # Consume OTP (one-time use)
    _OTP_CACHE.pop(clean, None)

    # Locate or create Patient record
    patient = db.query(Patient).filter(Patient.phone == clean).first()
    display_name = patient.display_name if patient else "Verified Patient"
    patient_id = patient.id if patient else None

    token = create_patient_access_token(phone=clean, patient_id=patient_id, name=display_name)
    expire_time = datetime.now(timezone.utc) + timedelta(days=7)

    return PatientAuthResponse(
        access_token=token,
        token_type="bearer",
        phone=clean,
        patient_id=patient_id,
        display_name=display_name,
        expires_at=expire_time,
    )


@router.get("/appointments", response_model=List[AppointmentRead], summary="List verified patient's appointments")
def get_verified_patient_appointments(
    current_patient: PatientUser = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Retrieve only appointments booked under the verified patient's phone number."""
    # Find matching patients with this phone number
    patients = db.query(Patient).filter(Patient.phone == current_patient.phone).all()
    patient_ids = [p.id for p in patients]

    if not patient_ids:
        return []

    appointments = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.patient),
            joinedload(Appointment.doctor),
            joinedload(Appointment.department),
            joinedload(Appointment.queue_entry),
        )
        .filter(Appointment.patient_id.in_(patient_ids))
        .order_by(Appointment.appointment_date.desc(), Appointment.start_time.asc())
        .all()
    )

    return [_format_appointment_read(apt) for apt in appointments]


@router.post("/appointments/lookup", response_model=AppointmentRead, summary="Lookup single appointment pass by reference and phone")
def lookup_patient_appointment(
    payload: PatientAppointmentLookupRequest,
    db: Session = Depends(get_db),
):
    """Securely look up an appointment pass requiring both booking reference and matching phone number."""
    apt = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.patient),
            joinedload(Appointment.doctor),
            joinedload(Appointment.department),
            joinedload(Appointment.queue_entry),
        )
        .filter(Appointment.booking_reference == payload.booking_reference.strip().upper())
        .first()
    )

    if not apt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment reference not found")

    cleaned_input_phone = _clean_phone(payload.phone)
    patient_phone = _clean_phone(apt.patient.phone or "")

    if not patient_phone or patient_phone != cleaned_input_phone:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification failed: Provided phone number does not match booking records",
        )

    return _format_appointment_read(apt)


@router.post("/appointments/{appointment_id}/reschedule", response_model=AppointmentRead, summary="Patient self-reschedule")
def patient_self_reschedule(
    appointment_id: int,
    payload: PatientSelfRescheduleRequest,
    current_patient: PatientUser = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Reschedule an appointment with strict ownership verification."""
    apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not apt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    # Verify patient ownership
    if not apt.patient or _clean_phone(apt.patient.phone or "") != _clean_phone(current_patient.phone):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: You do not own this appointment record",
        )

    updated = reschedule_appointment(
        db=db,
        appointment_id=appointment_id,
        new_date=payload.new_date,
        new_start_time=payload.new_start_time,
    )
    return _format_appointment_read(updated)


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentRead, summary="Patient self-cancel")
def patient_self_cancel(
    appointment_id: int,
    payload: PatientSelfCancelRequest,
    current_patient: PatientUser = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Cancel an appointment with strict ownership verification."""
    apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not apt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    # Verify patient ownership
    if not apt.patient or _clean_phone(apt.patient.phone or "") != _clean_phone(current_patient.phone):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: You do not own this appointment record",
        )

    updated = cancel_appointment(
        db=db,
        appointment_id=appointment_id,
        reason=payload.reason or "Cancelled by patient via self-service portal",
    )
    return _format_appointment_read(updated)


@router.post("/appointments/{appointment_id}/check-in", response_model=QueueEntryRead, summary="Patient self check-in")
def patient_self_check_in(
    appointment_id: int,
    current_patient: PatientUser = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Self check-in for outpatient queue token with ownership verification."""
    apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not apt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    if not apt.patient or _clean_phone(apt.patient.phone or "") != _clean_phone(current_patient.phone):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: You do not own this appointment record",
        )

    q_entry = check_in(payload=QueueCheckInRequest(appointment_id=appointment_id), db=db)
    return q_entry

