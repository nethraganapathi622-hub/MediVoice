from datetime import date, time, timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.alert import TriageAlert
from app.models.appointment import Appointment
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.schedule import DoctorSchedule
from app.services.ai_assistant_service import _CONVERSATION_SESSIONS
from app.services.hospital_tools import search_doctors, search_departments


@pytest.fixture(autouse=True)
def clean_sessions():
    """Clear conversation sessions before each test."""
    _CONVERSATION_SESSIONS.clear()
    yield
    _CONVERSATION_SESSIONS.clear()


@pytest.fixture
def hospital_data_with_tomorrow(sample_hospital_data, db_session: Session):
    """Seed schedule for tomorrow specifically for assistant booking tests."""
    doctor = sample_hospital_data["doctor"]
    tomorrow = date.today() + timedelta(days=1)
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
    return sample_hospital_data


def test_assistant_config_endpoint(client: TestClient):
    """Verify assistant capabilities and emergency metadata."""
    res = client.get("/api/assistant/config")
    assert res.status_code == 200
    data = res.json()
    assert "en" in data["supported_languages"]
    assert "ta" in data["supported_languages"]
    assert "hi" in data["supported_languages"]
    assert data["ambulance_number"] == "108"
    assert "emergency_phone" in data


def test_assistant_request_validation(client: TestClient):
    """Verify strict Pydantic validation on assistant chat requests."""
    # Empty message should fail
    res = client.post("/api/assistant/chat", json={"message": "", "language": "en"})
    assert res.status_code == 422

    # Unsupported language code should fail
    res = client.post("/api/assistant/chat", json={"message": "Hello", "language": "fr"})
    assert res.status_code == 422


def test_multilingual_greetings(client: TestClient):
    """Verify multilingual conversational greetings in English, Tamil, and Hindi."""
    # English
    res_en = client.post("/api/assistant/chat", json={"message": "Hello MediVoice", "language": "en"})
    assert res_en.status_code == 200
    data_en = res_en.json()
    assert data_en["intent"] == "greeting"
    assert "MediVoice" in data_en["assistant_text"]
    assert data_en["language"] == "en"

    # Tamil
    res_ta = client.post("/api/assistant/chat", json={"message": "வணக்கம்", "language": "ta"})
    assert res_ta.status_code == 200
    data_ta = res_ta.json()
    assert data_ta["intent"] == "greeting"
    assert "வணக்கம்" in data_ta["assistant_text"]
    assert data_ta["language"] == "ta"

    # Hindi
    res_hi = client.post("/api/assistant/chat", json={"message": "नमस्ते", "language": "hi"})
    assert res_hi.status_code == 200
    data_hi = res_hi.json()
    assert data_hi["intent"] == "greeting"
    assert "नमस्ते" in data_hi["assistant_text"]
    assert data_hi["language"] == "hi"


def test_emergency_escalation_english(client: TestClient, db_session: Session):
    """Verify acute symptoms immediately trigger emergency response and persist critical alert."""
    res = client.post(
        "/api/assistant/chat",
        json={
            "message": "My father has severe chest pain and cannot breathe!",
            "language": "en",
            "patient_phone": "+91 98888 77777",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "emergency"
    assert "CRITICAL MEDICAL ALERT" in data["assistant_text"]
    assert data["action_result"]["emergency"] is True
    assert data["action_result"]["ambulance_number"] == "108"

    # Verify critical triage alert was created in the database
    alert_id = data["action_result"]["alert_id"]
    alert = db_session.query(TriageAlert).filter(TriageAlert.id == alert_id).first()
    assert alert is not None
    assert alert.priority == "critical"
    assert alert.alert_type == "trauma_priority"
    assert "chest pain" in alert.description.lower()


def test_emergency_escalation_tamil_and_hindi(client: TestClient, db_session: Session):
    """Verify acute emergency triggers in Tamil and Hindi."""
    # Tamil: நெஞ்சு வலி
    res_ta = client.post(
        "/api/assistant/chat",
        json={"message": "நோயாளிக்கு கடுமையான நெஞ்சு வலி மற்றும் மயக்கம் உள்ளது", "language": "ta"},
    )
    assert res_ta.status_code == 200
    data_ta = res_ta.json()
    assert data_ta["intent"] == "emergency"
    assert "108" in data_ta["assistant_text"]

    # Hindi: सीने में दर्द
    res_hi = client.post(
        "/api/assistant/chat",
        json={"message": "मरीज के सीने में दर्द है और सांस लेने में तकलीफ हो रही है", "language": "hi"},
    )
    assert res_hi.status_code == 200
    data_hi = res_hi.json()
    assert data_hi["intent"] == "emergency"
    assert "108" in data_hi["assistant_text"]


def test_doctor_search_and_availability_flow(client: TestClient, sample_hospital_data, db_session: Session):
    """Verify doctor specialty query returns matching specialist and availability."""
    # Query for cardiology specialist
    res = client.post(
        "/api/assistant/chat",
        json={"message": "I need to see a cardiologist", "language": "en"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] in ["find_doctor", "book_appointment"]
    assert "Cardiology" in data["assistant_text"] or "Dr. Test Specialist" in data["assistant_text"]
    assert data["action_result"] is not None
    assert "doctors" in data["action_result"]


def test_appointment_confirmation_and_booking_flow(client: TestClient, hospital_data_with_tomorrow, db_session: Session):
    """Verify full multi-turn booking: slot selection -> confirmation prompt -> safe commit."""
    doctor = hospital_data_with_tomorrow["doctor"]
    tomorrow = date.today() + timedelta(days=1)

    # Step 1: User requests specific slot
    res1 = client.post(
        "/api/assistant/chat",
        json={
            "message": f"Book Dr. Test Specialist for {tomorrow} at 10:00",
            "language": "en",
            "patient_name": "Ravi Kumar",
            "patient_phone": "+91 98400 12345",
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    conv_id = data1["conversation_id"]

    # Must require confirmation before executing database mutation!
    assert data1["pending_action"] is not None
    assert data1["pending_action"]["doctor_id"] == doctor.id
    assert data1["pending_action"]["time"] == "10:00"
    assert "confirm" in data1["assistant_text"].lower()

    # Verify no appointment has been created yet!
    initial_count = db_session.query(Appointment).count()
    assert initial_count == 0

    # Step 2: User explicitly confirms
    res2 = client.post(
        "/api/assistant/chat",
        json={
            "conversation_id": conv_id,
            "message": "Yes, please confirm the booking",
            "language": "en",
            "confirmed_action": data1["pending_action"],
            "patient_name": "Ravi Kumar",
            "patient_phone": "+91 98400 12345",
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["action_result"]["success"] is True
    booking_ref = data2["action_result"]["booking_reference"]
    assert booking_ref.startswith("APT-")

    # Verify appointment was persisted in database
    persisted = db_session.query(Appointment).filter(Appointment.booking_reference == booking_ref).first()
    assert persisted is not None
    assert persisted.doctor_id == doctor.id
    assert persisted.patient.display_name == "Ravi Kumar"
    assert str(persisted.start_time).startswith("10:00")


def test_booking_slot_conflict_offers_alternatives(client: TestClient, hospital_data_with_tomorrow, db_session: Session):
    """Verify slot conflicts return alternatives and do not double-book."""
    doctor = hospital_data_with_tomorrow["doctor"]
    tomorrow = date.today() + timedelta(days=1)

    # 1. Book first appointment at 09:30
    res_book1 = client.post(
        "/api/assistant/chat",
        json={
            "message": "Confirm",
            "confirmed_action": {
                "action": "book_appointment",
                "doctor_id": doctor.id,
                "date": str(tomorrow),
                "time": "09:30",
                "patient_name": "Patient One",
                "patient_phone": "+91 91111 22222",
            },
        },
    )
    assert res_book1.status_code == 200
    assert res_book1.json()["action_result"]["success"] is True

    # 2. Attempt to book identical slot at 09:30 for a different patient
    res_conflict = client.post(
        "/api/assistant/chat",
        json={
            "message": "Confirm",
            "confirmed_action": {
                "action": "book_appointment",
                "doctor_id": doctor.id,
                "date": str(tomorrow),
                "time": "09:30",
                "patient_name": "Patient Two",
                "patient_phone": "+91 93333 44444",
            },
        },
    )
    assert res_conflict.status_code == 200
    res_data = res_conflict.json()
    assert res_data["action_result"]["success"] is False
    assert "already booked" in res_data["action_result"]["error"].lower()
    # Alternatives should be offered
    assert "alternative_slots" in res_data["action_result"]


def test_appointment_lookup_unauthorized_privacy(client: TestClient, hospital_data_with_tomorrow, db_session: Session):
    """Verify appointment details require matching phone number and cannot leak other patients' info."""
    doctor = hospital_data_with_tomorrow["doctor"]
    tomorrow = date.today() + timedelta(days=1)

    # Book an appointment
    res = client.post(
        "/api/assistant/chat",
        json={
            "message": "Confirm",
            "confirmed_action": {
                "action": "book_appointment",
                "doctor_id": doctor.id,
                "date": str(tomorrow),
                "time": "11:00",
                "patient_name": "Private Patient",
                "patient_phone": "+91 98888 12345",
            },
        },
    )
    assert res.json()["action_result"]["success"] is True
    booking_ref = res.json()["action_result"]["booking_reference"]


    # Query with incorrect phone number
    res_wrong_phone = client.post(
        "/api/assistant/chat",
        json={
            "message": f"Check status of appointment {booking_ref}",
            "patient_phone": "+91 00000 00000",
        },
    )
    assert res_wrong_phone.status_code == 200
    lookup_res = res_wrong_phone.json()["action_result"]
    assert lookup_res.get("found") is False
    assert "Private Patient" not in res_wrong_phone.json()["assistant_text"]

    # Query with correct phone number
    res_correct = client.post(
        "/api/assistant/chat",
        json={
            "message": f"Check status of appointment {booking_ref}",
            "patient_phone": "+91 98888 12345",
        },
    )
    assert res_correct.status_code == 200
    correct_lookup = res_correct.json()["action_result"]
    assert correct_lookup.get("found") is True
    assert correct_lookup["booking_reference"] == booking_ref


def test_department_directions_tool(client: TestClient, sample_hospital_data):
    """Verify department location and floor wayfinding queries."""
    res = client.post(
        "/api/assistant/chat",
        json={"message": "Where is the Test Cardiology department?", "language": "en"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "hospital_directions"
    assert "Wing B, 1st Floor" in data["assistant_text"]
    assert data["action_result"]["found"] is True


def test_mocked_gemini_provider_integration(client: TestClient, sample_hospital_data, monkeypatch):
    """Verify that when GEMINI_API_KEY is configured, Gemini is invoked and structured JSON is parsed."""
    from app.core.config import Settings, get_settings
    from app.main import app as fastapi_app

    # Mock settings with GEMINI_API_KEY
    mock_settings = Settings(
        PROJECT_NAME="MediVoice API (Test)",
        DATABASE_URL="sqlite:///:memory:",
        GEMINI_API_KEY="AIzaSyMockedKeyForTestingPurposesOnly123",
        ENVIRONMENT="test",
    )
    fastapi_app.dependency_overrides[get_settings] = lambda: mock_settings

    # Mock google.genai Client
    mock_response = MagicMock()
    mock_response.text = (
        '{"intent": "find_doctor", "assistant_text": "Dr. Test Specialist is on duty in Cardiology.", '
        '"specialty": "Cardiology", "doctor_id": 1, "clarification_needed": false}'
    )

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        res = client.post(
            "/api/assistant/chat",
            json={"message": "I want to consult Dr. Test Specialist", "language": "en"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["ai_provider_used"] == "gemini"
        assert "Test Specialist" in data["assistant_text"]

    fastapi_app.dependency_overrides.clear()


def test_mocked_gemini_error_graceful_fallback(client: TestClient, sample_hospital_data, monkeypatch):
    """Verify that when Gemini raises a network/timeout error, MediVoice falls back gracefully without 500 error."""
    from app.core.config import Settings, get_settings
    from app.main import app as fastapi_app

    mock_settings = Settings(
        PROJECT_NAME="MediVoice API (Test)",
        DATABASE_URL="sqlite:///:memory:",
        GEMINI_API_KEY="AIzaSyMockedKeyForTestingPurposesOnly123",
        ENVIRONMENT="test",
    )
    fastapi_app.dependency_overrides[get_settings] = lambda: mock_settings

    # Mock google.genai Client raising exception
    with patch("google.genai.Client", side_effect=Exception("Gemini API connection timeout")):
        res = client.post(
            "/api/assistant/chat",
            json={"message": "I need a heart doctor", "language": "en"},
        )
        assert res.status_code == 200
        data = res.json()
        # Falls back to clinical rule-based engine
        assert data["ai_provider_used"] == "rule_based_fallback"
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def seeded_cardiology_and_neurology(db_session: Session):
    """Seed realistic cardiology and neurology departments, specialists, and schedules matching canonical demo data."""
    card_dept = Department(
        code="CARD",
        name="Cardiology & Heart Care",
        location="Wing B, 2nd Floor",
        floor="2nd Floor",
        extension="Ext. 2401",
        description="Comprehensive cardiac diagnostics, 2D Echo, interventional cardiology.",
        is_active=True,
    )
    neur_dept = Department(
        code="NEUR",
        name="Neurology & Stroke Clinic",
        location="Wing C, 3rd Floor",
        floor="3rd Floor",
        extension="Ext. 3105",
        description="Advanced neurological diagnostics, stroke triage, epilepsy monitoring.",
        is_active=True,
    )
    db_session.add_all([card_dept, neur_dept])
    db_session.flush()

    card_doc = Doctor(
        name="Dr. Arvind Ramanathan",
        department_id=card_dept.id,
        specialty="Senior Consultant Cardiologist",
        qualifications="MBBS, MD (Gen Med), DM (Cardiology)",
        experience="18+ years",
        consultation_fee=800.0,
        room_number="OPD 204, Wing B",
        is_active=True,
    )
    neur_doc = Doctor(
        name="Dr. Meera Vasudevan",
        department_id=neur_dept.id,
        specialty="Chief Neurologist & Stroke Specialist",
        qualifications="MBBS, MD, DM (Neurology), FAAN",
        experience="15+ years",
        consultation_fee=900.0,
        room_number="OPD 312, Wing C",
        is_active=True,
    )
    db_session.add_all([card_doc, neur_doc])
    db_session.flush()

    tomorrow = date.today() + timedelta(days=1)
    for doc in [card_doc, neur_doc]:
        sched = DoctorSchedule(
            doctor_id=doc.id,
            working_date=tomorrow,
            start_time=time(9, 0),
            end_time=time(13, 0),
            slot_duration_minutes=30,
            is_available=True,
        )
        db_session.add(sched)
    db_session.flush()

    return {
        "card_dept": card_dept,
        "neur_dept": neur_dept,
        "card_doc": card_doc,
        "neur_doc": neur_doc,
        "tomorrow": tomorrow,
    }


def test_cardiology_specialist_assistant_lookup(client: TestClient, seeded_cardiology_and_neurology):
    """Verify virtual assistant finds cardiology specialist even with suffix mismatch ('Cardiologist' vs 'Cardiology')."""
    res = client.post(
        "/api/assistant/chat",
        json={"message": "I need a cardiologist for a heart checkup", "language": "en"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] in ["find_doctor", "book_appointment"]
    assert "Dr. Arvind Ramanathan" in data["assistant_text"]
    assert data["action_result"] is not None
    assert any(d["name"] == "Dr. Arvind Ramanathan" for d in data["action_result"].get("doctors", []))
    assert data["action_result"].get("recommended_doctor")["name"] == "Dr. Arvind Ramanathan"
    assert len(data["action_result"].get("slots", [])) > 0


def test_neurology_specialist_assistant_lookup(client: TestClient, seeded_cardiology_and_neurology):
    """Verify virtual assistant finds neurology specialist even with suffix mismatch ('Neurologist' vs 'Neurology')."""
    res = client.post(
        "/api/assistant/chat",
        json={"message": "I have severe headaches and need a neurologist", "language": "en"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] in ["find_doctor", "book_appointment"]
    assert "Dr. Meera Vasudevan" in data["assistant_text"]
    assert data["action_result"] is not None
    assert any(d["name"] == "Dr. Meera Vasudevan" for d in data["action_result"].get("doctors", []))
    assert data["action_result"].get("recommended_doctor")["name"] == "Dr. Meera Vasudevan"
    assert len(data["action_result"].get("slots", [])) > 0


def test_cardiology_and_neurology_appointment_booking_flow(client: TestClient, seeded_cardiology_and_neurology, db_session: Session):
    """Verify complete booking flows for both cardiology and neurology specialists."""
    tomorrow = seeded_cardiology_and_neurology["tomorrow"]
    card_doc = seeded_cardiology_and_neurology["card_doc"]
    neur_doc = seeded_cardiology_and_neurology["neur_doc"]

    # 1. Cardiology booking confirmation & persist
    res1 = client.post(
        "/api/assistant/chat",
        json={
            "message": f"Book Dr. Arvind Ramanathan for {tomorrow} at 10:00",
            "language": "en",
            "patient_name": "Arun Kumar",
            "patient_phone": "+91 98401 11111",
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["pending_action"] is not None
    assert data1["pending_action"]["doctor_id"] == card_doc.id

    res1_confirm = client.post(
        "/api/assistant/chat",
        json={
            "conversation_id": data1["conversation_id"],
            "message": "Yes, please confirm",
            "language": "en",
            "confirmed_action": data1["pending_action"],
            "patient_name": "Arun Kumar",
            "patient_phone": "+91 98401 11111",
        },
    )
    assert res1_confirm.status_code == 200
    assert res1_confirm.json()["action_result"]["success"] is True
    ref1 = res1_confirm.json()["action_result"]["booking_reference"]
    assert ref1.startswith("APT-")

    # 2. Neurology booking confirmation & persist
    res2 = client.post(
        "/api/assistant/chat",
        json={
            "message": f"Book Dr. Meera Vasudevan for {tomorrow} at 10:30",
            "language": "en",
            "patient_name": "Divya Sharma",
            "patient_phone": "+91 98402 22222",
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["pending_action"] is not None
    assert data2["pending_action"]["doctor_id"] == neur_doc.id

    res2_confirm = client.post(
        "/api/assistant/chat",
        json={
            "conversation_id": data2["conversation_id"],
            "message": "Yes, confirm booking",
            "language": "en",
            "confirmed_action": data2["pending_action"],
            "patient_name": "Divya Sharma",
            "patient_phone": "+91 98402 22222",
        },
    )
    assert res2_confirm.status_code == 200
    assert res2_confirm.json()["action_result"]["success"] is True
    ref2 = res2_confirm.json()["action_result"]["booking_reference"]
    assert ref2.startswith("APT-")


def test_hospital_tools_specialty_lookup_cardiology_and_neurology(db_session: Session, seeded_cardiology_and_neurology):
    """Verify search_doctors and search_departments tools handle canonical and aliased queries for Cardiology and Neurology."""
    # Test Cardiology lookup
    for term in ["Cardiology", "cardiology", "cardiologist", "heart"]:
        docs = search_doctors(db_session, specialty=term)
        assert len(docs) >= 1, f"Expected doctors for '{term}', got none"
        assert docs[0]["name"] == "Dr. Arvind Ramanathan"
        assert docs[0]["department_name"] == "Cardiology & Heart Care"

    # Test Neurology lookup
    for term in ["Neurology", "neurology", "neurologist", "brain"]:
        docs = search_doctors(db_session, specialty=term)
        assert len(docs) >= 1, f"Expected doctors for '{term}', got none"
        assert docs[0]["name"] == "Dr. Meera Vasudevan"
        assert docs[0]["department_name"] == "Neurology & Stroke Clinic"

    # Test Department lookup
    card_depts = search_departments(db_session, query="cardio")
    assert len(card_depts) >= 1
    assert card_depts[0]["code"] == "CARD"

    neur_depts = search_departments(db_session, query="neuro")
    assert len(neur_depts) >= 1
    assert neur_depts[0]["code"] == "NEUR"


@pytest.fixture
def seeded_all_eight_specialties(db_session: Session):
    """Seed all 8 canonical hospital departments, specialists, and schedules."""
    data = [
        ("CARD", "Cardiology & Heart Care", "Wing B, 2nd Floor", "Dr. Arvind Ramanathan", "Senior Consultant Cardiologist", 800.0, "OPD 204, Wing B"),
        ("NEUR", "Neurology & Stroke Clinic", "Wing C, 3rd Floor", "Dr. Meera Vasudevan", "Chief Neurologist & Stroke Specialist", 900.0, "OPD 312, Wing C"),
        ("ORTH", "Orthopedics & Joint Replacement", "Wing A, 1st Floor", "Dr. Rajesh K. Sundaram", "Senior Orthopedic & Joint Surgeon", 850.0, "OPD 108, Wing A"),
        ("PEDI", "Pediatrics & Child Wellness", "Wing D, 2nd Floor", "Dr. Ananya Sen", "Consultant Pediatrician", 700.0, "OPD 218, Wing D"),
        ("EMRG", "Emergency & Critical Trauma Unit", "Block A, Ground Floor", "Dr. Vikramaditya Rao", "Emergency Medicine Director", 600.0, "Trauma Desk, Block A"),
        ("GENMED", "Internal & Preventive Medicine", "Wing A, 1st Floor", "Dr. Pradeep Narayanan", "Lead Physician, Internal Medicine", 650.0, "OPD 102, Wing A"),
        ("RAD", "Radiology & Diagnostic Imaging", "Basement 1", "Dr. Sunita Kulkarni", "Head of Diagnostic Imaging", 750.0, "Reporting Bay 3, Basement 1"),
        ("ONCO", "Medical Oncology & Day Care", "Wing E, 4th Floor", "Dr. Shalini Mukhopadhyay", "Consultant Medical Oncologist", 1000.0, "OPD 405, Wing E"),
    ]
    tomorrow = date.today() + timedelta(days=1)
    doctors = {}
    departments = {}
    for code, dept_name, loc, doc_name, spec, fee, room in data:
        dept = Department(code=code, name=dept_name, location=loc, floor="1st Floor", is_active=True)
        db_session.add(dept)
        db_session.flush()
        departments[code] = dept

        doc = Doctor(
            name=doc_name,
            department_id=dept.id,
            specialty=spec,
            qualifications="MBBS, MD, Specialist",
            experience="12+ years",
            consultation_fee=fee,
            room_number=room,
            is_active=True,
        )
        db_session.add(doc)
        db_session.flush()
        doctors[code] = doc

        sched = DoctorSchedule(
            doctor_id=doc.id,
            working_date=tomorrow,
            start_time=time(9, 0),
            end_time=time(13, 0),
            slot_duration_minutes=30,
            is_available=True,
        )
        db_session.add(sched)
    db_session.flush()
    return {"departments": departments, "doctors": doctors, "tomorrow": tomorrow}


def test_sequential_specialty_switch_cardiology_to_neurology(client: TestClient, seeded_all_eight_specialties):
    """Reproduction Test: In the same conversation, querying Cardiology then Neurology MUST recommend Neurology."""
    conv_id = "test-switch-cardio-to-neuro"

    # Turn 1: Cardiology
    res1 = client.post(
        "/api/assistant/chat",
        json={"conversation_id": conv_id, "message": "I need a cardiologist", "language": "en"},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert "Arvind Ramanathan" in data1["assistant_text"]

    # Turn 2: Neurology in SAME conversation
    res2 = client.post(
        "/api/assistant/chat",
        json={"conversation_id": conv_id, "message": "Now I need a neurologist", "language": "en"},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert "Meera Vasudevan" in data2["assistant_text"], "Must recommend Dr. Meera Vasudevan for Neurology"
    assert "Arvind Ramanathan" not in data2["assistant_text"], "Must NOT reuse previous cardiologist!"


def test_sequential_specialty_switch_neurology_to_cardiology(client: TestClient, seeded_all_eight_specialties):
    """Reverse Order Test: Querying Neurology then Cardiology in the same conversation MUST recommend Cardiology."""
    conv_id = "test-switch-neuro-to-cardio"

    # Turn 1: Neurology
    res1 = client.post(
        "/api/assistant/chat",
        json={"conversation_id": conv_id, "message": "I need a neurologist", "language": "en"},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert "Meera Vasudevan" in data1["assistant_text"]

    # Turn 2: Cardiology in SAME conversation
    res2 = client.post(
        "/api/assistant/chat",
        json={"conversation_id": conv_id, "message": "Now I need a cardiologist", "language": "en"},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert "Arvind Ramanathan" in data2["assistant_text"], "Must recommend Dr. Arvind Ramanathan for Cardiology"
    assert "Meera Vasudevan" not in data2["assistant_text"], "Must NOT reuse previous neurologist!"


def test_all_eight_specialties_and_symptoms(client: TestClient, seeded_all_eight_specialties):
    """Verify doctor recommendations across all 8 clinical departments and common symptom inquiries."""
    test_cases = [
        ("I need a pediatrician for my child", "Ananya Sen"),
        ("Find a pediatrician", "Ananya Sen"),
        ("I need a children's doctor", "Ananya Sen"),
        ("I need a cardiologist", "Arvind Ramanathan"),
        ("I have a heart-related concern", "Arvind Ramanathan"),
        ("Find a heart specialist", "Arvind Ramanathan"),
        ("I need a neurologist", "Meera Vasudevan"),
        ("I have frequent headaches and want a neurologist", "Meera Vasudevan"),
        ("Which neurologists are available tomorrow?", "Meera Vasudevan"),
        ("I need a general physician", "Pradeep Narayanan"),
        ("I have a general health concern", "Pradeep Narayanan"),
        ("I have knee or joint pain and need an orthopedic specialist", "Rajesh K. Sundaram"),
        ("I need an orthopedic surgeon", "Rajesh K. Sundaram"),
        ("I need to consult an oncologist", "Shalini Mukhopadhyay"),
        ("I need diagnostic imaging", "Sunita Kulkarni"),
        ("Where can I get a scan?", "Sunita Kulkarni"),
        ("I need an emergency doctor", "Vikramaditya Rao"),
    ]
    for msg, expected_doc in test_cases:
        res = client.post("/api/assistant/chat", json={"message": msg, "language": "en"})
        assert res.status_code == 200
        data = res.json()
        assert expected_doc in data["assistant_text"], f"Failed for '{msg}': expected {expected_doc}, got {data['assistant_text']}"


def test_general_doctor_discovery_clears_stale_session(client: TestClient, seeded_all_eight_specialties):
    """Verify 'Which doctors are available at your hospital?' returns all active doctors even after a specific doctor was queried."""
    conv_id = "test-discovery-clears-stale"

    # Turn 1: Specific doctor
    client.post(
        "/api/assistant/chat",
        json={"conversation_id": conv_id, "message": "I need a cardiologist", "language": "en"},
    )

    # Turn 2: Broad hospital discovery
    res2 = client.post(
        "/api/assistant/chat",
        json={"conversation_id": conv_id, "message": "Which doctors are available at your hospital?", "language": "en"},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert "on-duty hospital specialists" in data2["assistant_text"]
    assert "doctors" in data2["action_result"]
    assert len(data2["action_result"]["doctors"]) == 8


def test_department_name_and_code_lookups(db_session: Session, seeded_all_eight_specialties):
    """Verify department-name and department-code matching for all 8 departments."""
    codes = ["CARD", "NEUR", "ORTH", "PEDI", "EMRG", "GENMED", "RAD", "ONCO"]
    for code in codes:
        depts = search_departments(db_session, query=code)
        assert len(depts) >= 1, f"Expected department for code {code}"
        assert depts[0]["code"] == code

        docs = search_doctors(db_session, specialty=code)
        assert len(docs) >= 1, f"Expected doctors for code {code}"


def test_collision_prevention_orthopedics_vs_pediatrics(db_session: Session, seeded_all_eight_specialties):
    """Verify that 'orthopedics' never collides with 'pediatrics' despite the substring 'pedi' inside 'orthopedics'."""
    docs = search_doctors(db_session, specialty="orthopedics")
    assert len(docs) == 1
    assert docs[0]["name"] == "Dr. Rajesh K. Sundaram"
    assert docs[0]["name"] != "Dr. Ananya Sen"


def test_multi_turn_booking_flow_full_lifecycle(client: TestClient, seeded_all_eight_specialties):
    """Verify multi-turn booking: doctor selection -> slot picking -> confirmation -> check status."""
    conv_id = "test-full-lifecycle-booking"
    tomorrow = date.today() + timedelta(days=1)

    # Turn 1: Inquire about neurologist availability
    res1 = client.post(
        "/api/assistant/chat",
        json={"conversation_id": conv_id, "message": "Which neurologists are available tomorrow?", "language": "en"},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert "Meera Vasudevan" in data1["assistant_text"]
    assert data1["action_result"] is not None
    assert "available_slots" in data1["action_result"]
    assert len(data1["action_result"]["available_slots"]) > 0

    # Turn 2: Select a specific slot time
    res2 = client.post(
        "/api/assistant/chat",
        json={
            "conversation_id": conv_id,
            "message": "10:00",
            "language": "en",
            "patient_name": "Kavitha Raj",
            "patient_phone": "+91 99400 88888",
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert "Please confirm your appointment" in data2["assistant_text"]
    assert "Dr. Meera Vasudevan" in data2["assistant_text"]
    assert data2["pending_action"] is not None
    assert data2["pending_action"]["time"] == "10:00"

    # Turn 3: Confirm booking
    res3 = client.post(
        "/api/assistant/chat",
        json={
            "conversation_id": conv_id,
            "message": "Confirm",
            "language": "en",
            "patient_name": "Kavitha Raj",
            "patient_phone": "+91 99400 88888",
        },
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert "successfully confirmed" in data3["assistant_text"]
    assert data3["action_result"]["success"] is True
    booking_ref = data3["action_result"]["booking_reference"]
    assert booking_ref.startswith("APT-")

    # Turn 4: Check appointment with reference
    res4 = client.post(
        "/api/assistant/chat",
        json={
            "conversation_id": conv_id,
            "message": f"Check status for {booking_ref}",
            "language": "en",
            "patient_phone": "+91 99400 88888",
        },
    )
    assert res4.status_code == 200
    data4 = res4.json()
    assert booking_ref in data4["assistant_text"]
    assert "Dr. Meera Vasudevan" in data4["assistant_text"]


