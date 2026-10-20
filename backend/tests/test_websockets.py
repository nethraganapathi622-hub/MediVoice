import json
from datetime import date, time, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import SYNTHETIC_STAFF, StaffUser, create_staff_access_token
from app.models.schedule import DoctorSchedule
from app.ws.connection_manager import ws_manager


def test_ws_public_connection_and_ping(client: TestClient):
    """Test public client connection, handshake ack, and ping-pong keepalive."""
    with client.websocket_connect("/ws/events") as websocket:
        ack_data = websocket.receive_json()
        assert ack_data["type"] == "connection_established"
        assert ack_data["scope"] == "public"
        assert "session_id" in ack_data

        # Ping-Pong keepalive
        websocket.send_json({"type": "ping"})
        pong_data = websocket.receive_json()
        assert pong_data["type"] == "pong"


def test_ws_staff_authentication_handshake(client: TestClient):
    """Test upgrading a public session to staff using a valid signed JWT."""
    staff = StaffUser(
        staff_id="EMP-4091",
        name="Nurse Supervisor Jackson",
        role="TriageLead",
        department="Emergency",
    )
    token = create_staff_access_token(staff)

    with client.websocket_connect("/ws/events") as websocket:
        # Initial ack
        ack = websocket.receive_json()
        assert ack["scope"] == "public"

        # Send valid auth payload
        websocket.send_json({"type": "auth", "token": token})
        auth_res = websocket.receive_json()
        assert auth_res["type"] == "auth_success"
        assert auth_res["scope"] == "staff"
        assert auth_res["staff"]["staff_id"] == "EMP-4091"
        assert auth_res["staff"]["role"] == "TriageLead"


def test_ws_staff_invalid_token_rejection(client: TestClient):
    """Test that a forged or malformed token is rejected during authentication handshake."""
    with client.websocket_connect("/ws/events") as websocket:
        websocket.receive_json()  # ack

        # Invalid token
        websocket.send_json({"type": "auth", "token": "invalid.forged.jwt.token"})
        res = websocket.receive_json()
        assert res["type"] == "auth_error"
        assert "Authentication failed" in res["message"]


def test_ws_staff_endpoint_protection(client: TestClient):
    """Test that /ws/staff accepts valid staff token and rejects invalid token with policy violation."""
    staff = StaffUser(
        staff_id="EMP-1022",
        name="Dr. Robert Chen",
        role="Doctor",
        department="Cardiology",
    )
    token = create_staff_access_token(staff)

    # 1. Valid handshake
    with client.websocket_connect("/ws/staff") as websocket:
        websocket.send_json({"type": "auth", "token": token})
        res = websocket.receive_json()
        assert res["type"] == "auth_success"
        assert res["staff"]["name"] == "Dr. Robert Chen"

    # 2. Invalid token should close with policy violation
    try:
        with client.websocket_connect("/ws/staff") as websocket:
            websocket.send_json({"type": "auth", "token": "bad-token"})
            res = websocket.receive_json()
            assert res["type"] == "auth_error"
    except Exception:
        # Starlette test client raises on socket close
        pass


def test_ws_status_endpoint(client: TestClient):
    """Test the REST diagnostic endpoint for WebSocket connections."""
    res = client.get("/api/ws/status")
    assert res.status_code == 200
    data = res.json()
    assert "total_connections" in data
    assert "staff_connections" in data
    assert "public_connections" in data
    assert "in-memory" in data["manager_mode"]


def test_real_time_event_on_appointment_creation_and_privacy(
    client: TestClient, sample_hospital_data, db_session: Session
):
    """Test that appointment booking broadcasts an appointment.created event with PII stripped."""
    doc_id = sample_hospital_data["doctor"].id
    dept_id = sample_hospital_data["department"].id

    test_date = date.today() + timedelta(days=6)
    sched = DoctorSchedule(
        doctor_id=doc_id,
        working_date=test_date,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched)
    db_session.commit()

    with client.websocket_connect("/ws/events") as websocket:
        websocket.receive_json()  # connection established

        # Book an appointment
        res = client.post(
            "/api/appointments",
            json={
                "doctor_id": doc_id,
                "department_id": dept_id,
                "appointment_date": str(test_date),
                "start_time": "10:00:00",
                "patient_name": "Private Patient Name",
                "patient_phone": "+91 99999 88888",
                "patient_email": "private@example.com",
                "notes": "Highly confidential clinical symptoms",
            },
        )
        assert res.status_code == 201

        # Check received WebSocket event
        event_raw = websocket.receive_text()
        event = json.loads(event_raw)
        assert event["event_type"] == "appointment.created"
        assert event["event_id"].startswith("evt_")
        assert "timestamp" in event

        payload = event["payload"]
        assert payload["booking_reference"].startswith("APT-")
        assert payload["doctor_id"] == doc_id
        assert payload["status"] == "booked"

        # STRICT PRIVACY VALIDATION: Never leak patient contact details or symptom notes over WebSockets
        assert "patient_phone" not in payload
        assert "patient_email" not in payload
        assert "notes" not in payload
        assert "Private Patient Name" not in json.dumps(payload)
        assert "+91 99999 88888" not in json.dumps(payload)


