"""
All incident querying/mutation logic lives here, not in app/api.py, so it
can be unit-tested without spinning up FastAPI and so api.py stays thin.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models_orm import Incident


def next_incident_id(db: Session) -> str:
    """INC-XXXXXX, monotonically increasing, collision-safe against existing rows."""
    existing = db.execute(select(Incident.id)).scalars().all()
    existing_nums = {int(i.split("-")[1]) for i in existing if i.startswith("INC-")}
    n = max(existing_nums, default=0) + 1
    return f"INC-{n:06d}"


def list_incidents(
    db: Session,
    *,
    severity: list[str] | None = None,
    attack_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[Incident]]:
    stmt = select(Incident)

    if severity:
        stmt = stmt.where(Incident.severity.in_(severity))
    if attack_type:
        stmt = stmt.where(Incident.attack_type == attack_type)
    if status:
        stmt = stmt.where(Incident.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Incident.src_ip.like(like)) | (Incident.dst_ip.like(like)))

    total = len(db.execute(stmt).scalars().all())

    stmt = stmt.order_by(Incident.timestamp.desc()).offset(offset).limit(limit)
    items = db.execute(stmt).scalars().all()
    return total, items


def get_incident(db: Session, incident_id: str) -> Incident | None:
    return db.get(Incident, incident_id)


def update_status(db: Session, incident_id: str, status: str) -> Incident | None:
    inc = db.get(Incident, incident_id)
    if inc is None:
        return None
    inc.status = status
    db.commit()
    db.refresh(inc)
    return inc


def create_incident(db: Session, **fields) -> Incident:
    if "id" not in fields:
        fields["id"] = next_incident_id(db)
    inc = Incident(**fields)
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc
