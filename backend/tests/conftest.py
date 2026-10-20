from datetime import date, time, timedelta
from decimal import Decimal
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.database import Base, get_db
from app.main import app as fastapi_app
import app.models as _hospital_models  # noqa: F401
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.schedule import DoctorSchedule
from app.models.patient import Patient


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Fixture providing isolated settings for testing."""
    return Settings(
        PROJECT_NAME="MediVoice API (Test)",
        VERSION="0.1.0-test",
        ENVIRONMENT="test",
        DEBUG=True,
        ALLOWED_ORIGINS=["http://localhost:5173", "http://testserver"],
        DATABASE_URL="sqlite:///:memory:",
        DATABASE_CONNECT_TIMEOUT=2,
    )


@pytest.fixture(scope="session")
def test_engine():
    """Create isolated in-memory test database engine with table schema."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Provide a transactional database session rolled back after every test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(test_settings: Settings, db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with dependency overrides for settings and database."""
    fastapi_app.dependency_overrides[get_settings] = lambda: test_settings
    fastapi_app.dependency_overrides[get_db] = lambda: db_session

    with TestClient(fastapi_app, base_url="http://testserver") as test_client:
        yield test_client

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def sample_hospital_data(db_session: Session):
    """Seed sample department, doctor, schedule, and patient for test cases."""
    dept = Department(
        code="TESTCARD",
        name="Test Cardiology",
        location="Wing B, 1st Floor",
        floor="1st Floor",
        extension="Ext. 1111",
        description="Test Cardiac Care",
        is_active=True,
    )
    db_session.add(dept)
    db_session.flush()

    doctor = Doctor(
        name="Dr. Test Specialist",
        department_id=dept.id,
        specialty="Interventional Cardiology",
        qualifications="MBBS, MD, DM",
        experience="10 years",
        consultation_fee=Decimal("750.00"),
        room_number="OPD 101",
        is_active=True,
    )
    db_session.add(doctor)
    db_session.flush()

    # Schedule for today
    today = date.today()
    sched_today = DoctorSchedule(
        doctor_id=doctor.id,
        working_date=today,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration_minutes=30,
        is_available=True,
    )
    db_session.add(sched_today)

    patient = Patient(
        display_name="Test Patient A",
        phone="+91 99999 11111",
        email="test.patient@example.com",
    )
    db_session.add(patient)
    db_session.commit()

    return {
        "department": dept,
        "doctor": doctor,
        "schedule": sched_today,
        "patient": patient,
    }
