import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db, init_db, make_engine
from app.services import incidents_service
from main import app


@pytest.fixture
def client():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c, TestSession()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def seed_incident(session, **overrides):
    fields = dict(
        timestamp=dt.datetime.now(dt.timezone.utc),
        src_ip="45.53.71.50",
        dst_ip="82.92.210.193",
        protocol="UDP",
        attack_type="Port Scan",
        severity="critical",
        confidence=96,
        status="new",
        packet_count=19462,
        explanation=[
            {"feature": "SYN Flag Count", "contribution": 52},
            {"feature": "Flow Duration", "contribution": 31},
            {"feature": "Bwd Packets/s", "contribution": 17},
        ],
    )
    fields.update(overrides)
    return incidents_service.create_incident(session, **fields)


def test_health(client):
    c, _ = client
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_incidents_empty(client):
    c, _ = client
    r = c.get("/api/incidents")
    assert r.status_code == 200
    assert r.json() == {"total": 0, "items": []}


def test_list_incidents_omits_explanation(client):
    c, db = client
    seed_incident(db)
    r = c.get("/api/incidents")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["explanation"] is None


def test_get_incident_by_id_includes_explanation(client):
    c, db = client
    inc = seed_incident(db)
    r = c.get(f"/api/incidents/{inc.id}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["explanation"]) == 3
    assert sum(f["contribution"] for f in body["explanation"]) == 100


def test_get_incident_404(client):
    c, _ = client
    r = c.get("/api/incidents/INC-999999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Incident not found"


def test_patch_incident_status(client):
    c, db = client
    inc = seed_incident(db)
    r = c.patch(f"/api/incidents/{inc.id}", json={"status": "investigating"})
    assert r.status_code == 200
    assert r.json()["status"] == "investigating"


def test_patch_incident_invalid_status_rejected(client):
    c, db = client
    inc = seed_incident(db)
    r = c.patch(f"/api/incidents/{inc.id}", json={"status": "not-a-real-status"})
    assert r.status_code == 422


def test_patch_incident_404(client):
    c, _ = client
    r = c.patch("/api/incidents/INC-999999", json={"status": "resolved"})
    assert r.status_code == 404


def test_summary(client):
    c, db = client
    seed_incident(db, severity="critical")
    seed_incident(db, severity="critical")
    seed_incident(db, severity="low")
    r = c.get("/api/summary")
    assert r.json() == {"total": 3, "low": 1, "medium": 0, "high": 0, "critical": 2}


def test_filter_by_severity_query_param(client):
    c, db = client
    seed_incident(db, severity="critical")
    seed_incident(db, severity="low")
    r = c.get("/api/incidents", params={"severity": "critical"})
    body = r.json()
    assert body["total"] == 1


def test_filter_by_ip_search(client):
    c, db = client
    seed_incident(db, src_ip="45.53.71.50")
    seed_incident(db, src_ip="1.2.3.4")
    r = c.get("/api/incidents", params={"q": "45.53"})
    assert r.json()["total"] == 1


def test_metrics_endpoint_never_500s_before_model_exists(client):
    c, _ = client
    r = c.get("/api/metrics")
    assert r.status_code == 200
    assert "threshold" in r.json()
