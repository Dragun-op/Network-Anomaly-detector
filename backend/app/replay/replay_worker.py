"""
On a timer: pull a flow, score it, and -- if it looks anomalous -- write
an Incident and push it over the WebSocket. Normal-looking flows are
dropped (matches real IDS behavior: we only alert on what the scorer flags).

Started/stopped from main.py's lifespan so it runs for the life of the app
and is trivially disabled via NT_REPLAY_ENABLED=false for tests.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from app.config import get_settings
from app.db import SessionLocal
from app.inference.explain import explain
from app.inference.model import get_scorer
from app.replay.flow_source import next_flow
from app.services import incidents_service
from app.ws import manager


async def _tick(scorer):
    flow = next_flow()
    scored = scorer.score(flow)
    if scored.attack_type is None:
        return  # normal traffic -- no incident raised

    contributions = explain(scorer, scored, flow)

    db = SessionLocal()
    try:
        inc = incidents_service.create_incident(
            db,
            timestamp=dt.datetime.now(dt.timezone.utc),
            src_ip=flow["src_ip"],
            dst_ip=flow["dst_ip"],
            protocol=flow["protocol"],
            attack_type=scored.attack_type,
            severity=scored.severity,
            confidence=scored.confidence,
            status="new",
            packet_count=flow["packet_count"],
            explanation=contributions,
        )
    finally:
        db.close()

    await manager.broadcast(
        {
            "id": inc.id,
            "timestamp": inc.timestamp.isoformat(),
            "src_ip": inc.src_ip,
            "dst_ip": inc.dst_ip,
            "protocol": inc.protocol,
            "attack_type": inc.attack_type,
            "severity": inc.severity,
            "confidence": inc.confidence,
            "status": inc.status,
            "packet_count": inc.packet_count,
        }
    )


async def run_forever():
    settings = get_settings()
    scorer = get_scorer()
    while True:
        await _tick(scorer)
        await asyncio.sleep(settings.replay_interval_seconds)


def start(app_state) -> asyncio.Task | None:
    settings = get_settings()
    if not settings.replay_enabled:
        return None
    task = asyncio.create_task(run_forever())
    app_state.replay_task = task
    return task


def stop(app_state):
    task = getattr(app_state, "replay_task", None)
    if task:
        task.cancel()
