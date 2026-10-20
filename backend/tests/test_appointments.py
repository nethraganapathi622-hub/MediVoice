from datetime import date, datetime, time, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.schedule import DoctorSchedule


def test_appointment_booking_success(client: TestClient, sample_hospital_data):
    """Test successful creation of outpatient appointment."""
    doc_id = sample_hospital_data["doctor"].id
    dept_id = sample_hospital_data["department"].id

    # Use a future date to avoid past-time collision
    future_date = date.today() + timedelta(days=1)

    # Add schedule for future date
    # In test, we can call POST endpoint which expects doctor schedule
    # Let's seed future schedule in DB
    # First, let's test with future date
    payload = {
        "doctor_id": doc_id,
        "department_id": dept_id,
        "appointment_date": str(future_date),
        "start_time": "10:00:00",
        "patient_name": "Ramesh Kumar",
        "patient_phone": "+91 98888 22222",
        "appointment_type": "New Consultation",
        "notes": "Mild chest discomfort",
    }

    # Before scheduling future date, it should reject because no schedule exists for that date
    res_nosched = client.post("/api/appointments", json=payload)
    assert res_nosched.status_code == 409
    assert "not scheduled" in res_nosched.json()["detail"].lower()


def test_appointment_booking_and_doctor_double_booking(
    client: TestClient, sample_hospital_data, db_session: Session
):
    """Test that booking an existing slot succeeds, but a second overlapping request is rejected."""
    doc_id = sample_hospital_data["doctor"].id
    dept_id = sample_hospital_data["department"].id

    future_date = date.today() + timedelta(days=2)
    # Add schedule for future_date
    sched = DoctorSchedule(
        doctor_id=doc_id,
        working_date=future_date,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched)
    db_session.commit()

    payload_1 = {
        "doctor_id": doc_id,
        "department_id": dept_id,
        "appointment_date": str(future_date),
        "start_time": "10:00:00",
        "patient_name": "Patient Alpha",
        "patient_phone": "+91 91111 00001",
        "appointment_type": "Consultation",
    }

    res_1 = client.post("/api/appointments", json=payload_1)
    assert res_1.status_code == 201
    apt_data = res_1.json()
    assert apt_data["booking_reference"].startswith("APT-")
    assert apt_data["status"] == "booked"
    apt_1_id = apt_data["id"]

    # 2. Attempt double booking for same doctor & overlapping time
    payload_2 = {
        "doctor_id": doc_id,
        "department_id": dept_id,
        "appointment_date": str(future_date),
        "start_time": "10:15:00",  # Overlaps with 10:00 - 10:30
        "patient_name": "Patient Beta",
        "patient_phone": "+91 92222 00002",
        "appointment_type": "Consultation",
    }

    res_2 = client.post("/api/appointments", json=payload_2)
    assert res_2.status_code == 409
    assert "already booked" in res_2.json()["detail"].lower()

    # 3. Patient overlapping appointment check
    # Try to book Patient Alpha with another doctor during the same time window
    # Create a second doctor in the same dept
    doc_2 = Doctor(
        name="Dr. Second Doctor",
        department_id=dept_id,
        specialty="General Cardiology",
        qualifications="MBBS, MD",
        experience="8 years",
        consultation_fee=Decimal("600.00"),
        room_number="OPD 102",
        is_active=True,
    )
    db_session.add(doc_2)
    db_session.flush()

    sched_2 = DoctorSchedule(
        doctor_id=doc_2.id,
        working_date=future_date,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched_2)
    db_session.commit()

    payload_patient_conflict = {
        "doctor_id": doc_2.id,
        "department_id": dept_id,
        "appointment_date": str(future_date),
        "start_time": "10:00:00",
        "patient_id": apt_data["patient_id"],
        "patient_name": "Patient Alpha",
        "patient_phone": "+91 91111 00001",
    }
    res_pat_conflict = client.post("/api/appointments", json=payload_patient_conflict)
    assert res_pat_conflict.status_code == 409
    assert "patient already has an active overlapping appointment" in res_pat_conflict.json()["detail"].lower()


