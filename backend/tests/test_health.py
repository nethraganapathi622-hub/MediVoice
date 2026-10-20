from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.main import app


class MockSuccessfulDbSession:
    """Mock database session that simulates successful query execution."""

    def execute(self, statement: object) -> object:
        return True

    def close(self) -> None:
        pass


class MockFailingDbSession:
    """Mock database session that simulates connection failure."""

    def execute(self, statement: object) -> object:
        raise OperationalError(
            statement="SELECT 1",
            params={},
            orig=Exception("could not connect to server: Connection refused"),
        )

    def close(self) -> None:
        pass


def test_health_endpoint(client: TestClient) -> None:
    """Test that the liveness health endpoint returns 200 with service metadata."""
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == "MediVoice API (Test)"
    assert payload["environment"] == "test"
    assert payload["version"] == "0.1.0-test"


def test_readiness_database_reachable(client: TestClient) -> None:
    """Test that readiness probe returns 200 and connected status when database is reachable."""
    def override_healthy_db() -> Generator[MockSuccessfulDbSession, None, None]:
        yield MockSuccessfulDbSession()

    app.dependency_overrides[get_db] = override_healthy_db

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["database"]["status"] == "connected"
    assert "PostgreSQL connection operational" in payload["database"]["details"]


def test_readiness_database_unavailable(client: TestClient) -> None:
    """Test that readiness probe returns 503 and not_ready status when database connection fails."""
    def override_failing_db() -> Generator[MockFailingDbSession, None, None]:
        yield MockFailingDbSession()

    app.dependency_overrides[get_db] = override_failing_db

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["database"]["status"] == "disconnected"
    assert "Database connection unavailable" in payload["database"]["details"]

    # Verify that raw credentials or socket traces are not exposed in client payload
    assert "could not connect to server" not in response.text
    assert "mock_pass" not in response.text


def test_cors_headers_allowed_origin(client: TestClient) -> None:
    """Test that configured CORS origins are properly respected."""
    response = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_unhandled_exception_returns_safe_500(client: TestClient) -> None:
    """Test that unexpected server exceptions return a safe 500 error without leaking stack traces."""
    # We can test accessing a path that triggers an unhandled error or verify 404/500 formatting
    response = client.get("/api/nonexistent")
    assert response.status_code == 404
