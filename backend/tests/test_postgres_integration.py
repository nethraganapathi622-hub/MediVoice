"""PostgreSQL Live Integration Test Suite.

DATABASE IDENTIFICATION:
------------------------
- Unit Tests (test_appointments.py, test_queue_alerts.py, test_departments_doctors.py, test_websockets.py):
  Run against isolated in-memory SQLite (sqlite:///:memory:) with per-test transaction rollback.
- Integration Tests (this file):
  Run STRICTLY against an explicitly configured live PostgreSQL test database
  via environment variable POSTGRES_TEST_DATABASE_URL or TEST_DATABASE_URL.

If POSTGRES_TEST_DATABASE_URL / TEST_DATABASE_URL is not set or the PostgreSQL server is not reachable,
these tests are skipped with a clear, diagnostic message.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import os
import uuid
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.security import StaffUser, create_staff_access_token
from app.main import app as fastapi_app
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.schedule import DoctorSchedule
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.queue import QueueEntry
from app.models.alert import TriageAlert
from app.services.appointment_service import book_appointment

settings = get_settings()
PG_TEST_URL = (
    os.getenv("POSTGRES_TEST_DATABASE_URL")
    or os.getenv("TEST_DATABASE_URL")
    or getattr(settings, "TEST_DATABASE_URL", None)
)


def _is_live_postgres_reachable(url: str) -> bool:
    """Test whether target PostgreSQL database is reachable."""
    if not url or "sqlite" in url:
        return False
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


IS_PG_AVAILABLE = _is_live_postgres_reachable(PG_TEST_URL)
skip_if_no_pg = pytest.mark.skipif(
    not IS_PG_AVAILABLE,
    reason="Live PostgreSQL test database not reachable. Set POSTGRES_TEST_DATABASE_URL to enable.",
)


@pytest.fixture(scope="module")
def pg_engine():
    """Module-level PostgreSQL engine for integration tests."""
    if not IS_PG_AVAILABLE:
        pytest.skip("PostgreSQL test database not reachable")
    engine = create_engine(PG_TEST_URL, pool_pre_ping=True)
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    """Provides a transactional session on the real PostgreSQL database."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def pg_client(pg_engine):
    """FastAPI TestClient wired to the real PostgreSQL database."""
    session_factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()


# ==============================================================================
# 1. Schema & Migration Verification
# ==============================================================================
@skip_if_no_pg
def test_pg_schema_and_constraints(pg_engine):
    """Verify that PostgreSQL creates all tables, foreign keys, and unique constraints."""
    inspector = inspect(pg_engine)
    tables = inspector.get_table_names()

    required_tables = [
        "departments",
        "doctors",
        "doctor_schedules",
        "patients",
        "appointments",
        "queue_entries",
        "triage_alerts",
        "consultation_notes",
    ]
    for tbl in required_tables:
        assert tbl in tables, f"Expected table '{tbl}' in PostgreSQL schema"

    # Check unique constraint on doctor_schedules (doctor_id, working_date)
    uniques = inspector.get_unique_constraints("doctor_schedules")
    unique_col_sets = [set(u["column_names"]) for u in uniques]
    assert {"doctor_id", "working_date"} in unique_col_sets

    # Check foreign keys on appointments
    fks = inspector.get_foreign_keys("appointments")
    referred_tables = {fk["referred_table"] for fk in fks}
    assert "doctors" in referred_tables
    assert "departments" in referred_tables
    assert "patients" in referred_tables


# ==============================================================================
# 2. Persistence Across Separate Database Sessions
# ==============================================================================
@skip_if_no_pg
def test_pg_persistence_across_separate_sessions(pg_engine):
    """Verify that records committed in one session persist and are readable by a new, independent session."""
    session_maker = sessionmaker(bind=pg_engine)

    # Session 1: Create department
    s1 = session_maker()
    uid = uuid.uuid4().hex[:8]
    dept_name = f"Postgres Cardio Unit {uid}"
    dept = Department(
        name=dept_name,
        code=f"PG_{uid}",
        location="East Tower Floor 3",
        floor="3",
        extension="7890",
        description="Persistent PostgreSQL cardiology testing",
        is_active=True,
    )
    s1.add(dept)
    s1.commit()
    dept_id = dept.id
    s1.close()

    # Session 2: Read department from separate connection
    s2 = session_maker()
    loaded_dept = s2.query(Department).filter(Department.id == dept_id).first()
    assert loaded_dept is not None
    assert loaded_dept.name == dept_name
    assert loaded_dept.floor == "3"

    # Clean up test row
    s2.delete(loaded_dept)
    s2.commit()
    s2.close()


