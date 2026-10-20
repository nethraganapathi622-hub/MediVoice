from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.doctor import Doctor


def test_list_and_get_departments(client: TestClient, sample_hospital_data):
    """Test department retrieval endpoints."""
    res = client.get("/api/departments")
    assert res.status_code == 200
    depts = res.json()
    assert len(depts) >= 1
    assert any(d["code"] == "TESTCARD" for d in depts)

    dept_id = sample_hospital_data["department"].id
    res_single = client.get(f"/api/departments/{dept_id}")
    assert res_single.status_code == 200
    assert res_single.json()["name"] == "Test Cardiology"

    # Non-existent department
    res_404 = client.get("/api/departments/99999")
    assert res_404.status_code == 404


def test_list_and_filter_doctors(client: TestClient, sample_hospital_data):
    """Test doctor listing with search and department filtering."""
    dept_id = sample_hospital_data["department"].id

    res = client.get(f"/api/doctors?department_id={dept_id}")
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) >= 1
    assert docs[0]["name"] == "Dr. Test Specialist"
    assert docs[0]["department"]["code"] == "TESTCARD"

    # Search filter
    res_search = client.get("/api/doctors?search=Specialist")
    assert res_search.status_code == 200
    assert len(res_search.json()) >= 1

    # Search non-matching
    res_empty = client.get("/api/doctors?search=NonExistentDoctor")
    assert res_empty.status_code == 200
    assert len(res_empty.json()) == 0

    # Single doctor
    doc_id = sample_hospital_data["doctor"].id
    res_doc = client.get(f"/api/doctors/{doc_id}")
    assert res_doc.status_code == 200
    assert res_doc.json()["id"] == doc_id


def test_doctor_availability_calculation(client: TestClient, sample_hospital_data):
    """Test slot generation and availability computation."""
    doc_id = sample_hospital_data["doctor"].id
    today = date.today()

    res = client.get(f"/api/doctors/{doc_id}/availability?date={today}")
    assert res.status_code == 200
    payload = res.json()
    assert payload["is_on_duty"] is True
    assert len(payload["available_slots"]) > 0

    # Past date rejection
    past_date = today - timedelta(days=2)
    res_past = client.get(f"/api/doctors/{doc_id}/availability?date={past_date}")
    assert res_past.status_code == 400
    assert "past" in res_past.json()["detail"].lower()
