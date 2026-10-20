"""Idempotent database seeding script for MediVoice development.

Usage:
    python -m app.seed
"""

import logging
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.database import SessionLocal, engine, Base
import app.models  # noqa: F401
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.schedule import DoctorSchedule
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.queue import QueueEntry
from app.models.alert import TriageAlert

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("medivoice.seed")

# Canonical seed data
SEED_DEPARTMENTS = [
    {
        "code": "CARD",
        "name": "Cardiology & Heart Care",
        "location": "Wing B, 2nd Floor",
        "floor": "2nd Floor",
        "extension": "Ext. 2401",
        "description": "Comprehensive cardiac diagnostics, 2D Echo, interventional cardiology, and coronary recovery suites.",
    },
    {
        "code": "NEUR",
        "name": "Neurology & Stroke Clinic",
        "location": "Wing C, 3rd Floor",
        "floor": "3rd Floor",
        "extension": "Ext. 3105",
        "description": "Advanced neurological diagnostics, stroke triage, epilepsy monitoring, and acute neuro-rehabilitation.",
    },
    {
        "code": "ORTH",
        "name": "Orthopedics & Joint Replacement",
        "location": "Wing A, 1st Floor",
        "floor": "1st Floor",
        "extension": "Ext. 1204",
        "description": "Arthroscopic surgery, joint replacement, trauma recovery, and bone density assessment unit.",
    },
    {
        "code": "PEDI",
        "name": "Pediatrics & Child Wellness",
        "location": "Wing D, 2nd Floor",
        "floor": "2nd Floor",
        "extension": "Ext. 2502",
        "description": "Child-friendly outpatient clinic, neonatal follow-up, immunization, and growth assessment.",
    },
    {
        "code": "EMRG",
        "name": "Emergency & Critical Trauma Unit",
        "location": "Block A, Ground Floor (Red Zone)",
        "floor": "Ground Floor",
        "extension": "Casualty 108",
        "description": "24/7 acute resuscitation, triage bays, mobile imaging, and immediate surgical trauma access.",
    },
    {
        "code": "RAD",
        "name": "Radiology & Diagnostic Imaging",
        "location": "Basement 1, Diagnostic Center",
        "floor": "Basement 1",
        "extension": "Ext. 0402",
        "description": "3T MRI, 128-Slice Dual Source CT, Digital X-Ray, High-Resolution Ultrasound, and DEXA scans.",
    },
    {
        "code": "GENMED",
        "name": "Internal & Preventive Medicine",
        "location": "Wing A, Ground Floor",
        "floor": "Ground Floor",
        "extension": "Ext. 1008",
        "description": "Routine health examinations, chronic metabolic care, diabetes management, and geriatric care.",
    },
    {
        "code": "ONCO",
        "name": "Medical Oncology & Day Care",
        "location": "Wing E, 4th Floor",
        "floor": "4th Floor",
        "extension": "Ext. 4209",
        "description": "Outpatient chemotherapy day care, tumor board consultations, and supportive precision oncology.",
    },
]

SEED_DOCTORS = [
    {
        "name": "Dr. Arvind Ramanathan",
        "dept_code": "CARD",
        "specialty": "Senior Consultant Cardiologist",
        "qualifications": "MBBS, MD (Gen Med), DM (Cardiology)",
        "experience": "18+ years",
        "consultation_fee": Decimal("800.00"),
        "room_number": "OPD 204, Wing B",
    },
    {
        "name": "Dr. Meera Vasudevan",
        "dept_code": "NEUR",
        "specialty": "Chief Neurologist & Stroke Specialist",
        "qualifications": "MBBS, MD, DM (Neurology), FAAN",
        "experience": "15+ years",
        "consultation_fee": Decimal("900.00"),
        "room_number": "OPD 312, Wing C",
    },
    {
        "name": "Dr. Rajesh K. Sundaram",
        "dept_code": "ORTH",
        "specialty": "Senior Orthopedic & Joint Surgeon",
        "qualifications": "MBBS, MS (Orthopedics), MCh",
        "experience": "21+ years",
        "consultation_fee": Decimal("850.00"),
        "room_number": "OPD 108, Wing A",
    },
    {
        "name": "Dr. Ananya Sen",
        "dept_code": "PEDI",
        "specialty": "Consultant Pediatrician",
        "qualifications": "MBBS, DCH, MD (Pediatrics)",
        "experience": "11+ years",
        "consultation_fee": Decimal("700.00"),
        "room_number": "OPD 218, Wing D",
    },
    {
        "name": "Dr. Vikramaditya Rao",
        "dept_code": "EMRG",
        "specialty": "Emergency Medicine Director",
        "qualifications": "MBBS, FEM, MD (Emergency Medicine)",
        "experience": "16+ years",
        "consultation_fee": Decimal("600.00"),
        "room_number": "Trauma Desk, Block A",
    },
    {
        "name": "Dr. Pradeep Narayanan",
        "dept_code": "GENMED",
        "specialty": "Lead Physician, Internal Medicine",
        "qualifications": "MBBS, MD (General Medicine)",
        "experience": "14+ years",
        "consultation_fee": Decimal("650.00"),
        "room_number": "OPD 102, Wing A",
    },
    {
        "name": "Dr. Sunita Kulkarni",
        "dept_code": "RAD",
        "specialty": "Head of Diagnostic Imaging",
        "qualifications": "MBBS, DMRD, MD (Radiology)",
        "experience": "17+ years",
        "consultation_fee": Decimal("750.00"),
        "room_number": "Reporting Bay 3, Basement 1",
    },
    {
        "name": "Dr. Shalini Mukhopadhyay",
        "dept_code": "ONCO",
        "specialty": "Consultant Medical Oncologist",
        "qualifications": "MBBS, MD, DNB (Medical Oncology)",
        "experience": "12+ years",
        "consultation_fee": Decimal("1000.00"),
        "room_number": "OPD 405, Wing E",
    },
]