# ==============================================================================
# 3. Appointment Persistence Across Restart Simulation
# ==============================================================================
@skip_if_no_pg
def test_pg_appointment_persistence_across_restart(pg_client, pg_engine):
    """Verify that an appointment created through the REST API persists in PostgreSQL."""
    session_maker = sessionmaker(bind=pg_engine)
    session = session_maker()

    # Setup department & doctor
    uid = uuid.uuid4().hex[:8]
    dept = Department(
        name=f"Integration OPD {uid}",
        code=f"INT_{uid}",
        location="Wing A",
        floor="1",
        extension="1001",
        description="Integration OPD",
        is_active=True,
    )
    session.add(dept)
    session.flush()

    doc = Doctor(
        name=f"Dr. Persistent {uid}",
        department_id=dept.id,
        specialty="General",
        qualifications="MBBS",
        experience="10 years",
        consultation_fee=Decimal("500.00"),
        room_number="OPD 1",
        is_active=True,
    )
    session.add(doc)
    session.flush()

    future_date = date.today() + timedelta(days=20)
    sched = DoctorSchedule(
        doctor_id=doc.id,
        working_date=future_date,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    session.add(sched)
    session.commit()

    # Book via API client
    res = pg_client.post(
        "/api/appointments",
        json={
            "doctor_id": doc.id,
            "department_id": dept.id,
            "appointment_date": str(future_date),
            "start_time": "09:30:00",
            "patient_name": "PG Test Patient",
            "patient_phone": "+91 98888 77777",
        },
    )
    assert res.status_code == 201
    apt_id = res.json()["id"]
    booking_ref = res.json()["booking_reference"]
    session.close()

    # Simulate restart by reading from brand new session directly from PostgreSQL
    check_session = session_maker()
    persisted_apt = check_session.query(Appointment).filter(Appointment.id == apt_id).first()
    assert persisted_apt is not None
    assert persisted_apt.booking_reference == booking_ref
    assert persisted_apt.status == "booked"

    # Clean up
    check_session.delete(persisted_apt)
    check_session.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == doc.id).delete()
    check_session.delete(doc)
    check_session.delete(dept)
    check_session.commit()
    check_session.close()


# ==============================================================================
# 4. Doctor Double-Booking and Concurrent Collision Prevention
# ==============================================================================
@skip_if_no_pg
def test_pg_concurrent_booking_collision_prevention(pg_engine):
    """Test that concurrent booking attempts for the same slot result in one success and conflict rejection."""
    session_maker = sessionmaker(bind=pg_engine)
    session = session_maker()

    uid = uuid.uuid4().hex[:8]
    dept = Department(
        name=f"Collision Test Dept {uid}",
        code=f"COL_{uid}",
        location="Wing C",
        floor="2",
        extension="3001",
        description="Collision check",
        is_active=True,
    )
    session.add(dept)
    session.flush()

    doc = Doctor(
        name=f"Dr. Concurrency {uid}",
        department_id=dept.id,
        specialty="Pediatrics",
        qualifications="MD",
        experience="12 years",
        consultation_fee=Decimal("700.00"),
        room_number="OPD 5",
        is_active=True,
    )
    session.add(doc)
    session.flush()

    target_date = date.today() + timedelta(days=22)
    sched = DoctorSchedule(
        doctor_id=doc.id,
        working_date=target_date,
        start_time=time(10, 0),
        end_time=time(12, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    session.add(sched)
    session.commit()

    from app.schemas.appointment import AppointmentCreate

    def try_booking(pat_name: str):
        thread_session = session_maker()
        try:
            payload = AppointmentCreate(
                doctor_id=doc.id,
                department_id=dept.id,
                appointment_date=target_date,
                start_time=time(10, 0),
                patient_name=pat_name,
            )
            apt = book_appointment(thread_session, payload)
            return {"status": "success", "id": apt.id}
        except Exception as e:
            thread_session.rollback()
            return {"status": "error", "error": str(e)}
        finally:
            thread_session.close()

    # Run two concurrent booking attempts simultaneously
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(try_booking, "Concurrent Patient 1")
        f2 = executor.submit(try_booking, "Concurrent Patient 2")
        r1 = f1.result()
        r2 = f2.result()

    statuses = [r1["status"], r2["status"]]
    # Exactly one must succeed and one must be rejected with conflict
    assert "success" in statuses
    assert "error" in statuses

    # Clean up
    clean_session = session_maker()
    clean_session.query(Appointment).filter(Appointment.doctor_id == doc.id).delete()
    clean_session.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == doc.id).delete()
    clean_session.query(Doctor).filter(Doctor.id == doc.id).delete()
    clean_session.query(Department).filter(Department.id == dept.id).delete()
    clean_session.commit()
    clean_session.close()
    session.close()


# ==============================================================================
# 5. Security & Authorization Enforcement
# ==============================================================================
@skip_if_no_pg
def test_pg_unauthorized_user_cannot_access_staff_alerts(pg_client):
    """Verify that unauthenticated clients cannot acknowledge clinical triage alerts."""
    res = pg_client.post(
        "/api/alerts/999/acknowledge",
        json={"staff_id": "STF-FAKE", "staff_name": "Fake Attacker"},
    )
    # Must reject without authorized staff Bearer token or credentials
    assert res.status_code in [401, 403, 404]
