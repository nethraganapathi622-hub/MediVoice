import re
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.schedule import DoctorSchedule
from app.schemas.appointment import AppointmentCreate
from app.services.appointment_service import (
    book_appointment,
    cancel_appointment,
    get_doctor_availability,
    reschedule_appointment,
)


# Specialty and clinical department aliases/stems for resilient matching across languages
SPECIALTY_ALIASES: Dict[str, List[str]] = {
    "cardiology": ["cardio", "heart", "cardiac", "cardiology", "cardiologist", "chest", "hypertension", "card", "இதயம்", "இதய", "दिल", "हृदय", "हार्ट"],
    "neurology": ["neuro", "brain", "nerve", "stroke", "headache", "dizziness", "neurology", "neurologist", "migraine", "neur", "மூளை", "நரம்பியல்", "நரம்பு", "தலைவலி", "दिमाग", "न्यूरो", "सिरदर्द"],
    "orthopedics": ["ortho", "bone", "joint", "fracture", "knee", "spine", "orthopedic", "orthopedics", "orthopedist", "orth", "எலும்பு", "மூட்டு", "முழங்கால்", "हड्डी", "जोड़"],
    "pediatrics": ["pediatric", "pediatrics", "pediatrician", "child", "children", "baby", "infant", "newborn", "pedi", "குழந்தை", "குழந்தைகள்", "बच्चா", "शिशु"],
    "radiology": ["radio", "radiology", "radiologist", "imaging", "mri", "ct scan", "x-ray", "xray", "ultrasound", "scan", "dexa", "rad", "ஸ்கேன்", "எக்ஸ்ரே", "கதிரியக்கம்", "रेडियोलॉजी", "एक्स-रे", "सीटी स्कैन", "स्कैन"],
    "oncology": ["onco", "oncology", "oncologist", "cancer", "tumor", "chemotherapy", "onco", "புற்றுநோய்", "கட்டி", "ऑन्कोलॉजी", "कैंसर", "ट्यूमर"],
    "general medicine": ["genmed", "internal", "physician", "general medicine", "internal medicine", "preventive", "fever", "cough", "cold", "பொது மருத்துவம்", "பொது", "காய்ச்சல்", "सामान्य चिकित्सा", "बुखार", "चिकित्सक"],
    "emergency": ["emergency", "trauma", "casualty", "critical", "resuscitation", "ambulance", "108", "emrg", "அவசரம்", "விபத்து", "இமர்ஜென்சி", "इमरजेंसी", "आपातकालीन"],
}