def seed_database() -> None:
    """Idempotently seed the hospital database with departments, doctors, and schedules."""
    settings = get_settings()
    logger.info("Connecting to database at configured DATABASE_URL: %s", settings.safe_database_url)

    try:
        # Create tables if they do not exist (safe: checkfirst=True)
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except OperationalError as exc:
        logger.error(
            "Failed to connect to PostgreSQL at %s.\n"
            "Error: %s\n\n"
            "To fix this:\n"
            "1. Verify your local PostgreSQL service is running.\n"
            "2. Set the valid credentials in backend/.env: DATABASE_URL=postgresql+psycopg2://<user>:<password>@localhost:5432/<dbname>\n"
            "3. If using Docker, run: docker run --name medivoice-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=medivoice_db -p 5432:5432 -d postgres:16-alpine",
            settings.safe_database_url,
            type(exc).__name__,
        )
        sys.exit(1)

    db = SessionLocal()
    try:
        # 1. Seed Departments
        dept_map = {}
        for d_info in SEED_DEPARTMENTS:
            dept = db.query(Department).filter(Department.code == d_info["code"]).first()
            if not dept:
                dept = Department(
                    code=d_info["code"],
                    name=d_info["name"],
                    location=d_info["location"],
                    floor=d_info["floor"],
                    extension=d_info["extension"],
                    description=d_info["description"],
                    is_active=True,
                )
                db.add(dept)
                db.flush()
                logger.info("Created department: %s (%s)", dept.name, dept.code)
            dept_map[d_info["code"]] = dept

        # 2. Seed Doctors
        doc_map = {}
        for doc_info in SEED_DOCTORS:
            dept = dept_map.get(doc_info["dept_code"])
            if not dept:
                continue

            doctor = (
                db.query(Doctor)
                .filter(Doctor.name == doc_info["name"], Doctor.department_id == dept.id)
                .first()
            )
            if not doctor:
                doctor = Doctor(
                    name=doc_info["name"],
                    department_id=dept.id,
                    specialty=doc_info["specialty"],
                    qualifications=doc_info["qualifications"],
                    experience=doc_info["experience"],
                    consultation_fee=doc_info["consultation_fee"],
                    room_number=doc_info["room_number"],
                    is_active=True,
                )
                db.add(doctor)
                db.flush()
                logger.info("Created doctor: %s (%s)", doctor.name, doctor.specialty)
            doc_map[doctor.name] = doctor

        # 3. Seed Schedules (Today + next 14 days)
        today = date.today()
        for doctor in doc_map.values():
            for day_offset in range(14):
                sched_date = today + timedelta(days=day_offset)
                existing_sched = (
                    db.query(DoctorSchedule)
                    .filter(
                        DoctorSchedule.doctor_id == doctor.id,
                        DoctorSchedule.working_date == sched_date,
                    )
                    .first()
                )
                if not existing_sched:
                    schedule = DoctorSchedule(
                        doctor_id=doctor.id,
                        working_date=sched_date,
                        start_time=time(9, 0),
                        end_time=time(13, 0),
                        slot_duration_minutes=30,
                        is_available=True,
                    )
                    db.add(schedule)

        # 4. Seed Demo Patients (if not present)
        patient_1 = db.query(Patient).filter(Patient.display_name == "Karthik Subramanian").first()
        if not patient_1:
            patient_1 = Patient(
                display_name="Karthik Subramanian",
                phone="+91 98401 23456",
                email="karthik.s@example.com",
            )
            db.add(patient_1)
            db.flush()

        patient_2 = db.query(Patient).filter(Patient.display_name == "Meenakshi Sundaresan").first()
        if not patient_2:
            patient_2 = Patient(
                display_name="Meenakshi Sundaresan",
                phone="+91 98402 34567",
                email="meenakshi.s@example.com",
            )
            db.add(patient_2)
            db.flush()

        # 5. Seed Initial Alerts (if not present)
        existing_alert = db.query(TriageAlert).filter(TriageAlert.alert_type == "trauma_priority").first()
        if not existing_alert:
            alert = TriageAlert(
                priority="critical",
                alert_type="trauma_priority",
                description="Incoming road traffic trauma patient arriving via 108 ambulance. Resuscitation team on standby.",
                location="Block A - Bay 1",
                status="active",
                department_id=dept_map.get("EMRG").id if "EMRG" in dept_map else None,
            )
            db.add(alert)

        db.commit()
        logger.info("Database seeding successfully completed!")
    except Exception as exc:
        db.rollback()
        logger.exception("Error while seeding database: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
