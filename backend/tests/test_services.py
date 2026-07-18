import datetime as dt

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import Base, init_db, make_engine
from app.models_orm import ModelVersion
from app.services import incidents_service, metrics_service, summary_service


@pytest.fixture
def db_session():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def make_incident(db, **overrides):
    fields = dict(
        timestamp=dt.datetime.now(dt.timezone.utc),
        src_ip="10.0.0.1",
        dst_ip="10.0.0.2",
        protocol="TCP",
        attack_type="Port Scan",
        severity="high",
        confidence=88,
        status="new",
        packet_count=1200,
        explanation=[],
    )
    fields.update(overrides)
    return incidents_service.create_incident(db, **fields)


def test_next_incident_id_increments(db_session):
    id1 = incidents_service.next_incident_id(db_session)
    make_incident(db_session, id=id1)
    id2 = incidents_service.next_incident_id(db_session)
    assert id1 != id2
    assert id2 == "INC-000002"


def test_list_incidents_filters_by_severity(db_session):
    make_incident(db_session, severity="critical")
    make_incident(db_session, severity="low")

    total, items = incidents_service.list_incidents(db_session, severity=["critical"])
    assert total == 1
    assert items[0].severity == "critical"


def test_list_incidents_filters_by_ip_search(db_session):
    make_incident(db_session, src_ip="45.53.71.50")
    make_incident(db_session, src_ip="10.10.10.10")

    total, items = incidents_service.list_incidents(db_session, q="45.53")
    assert total == 1
    assert items[0].src_ip == "45.53.71.50"


def test_list_incidents_pagination(db_session):
    for _ in range(5):
        make_incident(db_session)

    total, page1 = incidents_service.list_incidents(db_session, limit=2, offset=0)
    _, page2 = incidents_service.list_incidents(db_session, limit=2, offset=2)
    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2
    assert {i.id for i in page1}.isdisjoint({i.id for i in page2})


def test_update_status(db_session):
    inc = make_incident(db_session)
    updated = incidents_service.update_status(db_session, inc.id, "investigating")
    assert updated.status == "investigating"


def test_update_status_missing_id_returns_none(db_session):
    assert incidents_service.update_status(db_session, "INC-999999", "resolved") is None


def test_summary_counts_by_severity(db_session):
    make_incident(db_session, severity="critical")
    make_incident(db_session, severity="critical")
    make_incident(db_session, severity="low")

    summary = summary_service.get_summary(db_session)
    assert summary == {"total": 3, "low": 1, "medium": 0, "high": 0, "critical": 2}


def test_metrics_falls_back_when_no_model_registered(db_session):
    metrics = metrics_service.get_current_metrics(db_session)
    assert "no trained model" in metrics["algorithm"]


def test_metrics_reads_latest_model_version(db_session):
    db_session.add(
        ModelVersion(
            trained_at=dt.datetime.now(dt.timezone.utc),
            algorithm="XGBoost",
            threshold=0.62,
            metrics={"precision": 0.91, "recall": 0.88, "false_positive_rate": 0.02},
        )
    )
    db_session.commit()

    metrics = metrics_service.get_current_metrics(db_session)
    assert metrics["algorithm"] == "XGBoost"
    assert metrics["precision"] == 0.91
