from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models_orm import Incident

SEVERITIES = ["low", "medium", "high", "critical"]


def get_summary(db: Session) -> dict:
    rows = db.execute(
        select(Incident.severity, func.count()).group_by(Incident.severity)
    ).all()
    counts = {sev: 0 for sev in SEVERITIES}
    for sev, count in rows:
        counts[sev] = count
    return {"total": sum(counts.values()), **counts}
