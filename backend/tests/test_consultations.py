from datetime import date, time, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.queue import QueueEntry


@pytest.fixture
def auth_doctor_token(client: TestClient) -> str:
    """Authenticate with synthetic doctor account and return JWT access token."""
    res = client.post("/api/auth/staff-token", json={"staff_id": "EMP-1022", "passcode": "hospital123"})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_doctor_creates_consultation_note_with_prescriptions(
    client: TestClient,
    sample_hospital_data,
    db_session: Session,
    auth_doctor_token: str,
):
    """Verify that a doctor records diagnosis and prescriptions, automatically completing the appointment."""
    doctor = sample_hospital_data["doctor"]
    dept = sample_hospital_data["department"]
    patient = sample_hospital_data["patient"]

    # Create active appointment
    apt = Appointment(
        booking_reference="APT-EHR-001",
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        appointment_date=date.today(),
        start_time=time(10, 0),
        end_time=time(10, 30),
        status="in-progress",
    )
    db_session.add(apt)
    db_session.flush()

    q_entry = QueueEntry(
        appointment_id=apt.id,
        token="CARD-EHR",
        status="called",
        priority="normal",
    )
    db_session.add(q_entry)
    db_session.commit()

    headers = {"Authorization": f"Bearer {auth_doctor_token}"}
    payload = {
        "appointment_id": apt.id,
        "chief_complaint": "Recurrent palpitations and exertional dyspnea",
        "diagnosis": "Sinus Tachycardia with mild hypertension",
        "clinical_notes": "BP: 135/85 mmHg, HR: 98 bpm. Normal S1/S2 heart sounds, no murmur detected.",
        "prescriptions": [
            {
                "medication_name": "Metoprolol Succinate",
                "dosage": "25mg",
                "frequency": "Once daily in morning",
                "duration_days": 30,
                "instructions": "Take after breakfast with water",
            },
            {
                "medication_name": "Aspirin",
                "dosage": "75mg",
                "frequency": "Once daily",
                "duration_days": 30,
                "instructions": "Take after lunch",
            },
        ],
        "follow_up_date": str(date.today() + timedelta(days=30)),
    }

    res = client.post("/api/consultations", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["diagnosis"] == "Sinus Tachycardia with mild hypertension"
    assert len(data["prescriptions"]) == 2
    assert data["prescriptions"][0]["medication_name"] == "Metoprolol Succinate"

    # Verify appointment and queue status progressed to completed
    db_session.refresh(apt)
    db_session.refresh(q_entry)
    assert apt.status == "completed"
    assert q_entry.status == "completed"

    # Verify authorized staff can read note and history
    res_get = client.get(f"/api/consultations/appointment/{apt.id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["diagnosis"] == "Sinus Tachycardia with mild hypertension"

    res_history = client.get(f"/api/consultations/patient/{patient.id}", headers=headers)
    assert res_history.status_code == 200
    assert len(res_history.json()) >= 1

    # Verify unauthenticated request to read sensitive EHR note is rejected
    res_unauth_note = client.get(f"/api/consultations/appointment/{apt.id}")
    assert res_unauth_note.status_code == 401

    res_unauth_history = client.get(f"/api/consultations/patient/{patient.id}")
    assert res_unauth_history.status_code == 401


def test_duplicate_consultation_note_rejected(
    client: TestClient,
    sample_hospital_data,
    db_session: Session,
    auth_doctor_token: str,
):
    """Verify that multiple notes cannot be registered for the same appointment."""
    doctor = sample_hospital_data["doctor"]
    dept = sample_hospital_data["department"]
    patient = sample_hospital_data["patient"]

    apt = Appointment(
        booking_reference="APT-EHR-DUP",
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        appointment_date=date.today(),
        start_time=time(11, 0),
        end_time=time(11, 30),
        status="in-progress",
    )
    db_session.add(apt)
    db_session.commit()

    headers = {"Authorization": f"Bearer {auth_doctor_token}"}
    payload = {
        "appointment_id": apt.id,
        "chief_complaint": "General weakness",
        "diagnosis": "Mild dehydration",
    }

    res1 = client.post("/api/consultations", json=payload, headers=headers)
    assert res1.status_code == 201

    # Attempt second note for same appointment
    res2 = client.post("/api/consultations", json=payload, headers=headers)
    assert res2.status_code == 409


def test_unauthenticated_request_rejected(client: TestClient, sample_hospital_data):
    """Verify non-staff requests cannot create clinical consultation notes."""
    payload = {
        "appointment_id": 999,
        "chief_complaint": "Fake complaint",
        "diagnosis": "Unauthorized access",
    }
    res = client.post("/api/consultations", json=payload)
    assert res.status_code == 401