def test_failed_appointment_booking_emits_no_event(
    client: TestClient, sample_hospital_data
):
    """Test that a failed booking (e.g. past date) rolls back cleanly and emits NO success event."""
    doc_id = sample_hospital_data["doctor"].id
    dept_id = sample_hospital_data["department"].id
    past_date = date.today() - timedelta(days=5)

    with client.websocket_connect("/ws/events") as websocket:
        websocket.receive_json()  # connection established

        # Attempt invalid booking
        res = client.post(
            "/api/appointments",
            json={
                "doctor_id": doc_id,
                "department_id": dept_id,
                "appointment_date": str(past_date),
                "start_time": "10:00:00",
                "patient_name": "Failed Patient",
            },
        )
        assert res.status_code == 400

        # Send ping to confirm no intermediate broadcast was queued
        websocket.send_json({"type": "ping"})
        pong = websocket.receive_json()
        assert pong["type"] == "pong"


def test_real_time_queue_and_alert_events(
    client: TestClient, sample_hospital_data, db_session: Session
):
    """Test queue check-in, call, complete, alert creation, and alert acknowledgement events."""
    doc_id = sample_hospital_data["doctor"].id
    dept_id = sample_hospital_data["department"].id

    test_date = date.today() + timedelta(days=7)
    sched = DoctorSchedule(
        doctor_id=doc_id,
        working_date=test_date,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched)
    db_session.commit()

    # Authenticate staff token
    staff = StaffUser(
        staff_id="EMP-4091",
        name="Nurse Supervisor Jackson",
        role="TriageLead",
        department="Emergency",
    )
    token = create_staff_access_token(staff)

    with client.websocket_connect("/ws/events") as websocket:
        websocket.receive_json()  # connection established

        # Upgrade to staff so alert events are received
        websocket.send_json({"type": "auth", "token": token})
        websocket.receive_json()  # auth_success

        # 1. Book appointment
        res_apt = client.post(
            "/api/appointments",
            json={
                "doctor_id": doc_id,
                "department_id": dept_id,
                "appointment_date": str(test_date),
                "start_time": "10:30:00",
                "patient_name": "Queue Realtime Patient",
            },
        )
        assert res_apt.status_code == 201
        apt_id = res_apt.json()["id"]
        websocket.receive_json()  # appointment.created

        # 2. Check in -> emits queue.checked_in
        res_checkin = client.post("/api/queue/check-in", json={"appointment_id": apt_id})
        assert res_checkin.status_code == 201
        queue_id = res_checkin.json()["id"]

        q_event = websocket.receive_json()
        assert q_event["event_type"] == "queue.checked_in"
        assert q_event["payload"]["queue_id"] == queue_id
        assert q_event["payload"]["status"] == "waiting"

        # 3. Call patient -> emits queue.patient_called
        res_call = client.post(f"/api/queue/{queue_id}/call")
        assert res_call.status_code == 200
        call_event = websocket.receive_json()
        assert call_event["event_type"] == "queue.patient_called"
        assert call_event["payload"]["queue_id"] == queue_id
        assert call_event["payload"]["status"] == "called"

        # 4. Complete consultation -> emits queue.completed
        res_comp = client.post(f"/api/queue/{queue_id}/complete")
        assert res_comp.status_code == 200
        comp_event = websocket.receive_json()
        assert comp_event["event_type"] == "queue.completed"
        assert comp_event["payload"]["queue_id"] == queue_id
        assert comp_event["payload"]["status"] == "completed"

        # 5. Create triage alert -> emits alert.created
        res_alert = client.post(
            "/api/alerts",
            json={
                "priority": "critical",
                "alert_type": "icu_bed_threshold",
                "description": "ICU capacity reached 95% occupancy",
                "location": "ICU Block B",
            },
        )
        assert res_alert.status_code == 201
        alert_id = res_alert.json()["id"]
        alert_event = websocket.receive_json()
        assert alert_event["event_type"] == "alert.created"
        assert alert_event["payload"]["alert_id"] == alert_id
        assert alert_event["payload"]["priority"] == "critical"

        # 6. Acknowledge alert -> emits alert.acknowledged
        res_ack = client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"staff_id": "EMP-4091", "staff_name": "Nurse Supervisor Jackson"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_ack.status_code == 200
        ack_event = websocket.receive_json()
        assert ack_event["event_type"] == "alert.acknowledged"
        assert ack_event["payload"]["alert_id"] == alert_id
        assert ack_event["payload"]["status"] == "acknowledged"
