import pytest
from sqlalchemy.orm import sessionmaker

import app.db as db_module
from app.db import Base, init_db, make_engine
from app.inference.model import RuleBasedScorer
from app.models_orm import Incident
from app.replay import replay_worker
from app.replay.flow_source import next_flow


@pytest.fixture
def isolated_db(monkeypatch):
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(db_module, "SessionLocal", TestSession)
    monkeypatch.setattr(replay_worker, "SessionLocal", TestSession)
    yield TestSession
    Base.metadata.drop_all(bind=engine)


def test_next_flow_shape():
    flow = next_flow()
    for key in ("src_ip", "dst_ip", "protocol", "packet_count",
                "syn_flag_count", "flow_duration_ms", "packets_per_second"):
        assert key in flow


@pytest.mark.asyncio
async def test_tick_writes_incident_for_attack_like_flow(isolated_db, monkeypatch):
    attack_flow = {
        "src_ip": "1.2.3.4", "dst_ip": "5.6.7.8", "protocol": "TCP",
        "packet_count": 40000, "syn_flag_count": 800,
        "flow_duration_ms": 2, "packets_per_second": 15000,
    }
    monkeypatch.setattr(replay_worker, "next_flow", lambda: attack_flow)

    broadcasted = []

    async def fake_broadcast(payload):
        broadcasted.append(payload)

    monkeypatch.setattr(replay_worker.manager, "broadcast", fake_broadcast)

    await replay_worker._tick(RuleBasedScorer())

    session = isolated_db()
    count = session.query(Incident).count()
    session.close()

    assert count == 1
    assert len(broadcasted) == 1
    assert broadcasted[0]["src_ip"] == "1.2.3.4"


@pytest.mark.asyncio
async def test_tick_skips_normal_flow(isolated_db, monkeypatch):
    normal_flow = {
        "src_ip": "1.2.3.4", "dst_ip": "5.6.7.8", "protocol": "TCP",
        "packet_count": 100, "syn_flag_count": 1,
        "flow_duration_ms": 3000, "packets_per_second": 5,
    }
    monkeypatch.setattr(replay_worker, "next_flow", lambda: normal_flow)

    broadcasted = []
    monkeypatch.setattr(
        replay_worker.manager, "broadcast", lambda p: broadcasted.append(p)
    )

    await replay_worker._tick(RuleBasedScorer())

    session = isolated_db()
    count = session.query(Incident).count()
    session.close()

    assert count == 0
    assert broadcasted == []