def test_appointment_past_date_rejection(client: TestClient, sample_hospital_data):
    """Test that appointment dates in the past are rejected."""
    doc_id = sample_hospital_data["doctor"].id
    dept_id = sample_hospital_data["department"].id
    past_date = date.today() - timedelta(days=1)

    payload = {
        "doctor_id": doc_id,
        "department_id": dept_id,
        "appointment_date": str(past_date),
        "start_time": "10:00:00",
        "patient_name": "Past Patient",
    }
    res = client.post("/api/appointments", json=payload)
    assert res.status_code == 400
    assert "past" in res.json()["detail"].lower()


def test_appointment_rescheduling_and_cancellation(
    client: TestClient, sample_hospital_data, db_session: Session
):
    """Test rescheduling (with collision protection) and cancellation freeing slot."""
    doc_id = sample_hospital_data["doctor"].id
    dept_id = sample_hospital_data["department"].id

    day_3 = date.today() + timedelta(days=3)
    sched = DoctorSchedule(
        doctor_id=doc_id,
        working_date=day_3,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched)
    db_session.commit()

    # Create appointment at 09:30
    payload = {
        "doctor_id": doc_id,
        "department_id": dept_id,
        "appointment_date": str(day_3),
        "start_time": "09:30:00",
        "patient_name": "Reschedule Patient",
    }
    res = client.post("/api/appointments", json=payload)
    assert res.status_code == 201
    apt_id = res.json()["id"]

    # Reschedule to 11:00 (valid)
    res_resched = client.patch(
        f"/api/appointments/{apt_id}/reschedule",
        json={"new_date": str(day_3), "new_start_time": "11:00:00"},
    )
    assert res_resched.status_code == 200
    assert res_resched.json()["status"] == "rescheduled"
    assert res_resched.json()["start_time"] == "11:00:00"

    # Cancel appointment
    res_cancel = client.post(
        f"/api/appointments/{apt_id}/cancel",
        json={"reason": "Patient requested cancellation"},
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"
    assert "Patient requested cancellation" in res_cancel.json()["notes"]

    # Now verify that the 11:00 slot is freed and can be booked again!
    res_rebook = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc_id,
            "department_id": dept_id,
            "appointment_date": str(day_3),
            "start_time": "11:00:00",
            "patient_name": "New Slot Patient",
        },
    )
    assert res_rebook.status_code == 201


def test_appointment_invalid_ids_and_error_responses(client: TestClient, sample_hospital_data):
    """Test appropriate 404 error responses for non-existent doctor, department, or appointment."""
    today = date.today() + timedelta(days=5)

    # 1. Non-existent doctor
    res_bad_doc = client.post(
        "/api/appointments",
        json={
            "doctor_id": 99999,
            "department_id": sample_hospital_data["department"].id,
            "appointment_date": str(today),
            "start_time": "10:00:00",
            "patient_name": "Test Patient",
        },
    )
    assert res_bad_doc.status_code == 404
    assert "doctor" in res_bad_doc.json()["detail"].lower()

    # 2. Non-existent department
    res_bad_dept = client.post(
        "/api/appointments",
        json={
            "doctor_id": sample_hospital_data["doctor"].id,
            "department_id": 99999,
            "appointment_date": str(today),
            "start_time": "10:00:00",
            "patient_name": "Test Patient",
        },
    )
    assert res_bad_dept.status_code == 404
    assert "department" in res_bad_dept.json()["detail"].lower()

    # 3. Non-existent appointment GET
    res_bad_apt = client.get("/api/appointments/99999")
    assert res_bad_apt.status_code == 404

    # 4. Non-existent appointment cancel
    res_bad_cancel = client.post("/api/appointments/99999/cancel", json={"reason": "test"})
    assert res_bad_cancel.status_code == 404


def test_appointment_transaction_rollback(
    client: TestClient, sample_hospital_data, db_session: Session
):
    """Test that a failed appointment booking rolls back transaction cleanly."""
    doc_id = sample_hospital_data["doctor"].id
    dept_id = sample_hospital_data["department"].id

    initial_apt_count = db_session.query(Appointment).count()

    # Attempt to book a past date (which raises HTTP 400 before or during transaction)
    past_date = date.today() - timedelta(days=2)
    res_fail = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc_id,
            "department_id": dept_id,
            "appointment_date": str(past_date),
            "start_time": "10:00:00",
            "patient_name": "Rollback Check Patient",
        },
    )
    assert res_fail.status_code == 400

    # Ensure no appointment was persisted in database
    final_apt_count = db_session.query(Appointment).count()
    assert final_apt_count == initial_apt_count