def search_departments(db: Session, query: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search active clinical departments by name, code, description, or specialty alias."""
    q = db.query(Department).filter(Department.is_active == True)
    if query:
        q_clean = query.strip().lower()
        matching_stems = [q_clean]
        for canonical, aliases in SPECIALTY_ALIASES.items():
            if q_clean == canonical or any(
                q_clean == a or (a.isascii() and re.search(r"\b" + re.escape(a) + r"\b", q_clean)) or (not a.isascii() and a in q_clean)
                for a in aliases
            ):
                matching_stems.extend([canonical] + aliases)
        matching_stems = list(set(matching_stems))
        conds = []
        for stem in matching_stems:
            if len(stem) <= 4 and stem.isascii():
                conds.append(Department.code.ilike(f"%{stem}%"))
                conds.append(Department.name.ilike(f"{stem}%"))
                conds.append(Department.name.ilike(f"% {stem}%"))
                conds.append(Department.description.ilike(f"{stem}%"))
                conds.append(Department.description.ilike(f"% {stem}%"))
            else:
                conds.append(Department.name.ilike(f"%{stem}%"))
                conds.append(Department.code.ilike(f"%{stem}%"))
                conds.append(Department.description.ilike(f"%{stem}%"))
        q = q.filter(or_(*conds))
    depts = q.order_by(Department.name.asc()).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "code": d.code,
            "description": d.description,
            "location": d.location,
            "floor": d.floor,
            "extension": d.extension,
        }
        for d in depts
    ]


def search_doctors(
    db: Session,
    specialty: Optional[str] = None,
    department_id: Optional[int] = None,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search active doctors by specialty, department ID, department name/code, or name."""
    q = db.query(Doctor).join(Department).filter(Doctor.is_active == True, Department.is_active == True)
    if department_id:
        q = q.filter(Doctor.department_id == department_id)
    if specialty:
        s_clean = specialty.strip().lower()
        matching_stems = [s_clean]
        for canonical, aliases in SPECIALTY_ALIASES.items():
            if s_clean == canonical or any(
                s_clean == a or (a.isascii() and re.search(r"\b" + re.escape(a) + r"\b", s_clean)) or (not a.isascii() and a in s_clean)
                for a in aliases
            ):
                matching_stems.extend([canonical] + aliases)
        matching_stems = list(set(matching_stems))

        conds = []
        for stem in matching_stems:
            if len(stem) <= 4 and stem.isascii():
                conds.append(Department.code.ilike(f"%{stem}%"))
                conds.append(Doctor.specialty.ilike(f"{stem}%"))
                conds.append(Doctor.specialty.ilike(f"% {stem}%"))
                conds.append(Department.name.ilike(f"{stem}%"))
                conds.append(Department.name.ilike(f"% {stem}%"))
            else:
                conds.append(Doctor.specialty.ilike(f"%{stem}%"))
                conds.append(Department.name.ilike(f"%{stem}%"))
                conds.append(Department.code.ilike(f"%{stem}%"))
        q = q.filter(or_(*conds))

    if query:
        search_filter = f"%{query.strip()}%"
        q = q.filter(
            or_(
                Doctor.name.ilike(search_filter),
                Doctor.specialty.ilike(search_filter),
                Department.name.ilike(search_filter),
                Department.code.ilike(search_filter),
            )
        )

    doctors = q.order_by(Doctor.name.asc()).all()
    return [
        {
            "id": doc.id,
            "name": doc.name,
            "specialty": doc.specialty,
            "qualifications": doc.qualifications,
            "experience": doc.experience,
            "consultation_fee": float(doc.consultation_fee),
            "room_number": doc.room_number,
            "department_id": doc.department_id,
            "department_name": doc.department.name if doc.department else "Outpatient Wing",
        }
        for doc in doctors
    ]


def check_doctor_availability_tool(
    db: Session, doctor_id: int, target_date: date
) -> Dict[str, Any]:
    """Retrieve verified available consultation slots for a doctor on a specific date."""
    try:
        avail = get_doctor_availability(db=db, doctor_id=doctor_id, target_date=target_date)
        available_slots = [s.start_time for s in avail.available_slots if s.is_available]
        return {
            "doctor_id": avail.doctor_id,
            "doctor_name": avail.doctor_name,
            "date": avail.date,
            "is_on_duty": avail.is_on_duty,
            "working_hours": avail.working_hours,
            "available_slots": available_slots,
            "total_available": len(available_slots),
        }
    except Exception as e:
        return {
            "doctor_id": doctor_id,
            "date": str(target_date),
            "is_on_duty": False,
            "available_slots": [],
            "error": str(e),
        }


def book_appointment_tool(
    db: Session,
    doctor_id: int,
    appointment_date: date,
    start_time_str: str,
    patient_name: str,
    patient_phone: Optional[str] = None,
    appointment_type: str = "Consultation",
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute validated appointment booking inside a transaction and return the persisted record."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        return {"success": False, "error": f"Doctor ID {doctor_id} not found."}

    # Parse start time supporting both HH:MM and HH:MM:SS
    clean_time = start_time_str.strip()
    try:
        if len(clean_time.split(":")) == 3:
            parsed_time = datetime.strptime(clean_time, "%H:%M:%S").time()
        else:
            parsed_time = datetime.strptime(clean_time, "%H:%M").time()
    except ValueError:
        return {"success": False, "error": f"Invalid start time format '{start_time_str}'. Expected HH:MM."}

    payload = AppointmentCreate(
        doctor_id=doctor.id,
        department_id=doctor.department_id,
        appointment_date=appointment_date,
        start_time=parsed_time,
        patient_name=patient_name.strip(),
        patient_phone=patient_phone.strip() if patient_phone else None,
        appointment_type=appointment_type,
        notes=notes or "Booked via MediVoice Multilingual AI Assistant",
    )

    try:
        appointment = book_appointment(db=db, payload=payload)
        return {
            "success": True,
            "appointment_id": appointment.id,
            "booking_reference": appointment.booking_reference,
            "doctor_id": appointment.doctor_id,
            "doctor_name": doctor.name,
            "department_name": doctor.department.name if doctor.department else "Outpatient Wing",
            "appointment_date": str(appointment.appointment_date),
            "start_time": appointment.start_time.strftime("%H:%M"),
            "end_time": appointment.end_time.strftime("%H:%M"),
            "status": appointment.status,
            "queue_token": appointment.queue_entry.token if appointment.queue_entry else None,
        }
    except Exception as exc:
        # Check alternative slots for this date to offer to the patient
        alt_slots = []
        try:
            avail = check_doctor_availability_tool(db, doctor_id, appointment_date)
            alt_slots = avail.get("available_slots", [])[:4]
        except Exception:
            pass

        return {
            "success": False,
            "error": getattr(exc, "detail", str(exc)),
            "alternative_slots": alt_slots,
        }


def reschedule_appointment_tool(
    db: Session,
    booking_reference: str,
    patient_phone: str,
    new_date: date,
    new_start_time_str: str,
) -> Dict[str, Any]:
    """Verify reference and patient phone, then atomically reschedule the appointment."""
    appointment = (
        db.query(Appointment)
        .join(Patient)
        .filter(
            Appointment.booking_reference == booking_reference.strip().upper(),
            Patient.phone == patient_phone.strip(),
        )
        .first()
    )

    if not appointment:
        return {
            "success": False,
            "error": "No appointment matching that booking reference and patient phone number was found.",
        }

    try:
        new_time = datetime.strptime(new_start_time_str.strip(), "%H:%M").time()
    except ValueError:
        return {"success": False, "error": "Invalid time format. Please provide time as HH:MM (e.g., 10:30)."}

    try:
        updated = reschedule_appointment(
            db=db,
            appointment_id=appointment.id,
            new_date=new_date,
            new_start_time=new_time,
        )
        return {
            "success": True,
            "appointment_id": updated.id,
            "booking_reference": updated.booking_reference,
            "doctor_name": updated.doctor.name if updated.doctor else "Specialist",
            "new_date": str(updated.appointment_date),
            "new_start_time": updated.start_time.strftime("%H:%M"),
            "new_end_time": updated.end_time.strftime("%H:%M"),
            "status": updated.status,
        }
    except Exception as exc:
        return {"success": False, "error": getattr(exc, "detail", str(exc))}


def cancel_appointment_tool(
    db: Session,
    booking_reference: str,
    patient_phone: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify reference and phone number, then cancel the appointment."""
    appointment = (
        db.query(Appointment)
        .join(Patient)
        .filter(
            Appointment.booking_reference == booking_reference.strip().upper(),
            Patient.phone == patient_phone.strip(),
        )
        .first()
    )

    if not appointment:
        return {
            "success": False,
            "error": "No appointment matching that booking reference and phone number was found.",
        }

    try:
        cancelled = cancel_appointment(db=db, appointment_id=appointment.id, reason=reason)
        return {
            "success": True,
            "appointment_id": cancelled.id,
            "booking_reference": cancelled.booking_reference,
            "status": cancelled.status,
            "message": "Appointment has been cancelled successfully.",
        }
    except Exception as exc:
        return {"success": False, "error": getattr(exc, "detail", str(exc))}


def lookup_appointment_tool(
    db: Session, booking_reference: str, patient_phone: str
) -> Dict[str, Any]:
    """Look up an appointment requiring strict booking reference and matching phone number."""
    appointment = (
        db.query(Appointment)
        .join(Patient)
        .filter(
            Appointment.booking_reference == booking_reference.strip().upper(),
            Patient.phone == patient_phone.strip(),
        )
        .first()
    )

    if not appointment:
        return {
            "found": False,
            "message": "Appointment not found. Please verify your booking reference and contact phone number.",
        }

    return {
        "found": True,
        "booking_reference": appointment.booking_reference,
        "patient_name": appointment.patient.display_name if appointment.patient else "Patient",
        "doctor_name": appointment.doctor.name if appointment.doctor else "Specialist",
        "department_name": appointment.department.name if appointment.department else "Outpatient",
        "appointment_date": str(appointment.appointment_date),
        "start_time": appointment.start_time.strftime("%H:%M"),
        "end_time": appointment.end_time.strftime("%H:%M"),
        "status": appointment.status,
        "room_number": appointment.doctor.room_number if appointment.doctor else "OPD",
        "queue_token": appointment.queue_entry.token if appointment.queue_entry else None,
    }


def get_department_directions_tool(
    db: Session, department_name_or_code: str
) -> Dict[str, Any]:
    """Retrieve verified campus directions and location for a hospital department."""
    import re
    # Strip punctuation and conversational filler words
    no_punct = re.sub(r"[^\w\s]", " ", department_name_or_code)
    cleaned = re.sub(
        r"(?i)\b(where|is|are|the|department|departments|floor|wing|location|of|how|do|i|get|to|can|find|please|tell|me|about|located|at)\b",
        " ",
        no_punct,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    search_term = cleaned if len(cleaned) >= 2 else department_name_or_code.strip()

    dept = (
        db.query(Department)
        .filter(
            or_(
                Department.name.ilike(f"%{search_term}%"),
                Department.code.ilike(f"%{search_term}%"),
                Department.description.ilike(f"%{search_term}%"),
            )
        )
        .first()
    )

    if not dept:
        # Check alias/stem match
        s_clean = search_term.lower()
        matching_stems = []
        for canonical, aliases in SPECIALTY_ALIASES.items():
            if s_clean in canonical or any(a in s_clean or s_clean in a for a in aliases):
                matching_stems.extend([canonical] + aliases)
        if matching_stems:
            conds = []
            for stem in matching_stems:
                conds.append(Department.name.ilike(f"%{stem}%"))
                conds.append(Department.code.ilike(f"%{stem}%"))
                conds.append(Department.description.ilike(f"%{stem}%"))
            dept = db.query(Department).filter(or_(*conds)).first()

    if not dept:
        return {
            "found": False,
            "message": f"Department matching '{department_name_or_code}' was not found in our directory.",
        }

    return {
        "found": True,
        "name": dept.name,
        "code": dept.code,
        "location": dept.location,
        "floor": dept.floor,
        "extension": dept.extension,
        "description": dept.description,
    }
