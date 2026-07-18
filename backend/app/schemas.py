"""
Response/request shapes. These intentionally mirror the API contract
field-for-field so the frontend needs zero changes once wired to the real API.
"""
import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high", "critical"]
Status = Literal["new", "investigating", "resolved"]


class FeatureContribution(BaseModel):
    feature: str
    contribution: int  # contributions across the list sum to 100


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    timestamp: dt.datetime
    src_ip: str
    dst_ip: str
    protocol: str
    attack_type: str
    severity: Severity
    confidence: int
    status: Status
    packet_count: int
    explanation: list[FeatureContribution] | None = None


class IncidentListOut(BaseModel):
    total: int
    items: list[IncidentOut]


class SummaryOut(BaseModel):
    total: int
    low: int
    medium: int
    high: int
    critical: int


class IncidentPatch(BaseModel):
    status: Status


class HealthOut(BaseModel):
    status: str = "ok"
    time: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))


class MetricsOut(BaseModel):
    threshold: float
    precision: float
    recall: float
    false_positive_rate: float
    algorithm: str | None = None
    trained_at: dt.datetime | None = None


class ThresholdPatch(BaseModel):
    threshold: float = Field(ge=0.0, le=1.0)
