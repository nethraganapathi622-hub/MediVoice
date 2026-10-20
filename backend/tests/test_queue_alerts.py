from datetime import date, time, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.models.schedule import DoctorSchedule


def test_queue_lifecycle(client: TestClient, sample_hospital_data, db_session: Session):
    """Test patient check-in, token generation, calling, and completion."""
    doc_id = sample_hospital_data["doctor"].id
    dept_id = sample_hospital_data["department"].id

    day_4 = date.today() + timedelta(days=4)
    sched = DoctorSchedule(
        doctor_id=doc_id,
        working_date=day_4,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched)
    db_session.commit()

    # Book appointment
    res_apt = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc_id,
            "department_id": dept_id,
            "appointment_date": str(day_4),
            "start_time": "09:00:00",
            "patient_name": "Queue Test Patient",
        },
    )
    assert res_apt.status_code == 201
    apt_id = res_apt.json()["id"]

    # Check in
    res_checkin = client.post(
        "/api/queue/check-in",
        json={"appointment_id": apt_id, "priority": "urgent"},
    )
    assert res_checkin.status_code == 201
    queue_data = res_checkin.json()
    assert queue_data["status"] == "waiting"
    assert queue_data["priority"] == "urgent"
    assert "TESTCARD-" in queue_data["token"]
    queue_id = queue_data["id"]

    # List queue
    res_list = client.get("/api/queue")
    assert res_list.status_code == 200
    assert any(q["id"] == queue_id for q in res_list.json())

    # Call patient
    res_call = client.post(f"/api/queue/{queue_id}/call")
    assert res_call.status_code == 200
    assert res_call.json()["status"] == "called"
    assert res_call.json()["called_time"] is not None

    # Complete consultation
    res_complete = client.post(f"/api/queue/{queue_id}/complete")
    assert res_complete.status_code == 200
    assert res_complete.json()["status"] == "completed"
    assert res_complete.json()["completed_time"] is not None


def test_triage_alerts_and_acknowledgement(client: TestClient, sample_hospital_data):
    """Test triage alert creation, filtering, and staff authorization for acknowledgement."""
    # Create alert
    res_create = client.post(
        "/api/alerts",
        json={
            "priority": "critical",
            "alert_type": "trauma_priority",
            "description": "Incoming severe trauma patient to Bay 1",
            "location": "Trauma Bay 1",
        },
    )
    assert res_create.status_code == 201
    alert_id = res_create.json()["id"]
    assert res_create.json()["status"] == "active"

    # Filter alerts by priority
    res_crit = client.get("/api/alerts?priority=critical")
    assert res_crit.status_code == 200
    assert any(a["id"] == alert_id for a in res_crit.json())

    # Attempt acknowledgement without staff info
    res_bad_ack = client.post(
        f"/api/alerts/{alert_id}/acknowledge",
        json={"staff_id": "", "staff_name": ""},
    )
    assert res_bad_ack.status_code in [401, 422]

    # Authorized acknowledgement with staff credentials
    res_ack = client.post(
        f"/api/alerts/{alert_id}/acknowledge",
        json={"staff_id": "STF-4401", "staff_name": "Nurse Radha Nair"},
        headers={"X-Staff-Role": "TriageLead"},
    )
    assert res_ack.status_code == 200
    ack_data = res_ack.json()
    assert ack_data["status"] == "acknowledged"
    assert "Nurse Radha Nair" in ack_data["acknowledged_by"]
    assert ack_data["acknowledged_at"] is not None


def test_queue_token_uniqueness_and_duplicate_checkin(
    client: TestClient, sample_hospital_data, db_session: Session
):
    """Test that check-in produces unique tokens for distinct appointments and prevents duplicate check-in."""
    doc_id = sample_hospital_data["doctor"].id
    dept_id = sample_hospital_data["department"].id

    day_5 = date.today() + timedelta(days=5)
    sched = DoctorSchedule(
        doctor_id=doc_id,
        working_date=day_5,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched)
    db_session.commit()

    # Appointment 1
    res1 = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc_id,
            "department_id": dept_id,
            "appointment_date": str(day_5),
            "start_time": "09:00:00",
            "patient_name": "Patient Token 1",
        },
    )
    assert res1.status_code == 201
    apt1_id = res1.json()["id"]

    # Appointment 2
    res2 = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc_id,
            "department_id": dept_id,
            "appointment_date": str(day_5),
            "start_time": "09:30:00",
            "patient_name": "Patient Token 2",
        },
    )
    assert res2.status_code == 201
    apt2_id = res2.json()["id"]

    # Check-in apt 1
    q1 = client.post("/api/queue/check-in", json={"appointment_id": apt1_id})
    assert q1.status_code == 201
    token1 = q1.json()["token"]

    # Check-in apt 2
    q2 = client.post("/api/queue/check-in", json={"appointment_id": apt2_id})
    assert q2.status_code == 201
    token2 = q2.json()["token"]

    # Verify uniqueness
    assert token1 != token2

    # Attempt duplicate check-in for apt 1
    dup_res = client.post("/api/queue/check-in", json={"appointment_id": apt1_id})
    assert dup_res.status_code == 409
    assert "already checked in" in dup_res.json()["detail"].lower()


def test_queue_invalid_ids(client: TestClient):
    """Test 404 responses for non-existent queue entries."""
    res_call = client.post("/api/queue/99999/call")
    assert res_call.status_code == 404

    res_comp = client.post("/api/queue/99999/complete")
    assert res_comp.status_code == 404

