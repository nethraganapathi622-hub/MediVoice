from datetime import date, time, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.schedule import DoctorSchedule
from app.services.notification_service import (
    clear_notification_history,
    get_notification_history,
)


@pytest.fixture(autouse=True)
def clean_notifications():
    """Ensure clean notification history before each test."""
    clear_notification_history()
    yield
    clear_notification_history()


def test_appointment_booking_dispatches_notification(client: TestClient, sample_hospital_data, db_session: Session):
    """Verify that completing a booking automatically creates a multilingual notification record."""
    doctor = sample_hospital_data["doctor"]
    dept = sample_hospital_data["department"]
    tomorrow = date.today() + timedelta(days=1)

    # Add schedule for tomorrow
    sched = DoctorSchedule(
        doctor_id=doctor.id,
        working_date=tomorrow,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched)
    db_session.flush()

    res = client.post(
        "/api/appointments",
        json={
            "doctor_id": doctor.id,
            "department_id": dept.id,
            "appointment_date": str(tomorrow),
            "start_time": "10:30:00",
            "patient_name": "Suresh Raina",
            "patient_phone": "+91 98400 99887",
        },
    )
    assert res.status_code == 201
    booking_ref = res.json()["booking_reference"]

    # Verify notification history
    history = get_notification_history()
    assert len(history) > 0
    notif = history[0]
    assert notif["template"] == "appointment_confirmed"
    assert notif["recipient_phone"] == "+91 98400 99887"
    assert booking_ref in notif["message"]


def test_queue_check_in_dispatches_whatsapp_notification(client: TestClient, sample_hospital_data, db_session: Session):
    """Verify that checking in for an OPD queue token generates a queue notification."""
    doctor = sample_hospital_data["doctor"]
    dept = sample_hospital_data["department"]
    today = date.today()

    # Book for tomorrow so queue entry is generated at check-in time
    tomorrow = today + timedelta(days=1)
    sched = DoctorSchedule(
        doctor_id=doctor.id,
        working_date=tomorrow,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched)
    db_session.flush()
    res_book = client.post(
        "/api/appointments",
        json={
            "doctor_id": doctor.id,
            "department_id": dept.id,
            "appointment_date": str(tomorrow),
            "start_time": "10:00:00",
            "patient_name": "Kavitha Raj",
            "patient_phone": "+91 91234 56789",
        },
    )
    assert res_book.status_code == 201
    apt_id = res_book.json()["id"]

    # Clear booking notification to isolate check-in test
    clear_notification_history()

    # Check-in
    res_checkin = client.post("/api/queue/check-in", json={"appointment_id": apt_id})
    assert res_checkin.status_code == 201
    token = res_checkin.json()["token"]

    history = get_notification_history()
    assert len(history) > 0
    notif = history[0]
    assert notif["template"] == "queue_token_issued"
    assert token in notif["message"]
    assert notif["recipient_phone"] == "+91 91234 56789"


def test_emergency_triage_notification(client: TestClient, sample_hospital_data):
    """Verify that an emergency phrase creates a high-priority trauma alert notification."""
    res = client.post(
        "/api/assistant/chat",
        json={"message": "Severe crushing chest pain and profuse sweating", "language": "en"},
    )
    assert res.status_code == 200

    history = get_notification_history()
    trauma_notifs = [n for n in history if n["template"] == "triage_escalation"]
    assert len(trauma_notifs) > 0
    assert trauma_notifs[0]["channel"] == "emergency_broadcast"


def test_notifications_recent_endpoint(client: TestClient, sample_hospital_data):
    """Verify the /api/notifications/recent endpoint returns audit records."""
    from app.services.notification_service import notification_service

    notification_service.send_appointment_confirmed(
        phone="+919876543210",
        patient_name="Test Patient",
        booking_ref="APT-TEST-001",
        doctor_name="Dr. Test",
        dept_name="Cardiology",
        apt_date="2026-10-25",
        start_time="10:00",
    )

    res = client.get("/api/notifications/recent")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["recipient_phone"] == "+919876543210"
    assert "APT-TEST-001" in data[0]["message"]
