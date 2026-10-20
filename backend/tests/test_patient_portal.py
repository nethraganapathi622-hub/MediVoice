from datetime import date, time, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.schedule import DoctorSchedule


def test_patient_otp_request_and_verification(client: TestClient, sample_hospital_data):
    """Test OTP request and token verification workflow."""
    phone = "+91 98400 11223"

    # Request OTP
    res_req = client.post("/api/patient/auth/request-otp", json={"phone": phone})
    assert res_req.status_code == 200
    assert res_req.json()["success"] is True

    # Verify with invalid OTP
    res_bad = client.post("/api/patient/auth/verify-otp", json={"phone": phone, "otp_code": "000000"})
    assert res_bad.status_code == 400

    # Verify with valid OTP
    res_verify = client.post("/api/patient/auth/verify-otp", json={"phone": phone, "otp_code": "123456"})
    assert res_verify.status_code == 200
    data = res_verify.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["phone"] == "+919840011223" or data["phone"] == "+91 98400 11223"


def test_patient_appointment_lookup_privacy(client: TestClient, sample_hospital_data, db_session: Session):
    """Test lookup by reference requires exact matching phone number."""
    doctor = sample_hospital_data["doctor"]
    dept = sample_hospital_data["department"]

    # Create patient and appointment
    pat = Patient(display_name="Meena Raman", phone="+919876543210")
    db_session.add(pat)
    db_session.flush()

    apt = Appointment(
        booking_reference="APT-PRIVACY-01",
        patient_id=pat.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        appointment_date=date.today() + timedelta(days=2),
        start_time=time(10, 0),
        end_time=time(10, 30),
        status="booked",
    )
    db_session.add(apt)
    db_session.commit()

    # Wrong phone
    res_wrong = client.post(
        "/api/patient/appointments/lookup",
        json={"booking_reference": "APT-PRIVACY-01", "phone": "+91 00000 00000"},
    )
    assert res_wrong.status_code == 403

    # Correct phone
    res_ok = client.post(
        "/api/patient/appointments/lookup",
        json={"booking_reference": "APT-PRIVACY-01", "phone": "+91 98765 43210"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["booking_reference"] == "APT-PRIVACY-01"
    assert res_ok.json()["patient"]["display_name"] == "Meena Raman"


def test_patient_self_reschedule_and_cancel_ownership(client: TestClient, sample_hospital_data, db_session: Session):
    """Test patient can reschedule and cancel own appointments, but is blocked from mutating other patients' records."""
    doctor = sample_hospital_data["doctor"]
    dept = sample_hospital_data["department"]

    # Seed tomorrow schedule
    tomorrow = date.today() + timedelta(days=1)
    day_after = date.today() + timedelta(days=2)
    sched = DoctorSchedule(
        doctor_id=doctor.id,
        working_date=day_after,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched)

    # Patient A
    pat_a = Patient(display_name="Patient Alpha", phone="+919999911111")
    # Patient B
    pat_b = Patient(display_name="Patient Beta", phone="+919999922222")
    db_session.add_all([pat_a, pat_b])
    db_session.flush()

    apt_a = Appointment(
        booking_reference="APT-ALPHA-01",
        patient_id=pat_a.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        appointment_date=day_after,
        start_time=time(9, 30),
        end_time=time(10, 0),
        status="booked",
    )
    db_session.add(apt_a)
    db_session.commit()

    # Authenticate as Patient B
    res_auth_b = client.post("/api/patient/auth/verify-otp", json={"phone": "+919999922222", "otp_code": "123456"})
    token_b = res_auth_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Patient B tries to cancel Patient A's appointment -> 403 Forbidden
    res_cancel_b = client.post(
        f"/api/patient/appointments/{apt_a.id}/cancel",
        json={"reason": "Malicious attempt"},
        headers=headers_b,
    )
    assert res_cancel_b.status_code == 403

    # Authenticate as Patient A
    res_auth_a = client.post("/api/patient/auth/verify-otp", json={"phone": "+919999911111", "otp_code": "123456"})
    token_a = res_auth_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Patient A self-reschedules to 10:30 on day_after
    res_resched = client.post(
        f"/api/patient/appointments/{apt_a.id}/reschedule",
        json={"new_date": str(day_after), "new_start_time": "10:30:00"},
        headers=headers_a,
    )
    assert res_resched.status_code == 200
    assert str(res_resched.json()["start_time"]).startswith("10:30")

    # Patient A self-cancels
    res_cancel_a = client.post(
        f"/api/patient/appointments/{apt_a.id}/cancel",
        json={"reason": "Change of plans"},
        headers=headers_a,
    )
    assert res_cancel_a.status_code == 200
    assert res_cancel_a.json()["status"] == "cancelled"
